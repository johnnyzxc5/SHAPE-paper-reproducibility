from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader
from tqdm import tqdm

from .contracts import CLASS_NAMES
from .data import ShapeH5Dataset, load_index, make_loader
from .metrics import classification_metrics
from .models import build_model
from .utils import atomic_json, seed_everything, sha256_file


def evaluate(
    checkpoint_path: Path,
    index_path: Path,
    output_dir: Path,
    cohort: str,
    split: str | None,
    batch_size: int,
    num_workers: int,
    amp: str,
    *,
    prepared_frame: pd.DataFrame | None = None,
    prepared_loader: DataLoader | None = None,
) -> None:
    if (prepared_frame is None) != (prepared_loader is None):
        raise ValueError("A prepared frame and loader must be supplied together")
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    representation = str(checkpoint["representation"])
    seed = int(checkpoint["seed"])
    seed_everything(seed, deterministic=True)
    if prepared_frame is None:
        frame = load_index(index_path, cohort=cohort, split=split)
        dataset = ShapeH5Dataset(frame, representation)
        loader = make_loader(
            dataset,
            batch_size=batch_size,
            shuffle=False,
            num_workers=num_workers,
            seed=seed,
            pin_memory=True,
            persistent_workers=True,
            prefetch_factor=2,
        )
    else:
        frame = prepared_frame
        loader = prepared_loader
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model_config = checkpoint["model_config"]
    model = build_model(
        representation,
        embedding_dim=int(model_config.get("embedding_dim", 128)),
        head_dim=int(model_config.get("head_dim", 256)),
        dropout=float(model_config.get("dropout", 0.5)),
    )
    model.load_state_dict(checkpoint["model_state"])
    model.to(device).eval()
    amp_dtype = {"off": None, "fp16": torch.float16, "bf16": torch.bfloat16}[amp]

    targets: list[np.ndarray] = []
    predictions: list[np.ndarray] = []
    probabilities: list[np.ndarray] = []
    indices: list[np.ndarray] = []
    with torch.no_grad():
        for inputs, labels, row_indices in tqdm(loader, unit="batch"):
            inputs = inputs.to(device, non_blocking=True)
            with torch.autocast(
                device_type=device.type,
                dtype=amp_dtype,
                enabled=amp_dtype is not None and device.type == "cuda",
            ):
                logits = model(inputs)
            probs = torch.softmax(logits.float(), dim=1).cpu().numpy()
            targets.append(labels.numpy())
            predictions.append(probs.argmax(axis=1))
            probabilities.append(probs)
            indices.append(row_indices.numpy())

    y_true = np.concatenate(targets)
    y_pred = np.concatenate(predictions)
    probs = np.concatenate(probabilities)
    order = np.concatenate(indices)
    result_frame = frame.iloc[order].reset_index(drop=True).copy()
    result_frame["prediction"] = y_pred
    result_frame["prediction_class"] = [CLASS_NAMES[index] for index in y_pred]
    result_frame["representation"] = representation
    result_frame["seed"] = seed
    result_frame["checkpoint"] = str(checkpoint_path.resolve())
    for index, name in enumerate(CLASS_NAMES):
        result_frame[f"prob_{name.lower()}"] = probs[:, index]

    output_dir.mkdir(parents=True, exist_ok=True)
    result_frame.to_parquet(output_dir / "predictions.parquet", index=False)
    metrics = classification_metrics(y_true, y_pred, probs)
    metrics.update(
        {
            "representation": representation,
            "seed": seed,
            "cohort": cohort,
            "split": split,
            "checkpoint_sha256": sha256_file(checkpoint_path),
            "index_sha256": sha256_file(index_path),
        }
    )
    atomic_json(output_dir / "metrics.json", metrics)
    pd.DataFrame(metrics["confusion_matrix"], index=CLASS_NAMES, columns=CLASS_NAMES).to_csv(
        output_dir / "confusion_matrix.csv"
    )
    pd.DataFrame(
        metrics["normalized_confusion_matrix"], index=CLASS_NAMES, columns=CLASS_NAMES
    ).to_csv(output_dir / "confusion_matrix_normalized.csv")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a frozen checkpoint without retraining")
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cohort", default="PRIMARY")
    parser.add_argument("--split", default="test", help="Use 'none' for cohorts without a split")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--amp", choices=("off", "fp16", "bf16"), default="fp16")
    args = parser.parse_args()
    split = None if args.split.lower() == "none" else args.split
    evaluate(
        args.checkpoint,
        args.index,
        args.output,
        args.cohort,
        split,
        args.batch_size,
        args.num_workers,
        args.amp,
    )
    print(f"EVALUATION PASS: {args.output}")


if __name__ == "__main__":
    main()
