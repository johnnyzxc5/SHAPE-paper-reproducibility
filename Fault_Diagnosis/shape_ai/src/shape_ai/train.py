from __future__ import annotations

import argparse
import copy
import os
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import balanced_accuracy_score, f1_score
from torch import nn
from tqdm import tqdm

from .contracts import CLASS_NAMES, REPRESENTATIONS
from .data import ShapeH5Dataset, load_index, make_loader
from .indexing import validate_index
from .models import build_model, parameter_count
from .utils import atomic_json, environment_snapshot, load_json, seed_everything, sha256_file


def _epoch(
    model: nn.Module,
    loader,
    criterion: nn.Module,
    device: torch.device,
    *,
    optimizer=None,
    scaler=None,
    amp_dtype: torch.dtype | None = None,
) -> dict[str, float]:
    training = optimizer is not None
    model.train(training)
    total_loss = 0.0
    targets: list[np.ndarray] = []
    predictions: list[np.ndarray] = []
    context = torch.enable_grad if training else torch.no_grad
    with context():
        for inputs, labels, _ in tqdm(loader, leave=False, unit="batch"):
            inputs = inputs.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)
            if training:
                optimizer.zero_grad(set_to_none=True)
            with torch.autocast(
                device_type=device.type,
                dtype=amp_dtype,
                enabled=amp_dtype is not None and device.type == "cuda",
            ):
                logits = model(inputs)
                loss = criterion(logits, labels)
            if training:
                if scaler is not None and scaler.is_enabled():
                    scaler.scale(loss).backward()
                    scaler.step(optimizer)
                    scaler.update()
                else:
                    loss.backward()
                    optimizer.step()
            total_loss += float(loss.detach()) * labels.shape[0]
            targets.append(labels.detach().cpu().numpy())
            predictions.append(logits.detach().argmax(dim=1).cpu().numpy())
    y_true = np.concatenate(targets)
    y_pred = np.concatenate(predictions)
    return {
        "loss": total_loss / len(y_true),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro")),
    }


def _atomic_checkpoint(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(payload, temporary)
    os.replace(temporary, path)


def train(
    config_path: Path,
    index_override: Path | None,
    output_override: Path | None,
    seed_override: int | None = None,
    batch_override: int | None = None,
    workers_override: int | None = None,
    amp_override: str | None = None,
) -> Path:
    config = copy.deepcopy(load_json(config_path))
    if seed_override is not None:
        config["seed"] = seed_override
    if batch_override is not None:
        config["training"]["batch_size"] = batch_override
    if workers_override is not None:
        config["data"]["num_workers"] = workers_override
    if amp_override is not None:
        config["training"]["amp"] = amp_override
    representation = str(config["representation"])
    if representation not in REPRESENTATIONS:
        raise KeyError(f"Unknown representation {representation}")
    seed = int(config["seed"])
    deterministic = bool(config.get("deterministic", True))
    seed_everything(seed, deterministic=deterministic)

    index_path = (index_override or Path(config["index_path"])).resolve()
    output_root = (output_override or Path(config["output_root"])).resolve()
    run_dir = output_root / representation / f"seed_{seed}"
    if (run_dir / "TRAINING_COMPLETE.json").exists():
        raise FileExistsError(f"Completed run already exists: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)

    full_index = pd.read_parquet(index_path)
    audit = validate_index(full_index, "primary")
    if not audit["pass"]:
        raise RuntimeError(f"Training index failed PRIMARY audit: {audit['errors']}")
    train_frame = load_index(index_path, cohort="PRIMARY", split="train")
    val_frame = load_index(index_path, cohort="PRIMARY", split="val")

    data_config = config["data"]
    training_config = config["training"]
    train_dataset = ShapeH5Dataset(train_frame, representation)
    val_dataset = ShapeH5Dataset(val_frame, representation)
    loader_args = {
        "batch_size": int(training_config["batch_size"]),
        "num_workers": int(data_config["num_workers"]),
        "seed": seed,
        "pin_memory": bool(data_config.get("pin_memory", True)),
        "persistent_workers": bool(data_config.get("persistent_workers", True)),
        "prefetch_factor": int(data_config.get("prefetch_factor", 2)),
    }
    train_loader = make_loader(train_dataset, shuffle=True, drop_last=False, **loader_args)
    val_loader = make_loader(val_dataset, shuffle=False, drop_last=False, **loader_args)

    if not torch.cuda.is_available() and not bool(config.get("allow_cpu", False)):
        raise RuntimeError("CUDA is required for scientific training; set allow_cpu only for smoke tests")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model_config = config["model"]
    model = build_model(
        representation,
        embedding_dim=int(model_config.get("embedding_dim", 128)),
        head_dim=int(model_config.get("head_dim", 256)),
        dropout=float(model_config.get("dropout", 0.5)),
    ).to(device)
    if bool(training_config.get("compile", False)):
        model = torch.compile(model)
    checkpoint_model = model._orig_mod if hasattr(model, "_orig_mod") else model

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(training_config["learning_rate"]),
        weight_decay=float(training_config.get("weight_decay", 0.0)),
    )
    epochs = int(training_config["epochs"])
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    amp_name = str(training_config.get("amp", "fp16")).lower()
    amp_dtype = {"off": None, "fp16": torch.float16, "bf16": torch.bfloat16}[amp_name]
    scaler = torch.cuda.amp.GradScaler(enabled=device.type == "cuda" and amp_dtype == torch.float16)

    resolved = dict(config)
    resolved["index_path"] = str(index_path)
    resolved["output_root"] = str(output_root)
    atomic_json(run_dir / "config.resolved.json", resolved)
    atomic_json(
        run_dir / "provenance.json",
        {
            "environment": environment_snapshot(),
            "index_sha256": sha256_file(index_path),
            "index_audit": audit,
            "parameter_count": parameter_count(checkpoint_model),
            "classes": list(CLASS_NAMES),
        },
    )

    history: list[dict[str, Any]] = []
    best_macro_f1 = -1.0
    best_balanced_accuracy = -1.0
    best_loss = float("inf")
    best_epoch = 0
    patience = int(training_config.get("early_stopping_patience", epochs))
    stale_epochs = 0
    start = time.perf_counter()

    for epoch in range(1, epochs + 1):
        train_metrics = _epoch(
            model, train_loader, criterion, device, optimizer=optimizer, scaler=scaler, amp_dtype=amp_dtype
        )
        val_metrics = _epoch(model, val_loader, criterion, device, amp_dtype=amp_dtype)
        row = {
            "epoch": epoch,
            "learning_rate": optimizer.param_groups[0]["lr"],
            **{f"train_{key}": value for key, value in train_metrics.items()},
            **{f"val_{key}": value for key, value in val_metrics.items()},
        }
        history.append(row)
        pd.DataFrame(history).to_csv(run_dir / "history.csv", index=False)

        score = (val_metrics["macro_f1"], val_metrics["balanced_accuracy"], -val_metrics["loss"])
        best_score = (best_macro_f1, best_balanced_accuracy, -best_loss)
        improved = score > best_score
        checkpoint = {
            "epoch": epoch,
            "representation": representation,
            "seed": seed,
            "classes": list(CLASS_NAMES),
            "model_config": model_config,
            "model_state": checkpoint_model.state_dict(),
            "optimizer_state": optimizer.state_dict(),
            "scheduler_state": scheduler.state_dict(),
            "validation_metrics": val_metrics,
            "index_sha256": sha256_file(index_path),
        }
        _atomic_checkpoint(run_dir / "last.pt", checkpoint)
        if improved:
            best_macro_f1 = val_metrics["macro_f1"]
            best_balanced_accuracy = val_metrics["balanced_accuracy"]
            best_loss = val_metrics["loss"]
            best_epoch = epoch
            stale_epochs = 0
            _atomic_checkpoint(run_dir / "best.pt", checkpoint)
        else:
            stale_epochs += 1
        scheduler.step()
        print(
            f"epoch={epoch:03d} train_f1={train_metrics['macro_f1']:.4f} "
            f"val_f1={val_metrics['macro_f1']:.4f} best_epoch={best_epoch}"
        )
        if stale_epochs >= patience:
            break

    completion = {
        "status": "PASS",
        "representation": representation,
        "seed": seed,
        "best_epoch": best_epoch,
        "best_validation_macro_f1": best_macro_f1,
        "best_validation_balanced_accuracy": best_balanced_accuracy,
        "best_validation_loss": best_loss,
        "epochs_completed": len(history),
        "elapsed_seconds": time.perf_counter() - start,
        "test_evaluated": False,
    }
    atomic_json(run_dir / "TRAINING_COMPLETE.json", completion)
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Train one frozen SHAPE experiment")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--index", type=Path, help="Override index_path in config")
    parser.add_argument("--output-root", type=Path, help="Override output_root in config")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--num-workers", type=int)
    parser.add_argument("--amp", choices=("off", "fp16", "bf16"))
    args = parser.parse_args()
    run_dir = train(
        args.config, args.index, args.output_root, args.seed, args.batch_size, args.num_workers, args.amp
    )
    print(f"TRAINING PASS: {run_dir}")


if __name__ == "__main__":
    main()
