from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .contracts import CLASS_NAMES


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate evaluation metrics across frozen seeds")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-seeds", default="", help="Comma-separated seed set")
    args = parser.parse_args()
    expected = {int(item) for item in args.expected_seeds.split(",") if item.strip()}
    records = []
    for path in sorted(args.root.rglob("metrics.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        row = {
            "path": str(path.resolve()),
            "cohort": payload.get("cohort"),
            "split": payload.get("split"),
            "representation": payload.get("representation"),
            "seed": int(payload["seed"]),
            "accuracy": payload.get("accuracy"),
            "balanced_accuracy": payload.get("balanced_accuracy"),
            "macro_f1": payload.get("macro_f1"),
            "macro_roc_auc_ovr": payload.get("macro_roc_auc_ovr"),
            "nominal_false_alarm_rate": payload.get("nominal_false_alarm_rate"),
            "fault_missed_detection_rate": payload.get("fault_missed_detection_rate"),
        }
        for class_name in CLASS_NAMES:
            class_metrics = payload.get("per_class", {}).get(class_name, {})
            row[f"recall_{class_name.lower()}"] = class_metrics.get("recall")
            row[f"f1_{class_name.lower()}"] = class_metrics.get("f1")
        records.append(row)
    if not records:
        raise SystemExit(f"No metrics.json files found under {args.root}")
    frame = pd.DataFrame(records)
    key_columns = ["cohort", "split", "representation"]
    if frame.duplicated(key_columns + ["seed"]).any():
        raise SystemExit("Duplicate cohort/split/representation/seed metric records detected")
    if expected:
        for key, group in frame.groupby(key_columns, dropna=False):
            actual = set(group["seed"])
            if actual != expected:
                raise SystemExit(f"Seed set mismatch for {key}: {actual} != {expected}")
    metric_columns = [
        column for column in frame.columns
        if column not in {"path", "cohort", "split", "representation", "seed"}
    ]
    summary = frame.groupby(key_columns, dropna=False)[metric_columns].agg(["mean", "std", "min", "max"])
    summary.columns = [f"{metric}_{stat}" for metric, stat in summary.columns]
    summary = summary.reset_index()
    args.output.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output / "metrics_by_seed.csv", index=False)
    summary.to_csv(args.output / "metrics_across_seeds.csv", index=False)
    print(f"AGGREGATION PASS: {args.output}")


if __name__ == "__main__":
    main()
