import json
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

from shape_ai.data import ShapeH5Dataset
from shape_ai.indexing import inspect_run, validate_index


def _write_run(path: Path, uid: str, fault_class: str, class_label: int) -> None:
    manifest = {
        "run_uid": uid,
        "parent_trajectory_id": 1,
        "split": "train",
        "fault_class": fault_class,
        "class_label": class_label,
        "target_joint": 2,
        "fault_joint": 2,
        "trajectory_mode": "fly",
        "K_segments": 2,
        "t_fault": 3.0,
        "s_LoE": 0.0,
        "s_Friction": 0.0,
        "A_d": 0.0,
        "f_d": 0.0,
        "phi_d": 0.0,
        "analysis_stratum": "test",
        "trajectory_seed": 1,
        "parameter_seed": 2,
        "fault_seed": 3,
        "noise_seed": 4,
    }
    with h5py.File(path, "w") as handle:
        handle.attrs["run_uid"] = uid
        handle.attrs["parent_trajectory_id"] = 1
        handle.attrs["fault_class"] = fault_class
        handle.attrs["trajectory_mode"] = "fly"
        handle.attrs["manifest_record_json"] = json.dumps(manifest)
        handle.create_dataset("/cwt/shape_log", data=np.zeros((448, 224, 6), dtype=np.float32))


def test_index_and_lazy_dataset(tmp_path):
    classes = ("Nominal", "LoE", "Friction", "Vibration")
    rows = []
    for label, fault_class in enumerate(classes):
        path = tmp_path / f"run_{label}.h5"
        _write_run(path, f"uid-{label}", fault_class, label)
        rows.append(inspect_run(path, verify_core=False, derive_dq2=False))
    frame = pd.DataFrame(rows)
    assert validate_index(frame, "sample")["pass"]
    dataset = ShapeH5Dataset(frame, "shape_cwt")
    tensor, label, row_index = dataset[2]
    assert tensor.shape == (6, 224, 448)
    assert int(label) == 2
    assert row_index == 2
