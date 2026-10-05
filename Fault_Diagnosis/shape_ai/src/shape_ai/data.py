from __future__ import annotations

from pathlib import Path
from typing import Any

import h5py
import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset, Sampler

from .contracts import REPRESENTATIONS, RepresentationSpec, to_model_array
from .utils import seed_worker


class ShapeH5Dataset(Dataset):
    """Lazy, worker-safe reader: every item opens only its finalized HDF5 file."""

    def __init__(self, frame: pd.DataFrame, representation: str):
        if representation not in REPRESENTATIONS:
            raise KeyError(f"Unknown representation {representation!r}")
        required = {"path", "label", "run_uid", "parent_trajectory_id"}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"Index is missing columns: {sorted(missing)}")
        self.frame = frame.reset_index(drop=True).copy()
        self.spec: RepresentationSpec = REPRESENTATIONS[representation]

    def __len__(self) -> int:
        return len(self.frame)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor, int]:
        row = self.frame.iloc[index]
        with h5py.File(row["path"], "r") as handle:
            array = np.asarray(handle[self.spec.dataset][:])
        model_array = to_model_array(array, self.spec)
        tensor = torch.from_numpy(model_array)
        label = torch.tensor(int(row["label"]), dtype=torch.long)
        return tensor, label, index


def load_index(
    index_path: str | Path,
    *,
    cohort: str | None = None,
    split: str | None = None,
) -> pd.DataFrame:
    frame = pd.read_parquet(index_path)
    if cohort is not None:
        frame = frame[frame["cohort"].astype(str).str.upper() == cohort.upper()]
    if split is not None:
        frame = frame[frame["split"].astype(str).str.lower() == split.lower()]
    if frame.empty:
        raise ValueError(f"No records after filtering cohort={cohort!r}, split={split!r}")
    return frame.reset_index(drop=True)


def make_loader(
    dataset: Dataset,
    *,
    batch_size: int,
    shuffle: bool,
    num_workers: int,
    seed: int,
    pin_memory: bool,
    persistent_workers: bool,
    prefetch_factor: int,
    drop_last: bool = False,
    batch_sampler: Sampler[list[int]] | None = None,
) -> DataLoader:
    generator = torch.Generator()
    generator.manual_seed(seed)
    options: dict[str, Any] = {
        "dataset": dataset,
        "num_workers": num_workers,
        "pin_memory": pin_memory,
        "worker_init_fn": seed_worker,
        "generator": generator,
    }
    if batch_sampler is None:
        options.update(batch_size=batch_size, shuffle=shuffle, drop_last=drop_last)
    else:
        options["batch_sampler"] = batch_sampler
    if num_workers > 0:
        options["persistent_workers"] = persistent_workers
        options["prefetch_factor"] = prefetch_factor
    return DataLoader(**options)
