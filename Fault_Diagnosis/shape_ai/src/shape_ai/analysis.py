from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, f1_score

from .utils import atomic_json


def _summary(group: pd.DataFrame) -> pd.Series:
    targets = group["label"].to_numpy()
    predictions = group["prediction"].to_numpy()
    values = {
        "runs": len(group),
        "parents": group["parent_trajectory_id"].nunique(),
        "accuracy_or_recall": float(np.mean(targets == predictions)),
    }
    if len(np.unique(targets)) > 1:
        values["balanced_accuracy"] = float(balanced_accuracy_score(targets, predictions))
        values["macro_f1"] = float(f1_score(targets, predictions, average="macro"))
    return pd.Series(values)


def _parent_bootstrap(frame: pd.DataFrame, replicates: int, seed: int) -> dict:
    groups = {parent: group for parent, group in frame.groupby("parent_trajectory_id")}
    parents = np.asarray(sorted(groups))
    rng = np.random.default_rng(seed)
    balanced = np.empty(replicates)
    macro_f1 = np.empty(replicates)
    for index in range(replicates):
        sampled = rng.choice(parents, size=len(parents), replace=True)
        target = np.concatenate([groups[parent]["label"].to_numpy() for parent in sampled])
        prediction = np.concatenate([groups[parent]["prediction"].to_numpy() for parent in sampled])
        balanced[index] = balanced_accuracy_score(target, prediction)
        macro_f1[index] = f1_score(target, prediction, average="macro")
    return {
        "replicates": replicates,
        "cluster": "parent_trajectory_id",
        "balanced_accuracy_ci95": np.quantile(balanced, [0.025, 0.975]).tolist(),
        "macro_f1_ci95": np.quantile(macro_f1, [0.025, 0.975]).tolist(),
    }


def analyze(predictions_path: Path, index_path: Path, output: Path, bootstrap: int) -> None:
    predictions = pd.read_parquet(predictions_path)
    index = pd.read_parquet(index_path)
    if predictions["run_uid"].duplicated().any():
        raise ValueError("Predictions contain duplicate run_uid values")
    source_columns = [
        "run_uid", "dq2_rms_post", "s_LoE", "s_Friction", "A_d", "f_d",
        "trajectory_mode", "cohort", "split", "fault_class", "label", "parent_trajectory_id",
    ]
    source = index[[column for column in source_columns if column in index.columns]]
    replace = [column for column in source.columns if column != "run_uid" and column in predictions.columns]
    merged = predictions.drop(columns=replace).merge(source, on="run_uid", validate="one_to_one")
    if len(merged) != len(predictions):
        raise ValueError("Not every prediction matched exactly one canonical index row")
    output.mkdir(parents=True, exist_ok=True)

    primary_test = merged[
        (merged["cohort"] == "PRIMARY") & (merged["split"].astype(str).str.lower() == "test")
    ].copy()
    if not primary_test.empty:
        atomic_json(output / "e0_parent_bootstrap.json", _parent_bootstrap(primary_test, bootstrap, 20260913))
        primary_test.groupby("trajectory_mode", dropna=False).apply(_summary).reset_index().to_csv(
            output / "e3_mode.csv", index=False
        )

        severity_parts = []
        definitions = {
            "LoE": ("s_LoE", [0.02, 0.05, 0.10, 0.20, 0.3000001]),
            "Friction": ("s_Friction", [0.02, 0.10, 0.30, 0.75, 1.5000001]),
            "Vibration": ("A_d", [0.10, 0.50, 1.00, 1.75, 2.5000001]),
        }
        for fault_class, (column, bins) in definitions.items():
            subset = primary_test[primary_test["fault_class"] == fault_class].copy()
            subset["severity_bin"] = pd.cut(subset[column].astype(float), bins=bins, right=False)
            table = subset.groupby("severity_bin", observed=True).apply(_summary).reset_index()
            table.insert(0, "fault_class", fault_class)
            severity_parts.append(table)
        pd.concat(severity_parts, ignore_index=True).to_csv(output / "e1_severity.csv", index=False)

        vibration = primary_test[primary_test["fault_class"] == "Vibration"].copy()
        vibration["frequency_bin"] = pd.cut(
            vibration["f_d"].astype(float), [2, 5, 10, 15, 20, 25, 30.000001], right=False
        )
        vibration["amplitude_bin"] = pd.cut(
            vibration["A_d"].astype(float), [0.1, 0.5, 1.0, 1.75, 2.500001], right=False
        )
        vibration.groupby(["amplitude_bin", "frequency_bin"], observed=True).apply(
            _summary
        ).reset_index().to_csv(output / "e2a_vibration_grid.csv", index=False)

        train = index[
            (index["cohort"] == "PRIMARY") & (index["split"].astype(str).str.lower() == "train")
        ]
        if "dq2_rms_post" in train and train["dq2_rms_post"].notna().all():
            thresholds = train["dq2_rms_post"].quantile([0.25, 0.50, 0.75]).to_numpy()
            primary_test["excitation_quartile"] = pd.cut(
                primary_test["dq2_rms_post"].astype(float),
                bins=[-np.inf, *thresholds, np.inf], labels=["Q1", "Q2", "Q3", "Q4"],
            )
            primary_test.groupby("excitation_quartile", observed=True).apply(
                _summary
            ).reset_index().to_csv(output / "e3_excitation_quartiles.csv", index=False)
            atomic_json(output / "e3_train_quartile_thresholds.json", thresholds.tolist())

    e2b = merged[merged["cohort"] == "E2B"].copy()
    if not e2b.empty:
        e2b.groupby(["f_d", "trajectory_mode"], dropna=False).apply(_summary).reset_index().to_csv(
            output / "e2b_frequency.csv", index=False
        )

    e4 = merged[merged["cohort"] == "E4"].copy()
    if not e4.empty:
        candidates = (
            "e4_condition", "noise_condition", "velocity_snr_db", "snr_dq_db",
            "position_noise_std_rad", "sigma_q_rad", "position_noise_deg",
        )
        group_columns = [column for column in candidates if column in e4.columns]
        if not group_columns:
            raise ValueError(
                "E4 predictions are present but no recognized noise-condition metadata was indexed"
            )
        e4.groupby(group_columns, dropna=False).apply(_summary).reset_index().to_csv(
            output / "e4_noise_robustness.csv", index=False
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create E0/E1/E2/E3 tables from frozen predictions")
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--bootstrap", type=int, default=2000)
    args = parser.parse_args()
    analyze(args.predictions, args.index, args.output, args.bootstrap)
    print(f"ANALYSIS PASS: {args.output}")


if __name__ == "__main__":
    main()
