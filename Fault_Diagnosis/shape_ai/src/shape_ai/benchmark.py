from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd
import torch
from torch import nn

from .data import ShapeH5Dataset, load_index, make_loader
from .models import build_model
from .utils import atomic_json, environment_snapshot, seed_everything


def _parse_ints(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def benchmark_one(
    frame: pd.DataFrame,
    representation: str,
    batch_size: int,
    workers: int,
    warmup: int,
    steps: int,
    amp: str,
) -> dict:
    seed_everything(20260913, deterministic=False)
    dataset = ShapeH5Dataset(frame, representation)
    loader = make_loader(
        dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=workers,
        seed=20260913,
        pin_memory=True,
        persistent_workers=workers > 0,
        prefetch_factor=2,
        drop_last=True,
    )
    device = torch.device("cuda")
    model = build_model(representation).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=1e-4)
    criterion = nn.CrossEntropyLoss()
    amp_dtype = {"off": None, "fp16": torch.float16, "bf16": torch.bfloat16}[amp]
    scaler = torch.cuda.amp.GradScaler(enabled=amp_dtype == torch.float16)
    torch.cuda.reset_peak_memory_stats()

    iterator = iter(loader)
    measured_samples = 0
    start = None
    try:
        for step in range(warmup + steps):
            try:
                inputs, labels, _ = next(iterator)
            except StopIteration:
                iterator = iter(loader)
                inputs, labels, _ = next(iterator)
            inputs = inputs.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type="cuda", dtype=amp_dtype, enabled=amp_dtype is not None):
                loss = criterion(model(inputs), labels)
            if scaler.is_enabled():
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()
            else:
                loss.backward()
                optimizer.step()
            if step + 1 == warmup:
                torch.cuda.synchronize()
                start = time.perf_counter()
            elif step >= warmup:
                measured_samples += labels.shape[0]
        torch.cuda.synchronize()
        elapsed = time.perf_counter() - start
        return {
            "status": "PASS",
            "representation": representation,
            "batch_size": batch_size,
            "num_workers": workers,
            "amp": amp,
            "steps": steps,
            "samples": measured_samples,
            "elapsed_seconds": elapsed,
            "samples_per_second": measured_samples / elapsed,
            "peak_vram_gib": torch.cuda.max_memory_allocated() / (1024**3),
        }
    except torch.cuda.OutOfMemoryError as exc:
        return {
            "status": "OOM",
            "representation": representation,
            "batch_size": batch_size,
            "num_workers": workers,
            "amp": amp,
            "error": str(exc),
        }
    finally:
        del model, optimizer, loader
        torch.cuda.empty_cache()


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark HDF5-to-GPU training throughput")
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--representation", required=True)
    parser.add_argument("--batch-sizes", default="8,16,32,64")
    parser.add_argument("--workers", default="0,2,4,8")
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--amp", choices=("off", "fp16", "bf16"), default="fp16")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise SystemExit("A CUDA GPU is required for the performance benchmark")
    frame = load_index(args.index, cohort="PRIMARY", split="train")
    results = []
    for workers in _parse_ints(args.workers):
        for batch_size in _parse_ints(args.batch_sizes):
            result = benchmark_one(
                frame, args.representation, batch_size, workers, args.warmup, args.steps, args.amp
            )
            print(result)
            results.append(result)
    passed = [result for result in results if result["status"] == "PASS"]
    best = max(passed, key=lambda result: result["samples_per_second"]) if passed else None
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results).to_csv(args.output.with_suffix(".csv"), index=False)
    atomic_json(args.output, {"environment": environment_snapshot(), "results": results, "best": best})
    if best is None:
        raise SystemExit("BENCHMARK FAIL: no stable configuration")
    print(f"BENCHMARK PASS: best={best}")


if __name__ == "__main__":
    main()
