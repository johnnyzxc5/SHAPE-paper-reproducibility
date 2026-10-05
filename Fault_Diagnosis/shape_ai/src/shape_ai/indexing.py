from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any, Iterable

import h5py
import numpy as np
import pandas as pd
from tqdm import tqdm

from .contracts import (
    CLASS_NAMES,
    CLASS_TO_INDEX,
    CORE_DATASETS,
    canonical_class,
    decode_attr,
    manifest_from_attr,
)
from .utils import atomic_json


MANIFEST_FIELDS = (
    "split",
    "class_label",
    "target_joint",
    "fault_joint",
    "trajectory_mode",
    "K_segments",
    "t_fault",
    "s_LoE",
    "s_Friction",
    "A_d",
    "f_d",
    "phi_d",
    "analysis_stratum",
    "trajectory_seed",
    "parameter_seed",
    "fault_seed",
    "noise_seed",
)


def discover_h5(roots: Iterable[str | Path]) -> list[tuple[Path, str | None]]:
    files: list[tuple[Path, str | None]] = []
    for root_value in roots:
        text = str(root_value)
        cohort_override = None
        if "=" in text:
            candidate, text = text.split("=", 1)
            cohort_override = candidate.strip().upper()
        root = Path(text).expanduser().resolve()
        if not root.exists():
            raise FileNotFoundError(root)
        if root.is_file():
            if root.name.startswith("run_") and root.suffix.lower() == ".h5":
                files.append((root, cohort_override))
        else:
            files.extend((path, cohort_override) for path in root.rglob("run_*.h5"))
    unique_map: dict[Path, str | None] = {}
    for path, cohort in files:
        resolved = path.resolve()
        if resolved in unique_map and unique_map[resolved] != cohort:
            raise ValueError(f"The same HDF5 was assigned to multiple cohorts: {resolved}")
        unique_map[resolved] = cohort
    unique = sorted(unique_map.items(), key=lambda item: str(item[0]).lower())
    if not unique:
        raise FileNotFoundError("No run_*.h5 files found under the supplied roots")
    return unique


def _count_h5_objects(handle: h5py.File) -> tuple[int, int]:
    groups = 0
    datasets = 0

    def visitor(_: str, obj: Any) -> None:
        nonlocal groups, datasets
        if isinstance(obj, h5py.Group):
            groups += 1
        elif isinstance(obj, h5py.Dataset):
            datasets += 1

    handle.visititems(visitor)
    return groups, datasets


def _finite_scalar(value: Any) -> Any:
    value = decode_attr(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def inspect_run(
    path: Path, verify_core: bool, derive_dq2: bool, cohort_override: str | None = None
) -> dict[str, Any]:
    with h5py.File(path, "r") as handle:
        required_attrs = ("run_uid", "parent_trajectory_id", "fault_class", "manifest_record_json")
        missing_attrs = [name for name in required_attrs if name not in handle.attrs]
        if missing_attrs:
            raise ValueError(f"Missing root attributes {missing_attrs}")

        run_uid = str(decode_attr(handle.attrs["run_uid"]))
        parent_id = int(decode_attr(handle.attrs["parent_trajectory_id"]))
        fault_class = canonical_class(handle.attrs["fault_class"])
        manifest = manifest_from_attr(handle.attrs["manifest_record_json"])

        if str(manifest.get("run_uid")) != run_uid:
            raise ValueError("run_uid differs between root attribute and manifest_record_json")
        if int(manifest.get("parent_trajectory_id")) != parent_id:
            raise ValueError("parent_trajectory_id differs between root and manifest")
        if canonical_class(manifest.get("fault_class")) != fault_class:
            raise ValueError("fault_class differs between root and manifest")

        if verify_core:
            groups, datasets = _count_h5_objects(handle)
            if groups != 7 or datasets != 25:
                raise ValueError(f"Expected 7 groups and 25 datasets, found {groups} and {datasets}")
            if len(handle.attrs) != 40:
                raise ValueError(f"Expected 40 root attributes, found {len(handle.attrs)}")
            for dataset_name, (shape, dtype) in CORE_DATASETS.items():
                if dataset_name not in handle:
                    raise ValueError(f"Missing dataset {dataset_name}")
                dataset = handle[dataset_name]
                if tuple(dataset.shape) != shape:
                    raise ValueError(
                        f"{dataset_name}: shape {tuple(dataset.shape)} != expected {shape}"
                    )
                if str(dataset.dtype) != dtype:
                    raise ValueError(f"{dataset_name}: dtype {dataset.dtype} != expected {dtype}")

        record: dict[str, Any] = {
            "path": str(path),
            "run_uid": run_uid,
            "parent_trajectory_id": parent_id,
            "fault_class": fault_class,
            "label": CLASS_TO_INDEX[fault_class],
            "cohort": cohort_override or ("PRIMARY" if parent_id <= 5000 else "E2B"),
            "file_size_bytes": path.stat().st_size,
        }
        for field in MANIFEST_FIELDS:
            record[field] = _finite_scalar(manifest.get(field))
        # Preserve future E4/noise metadata without weakening the frozen required fields.
        for field, value in manifest.items():
            if field not in record and isinstance(value, (str, int, float, bool, type(None))):
                record[field] = value

        root_mode = decode_attr(handle.attrs.get("trajectory_mode", ""))
        if root_mode and str(record.get("trajectory_mode") or "") != str(root_mode):
            raise ValueError("trajectory_mode differs between root and manifest")

        if derive_dq2:
            t_fault = float(record["t_fault"])
            time = np.asarray(handle["/coordinates/telemetry_time_s"][:, 0], dtype=np.float64)
            dq2 = np.asarray(handle["/telemetry/dq_meas"][:, 1], dtype=np.float64)
            mask = time >= t_fault
            if not mask.any():
                raise ValueError(f"No post-fault samples for t_fault={t_fault}")
            record["dq2_rms_post"] = float(np.sqrt(np.mean(np.square(dq2[mask]))))
        else:
            record["dq2_rms_post"] = math.nan
        return record


def validate_index(frame: pd.DataFrame, mode: str) -> dict[str, Any]:
    errors: list[str] = []
    required_columns = {
        "path", "run_uid", "parent_trajectory_id", "fault_class", "label", "cohort", "split"
    }
    missing = sorted(required_columns - set(frame.columns))
    if missing:
        errors.append(f"Missing index columns: {missing}")
        return {"pass": False, "errors": errors}

    if frame["run_uid"].duplicated().any():
        errors.append(f"Duplicate run_uid values: {int(frame['run_uid'].duplicated().sum())}")
    if frame["path"].duplicated().any():
        errors.append(f"Duplicate paths: {int(frame['path'].duplicated().sum())}")
    if not set(frame["fault_class"]).issubset(set(CLASS_NAMES)):
        errors.append("Unknown fault classes are present")
    if not all(Path(path).is_file() for path in frame["path"]):
        errors.append("One or more indexed HDF5 paths do not exist")

    primary = frame[frame["cohort"] == "PRIMARY"]
    e2b = frame[frame["cohort"] == "E2B"]
    if not primary.empty:
        grouped = primary.groupby("parent_trajectory_id", sort=False)
        bad_counts = grouped.size()[lambda values: values != 4]
        if len(bad_counts):
            errors.append(f"PRIMARY parents without four siblings: {len(bad_counts)}")
        bad_classes = sum(set(group["fault_class"]) != set(CLASS_NAMES) for _, group in grouped)
        if bad_classes:
            errors.append(f"PRIMARY parents without the exact four-class set: {bad_classes}")
        parent_split_counts = grouped["split"].nunique()
        if (parent_split_counts != 1).any():
            errors.append("At least one PRIMARY parent crosses split boundaries")

    if not e2b.empty:
        expected_freq = {2.0, 5.0, 8.0, 11.0, 14.0, 17.0, 20.0, 23.0, 26.0, 30.0}
        grouped = e2b.groupby("parent_trajectory_id", sort=False)
        bad_counts = grouped.size()[lambda values: values != 10]
        if len(bad_counts):
            errors.append(f"E2B parents without ten siblings: {len(bad_counts)}")
        bad_freq = sum(set(map(float, group["f_d"])) != expected_freq for _, group in grouped)
        if bad_freq:
            errors.append(f"E2B parents without exact frequency grid: {bad_freq}")
        if set(e2b["fault_class"]) != {"Vibration"}:
            errors.append("E2B contains a non-Vibration class")

    if mode in {"primary", "full"}:
        if len(primary) != 20000 or primary["parent_trajectory_id"].nunique() != 5000:
            errors.append(
                f"PRIMARY count mismatch: {len(primary)} runs, "
                f"{primary['parent_trajectory_id'].nunique()} parents"
            )
        expected_splits = {"train": 14000, "val": 3000, "test": 3000}
        actual_splits = primary["split"].astype(str).str.lower().value_counts().to_dict()
        if actual_splits != expected_splits:
            errors.append(f"PRIMARY split counts {actual_splits} != {expected_splits}")
    if mode in {"e2b", "full"}:
        if len(e2b) != 300 or e2b["parent_trajectory_id"].nunique() != 30:
            errors.append(
                f"E2B count mismatch: {len(e2b)} runs, "
                f"{e2b['parent_trajectory_id'].nunique()} parents"
            )
        if set(e2b["parent_trajectory_id"].astype(int)) != set(range(5001, 5031)):
            errors.append("E2B parent IDs are not exactly 5001..5030")

    return {
        "pass": not errors,
        "errors": errors,
        "runs": int(len(frame)),
        "parents": int(frame["parent_trajectory_id"].nunique()),
        "primary_runs": int(len(primary)),
        "e2b_runs": int(len(e2b)),
        "class_counts": {str(k): int(v) for k, v in frame["fault_class"].value_counts().items()},
        "split_counts": {str(k): int(v) for k, v in frame["split"].value_counts().items()},
    }


def build_index(
    roots: list[str], output: Path, mode: str, verify_core: bool, derive_dq2: bool
) -> dict[str, Any]:
    files = discover_h5(roots)
    records: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for path, cohort_override in tqdm(files, desc="Inspecting HDF5", unit="file"):
        try:
            records.append(
                inspect_run(
                    path,
                    verify_core=verify_core,
                    derive_dq2=derive_dq2,
                    cohort_override=cohort_override,
                )
            )
        except Exception as exc:  # retain every corrupt path in the audit report
            failures.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})

    frame = pd.DataFrame.from_records(records)
    report = validate_index(frame, mode) if len(frame) else {"pass": False, "errors": ["No valid runs"]}
    if failures:
        report["pass"] = False
        report.setdefault("errors", []).append(f"Unreadable/invalid HDF5 files: {len(failures)}")
    report["file_failures"] = failures
    report["verify_core"] = verify_core
    report["derive_dq2"] = derive_dq2
    report_path = output.with_suffix(".audit.json")
    atomic_json(report_path, report)
    if not report["pass"]:
        raise RuntimeError(f"Index audit failed; see {report_path}")

    output.parent.mkdir(parents=True, exist_ok=True)
    frame.sort_values(["cohort", "parent_trajectory_id", "label", "f_d"], na_position="last").to_parquet(
        output, index=False
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and audit the canonical SHAPE HDF5 index")
    parser.add_argument(
        "--root", action="append", required=True,
        help="Data root; repeat as needed. Use E4=C:/path to override cohort identity.",
    )
    parser.add_argument("--output", required=True, type=Path, help="Output Parquet index")
    parser.add_argument("--mode", choices=("sample", "primary", "e2b", "full"), default="full")
    parser.add_argument("--verify-core", action="store_true", help="Check all 25 datasets and 40 attrs")
    parser.add_argument("--derive-dq2", action="store_true", help="Compute E3 post-fault velocity RMS")
    args = parser.parse_args()
    report = build_index(args.root, args.output, args.mode, args.verify_core, args.derive_dq2)
    print(f"PASS: indexed {report['runs']} runs into {args.output}")


if __name__ == "__main__":
    main()
