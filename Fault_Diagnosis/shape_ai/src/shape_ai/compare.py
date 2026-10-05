from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, f1_score

from .utils import atomic_json


def _parse_named(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("Use NAME=PATH")
    name, path = value.split("=", 1)
    return name.strip(), Path(path.strip())


def _scores(target: np.ndarray, prediction: np.ndarray) -> tuple[float, float]:
    return (
        float(balanced_accuracy_score(target, prediction)),
        float(f1_score(target, prediction, average="macro")),
    )


def paired_parent_bootstrap(
    reference: pd.DataFrame, candidate: pd.DataFrame, replicates: int, seed: int
) -> dict:
    ref = reference[["run_uid", "parent_trajectory_id", "label", "prediction"]].rename(
        columns={"prediction": "reference_prediction"}
    )
    cand = candidate[["run_uid", "parent_trajectory_id", "label", "prediction"]].rename(
        columns={"parent_trajectory_id": "candidate_parent", "label": "candidate_label", "prediction": "candidate_prediction"}
    )
    paired = ref.merge(cand, on="run_uid", validate="one_to_one")
    if len(paired) != len(ref) or len(paired) != len(candidate):
        raise ValueError("Compared prediction files do not cover identical run_uid sets")
    if not (paired["parent_trajectory_id"] == paired["candidate_parent"]).all():
        raise ValueError("Parent identity mismatch between prediction files")
    if not (paired["label"] == paired["candidate_label"]).all():
        raise ValueError("Ground-truth label mismatch between prediction files")

    groups = {parent: group for parent, group in paired.groupby("parent_trajectory_id")}
    parents = np.asarray(sorted(groups))
    point_ref = _scores(paired["label"].to_numpy(), paired["reference_prediction"].to_numpy())
    point_cand = _scores(paired["label"].to_numpy(), paired["candidate_prediction"].to_numpy())
    rng = np.random.default_rng(seed)
    deltas = np.empty((replicates, 2))
    for index in range(replicates):
        sampled = rng.choice(parents, size=len(parents), replace=True)
        target = np.concatenate([groups[parent]["label"].to_numpy() for parent in sampled])
        ref_prediction = np.concatenate(
            [groups[parent]["reference_prediction"].to_numpy() for parent in sampled]
        )
        candidate_prediction = np.concatenate(
            [groups[parent]["candidate_prediction"].to_numpy() for parent in sampled]
        )
        ref_score = _scores(target, ref_prediction)
        candidate_score = _scores(target, candidate_prediction)
        deltas[index] = np.subtract(candidate_score, ref_score)
    names = ("balanced_accuracy", "macro_f1")
    return {
        name: {
            "reference": point_ref[position],
            "candidate": point_cand[position],
            "delta_candidate_minus_reference": point_cand[position] - point_ref[position],
            "delta_ci95": np.quantile(deltas[:, position], [0.025, 0.975]).tolist(),
            "bootstrap_probability_delta_gt_zero": float(np.mean(deltas[:, position] > 0)),
            "bootstrap_two_sided_p": float(
                min(1.0, 2 * min(np.mean(deltas[:, position] <= 0), np.mean(deltas[:, position] >= 0)))
            ),
        }
        for position, name in enumerate(names)
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Paired parent-cluster comparison of model predictions")
    parser.add_argument("--prediction", action="append", required=True, type=_parse_named)
    parser.add_argument("--reference", required=True, help="NAME used as the comparison reference")
    parser.add_argument("--bootstrap", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=20260913)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    paths = dict(args.prediction)
    if len(paths) != len(args.prediction):
        raise SystemExit("Prediction names must be unique")
    if args.reference not in paths:
        raise SystemExit(f"Unknown reference {args.reference!r}")
    frames = {name: pd.read_parquet(path) for name, path in paths.items()}
    seeds = {}
    for name, frame in frames.items():
        unique = frame["seed"].unique() if "seed" in frame else []
        if len(unique) != 1:
            raise SystemExit(f"{name} does not contain exactly one model seed")
        seeds[name] = int(unique[0])
    if len(set(seeds.values())) != 1:
        raise SystemExit(f"Pairwise comparison requires the same seed, found {seeds}")
    results = {}
    for name, frame in frames.items():
        if name == args.reference:
            continue
        results[name] = paired_parent_bootstrap(
            frames[args.reference], frame, args.bootstrap, args.seed
        )
    atomic_json(
        args.output,
        {
            "reference": args.reference,
            "bootstrap_replicates": args.bootstrap,
            "cluster": "parent_trajectory_id",
            "comparisons": results,
        },
    )
    print(f"COMPARISON PASS: {args.output}")


if __name__ == "__main__":
    main()
