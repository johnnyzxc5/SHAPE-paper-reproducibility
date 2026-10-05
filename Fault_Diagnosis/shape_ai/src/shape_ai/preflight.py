from __future__ import annotations

import argparse
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

from .contracts import REPRESENTATIONS, to_model_array
from .indexing import validate_index
from .utils import atomic_json, sha256_file


def run_preflight(index_path: Path, mode: str, samples: int) -> dict:
    frame = pd.read_parquet(index_path)
    report = validate_index(frame, mode)
    report["index_path"] = str(index_path.resolve())
    report["index_sha256"] = sha256_file(index_path)
    report["tensor_checks"] = []

    if len(frame):
        chosen = frame.sample(n=min(samples, len(frame)), random_state=20260913)
        for row in chosen.itertuples(index=False):
            with h5py.File(row.path, "r") as handle:
                for name, spec in REPRESENTATIONS.items():
                    array = np.asarray(handle[spec.dataset][:])
                    tensor = to_model_array(array, spec)
                    if tensor.shape != spec.tensor_shape or not np.isfinite(tensor).all():
                        report["pass"] = False
                        report["errors"].append(f"Invalid tensor {name} in {row.path}")
                report["tensor_checks"].append(str(row.run_uid))
    else:
        report["pass"] = False
        report["errors"].append("Index is empty")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate an existing SHAPE index and tensor contract")
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--mode", choices=("sample", "primary", "e2b", "full"), default="full")
    parser.add_argument("--samples", type=int, default=24)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    report = run_preflight(args.index, args.mode, args.samples)
    atomic_json(args.report, report)
    if not report["pass"]:
        raise SystemExit(f"PREFLIGHT FAIL: {report['errors']}; see {args.report}")
    print(f"PREFLIGHT PASS: {args.report}")


if __name__ == "__main__":
    main()
