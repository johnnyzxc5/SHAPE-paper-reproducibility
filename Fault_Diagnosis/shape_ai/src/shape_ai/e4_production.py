"""Bounded MATLAB-authority E4 regeneration and frozen-checkpoint evaluation."""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

from .analysis import analyze
from .contracts import CLASS_NAMES
from .indexing import inspect_run
from .metrics import classification_metrics
from .utils import atomic_json, sha256_file


SEEDS = (1729, 2027, 4099, 7919, 104729)
REPRESENTATIONS = ("shape_cwt", "torque_cwt", "gmo_cwt", "energy_cwt")
CONDITIONS = (
    ("velocity_40dB", 40.0, 0.0),
    ("velocity_30dB", 30.0, 0.0),
    ("velocity_20dB", 20.0, 0.0),
    ("velocity_10dB", 10.0, 0.0),
    ("position_0.01deg", math.inf, 0.01),
    ("position_0.05deg", math.inf, 0.05),
    ("position_0.2deg", math.inf, 0.20),
    ("combined_40dB_0.01deg", 40.0, 0.01),
    ("combined_40dB_0.05deg", 40.0, 0.05),
    ("combined_40dB_0.2deg", 40.0, 0.20),
)
NAMESPACE = uuid.UUID("886b8c17-2a94-50db-9c10-d45479caea66")


def select_production(index_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    frame = pd.read_parquet(index_path)
    required = {"cohort", "split", "path", "run_uid", "noise_seed", "parent_trajectory_id", "fault_class"}
    if not required.issubset(frame):
        raise ValueError(f"Production index lacks {sorted(required - set(frame))}")
    primary = frame[frame.cohort.eq("PRIMARY")].copy()
    train = primary[primary.split.astype(str).str.lower().eq("train")].copy()
    test = primary[primary.split.astype(str).str.lower().eq("test")].copy()
    val = primary[primary.split.astype(str).str.lower().eq("val")]
    if len(primary) != 20000 or len(train) != 14000 or len(val) != 3000 or len(test) != 3000:
        raise ValueError("Expected 20,000 PRIMARY: 14,000 Train, 3,000 Val, 3,000 Test")
    if frame.run_uid.duplicated().any() or frame.path.duplicated().any():
        raise ValueError("Production index contains duplicate UID/path")
    if set(train.run_uid) & set(test.run_uid) or set(train.run_uid) & set(val.run_uid):
        raise ValueError("Calibration membership overlaps Val/Test")
    for part in (train, test):
        missing = [path for path in part.path if not Path(path).is_file()]
        if missing:
            raise FileNotFoundError(f"{len(missing)} indexed HDF5 files missing; first: {missing[0]}")
    return train.sort_values("run_uid").reset_index(drop=True), test.sort_values("run_uid").reset_index(drop=True), sha256_file(index_path)


def _matlab_call(matlab: str, code_dir: Path, expression: str) -> None:
    quoted = str(code_dir).replace("'", "''")
    subprocess.run([matlab, "-batch", f"addpath('{quoted}'); {expression};"], check=True)


class _MatlabStageSession:
    """Keep one MATLAB process pool alive while sequential chunks are evaluated."""

    def __init__(self, matlab: str, code_dir: Path, workers: int):
        self.matlab = matlab
        self.code_dir = code_dir
        self.workers = workers
        self.engine = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.engine is not None:
            self.engine.quit()
            self.engine = None

    def _start(self) -> None:
        executable = shutil.which(self.matlab)
        if executable is None:
            raise FileNotFoundError(f"MATLAB executable missing: {self.matlab}")
        distribution = Path(executable).resolve().parent.parent / "extern" / "engines" / "python" / "dist"
        if not (distribution / "matlab" / "engine").is_dir():
            raise FileNotFoundError(f"MATLAB Engine for Python missing: {distribution}")
        sys.path.insert(0, str(distribution))
        import matlab.engine

        process_start = time.perf_counter()
        self.engine = matlab.engine.start_matlab("-nodesktop -nosplash")
        process_seconds = time.perf_counter() - process_start
        self.engine.addpath(str(self.code_dir), nargout=0)
        client_threads = int(self.engine.maxNumCompThreads())
        if client_threads < 1:
            raise RuntimeError("MATLAB reported an invalid numerical thread count")
        pool_start = time.perf_counter()
        self.engine.eval(f"parpool('Processes',{self.workers});", nargout=0)
        pool_seconds = time.perf_counter() - pool_start
        thread_start = time.perf_counter()
        self.engine.eval(f"spmd, maxNumCompThreads({client_threads}); end;", nargout=0)
        thread_seconds = time.perf_counter() - thread_start
        print("E4_MATLAB_POOL_TIMING " + json.dumps(dict(
            workers=self.workers, process_startup_seconds=process_seconds,
            pool_startup_seconds=pool_seconds, client_numerical_threads=client_threads,
            worker_thread_setup_seconds=thread_seconds,
        )), flush=True)

    def stage(self, index_file: Path, calibration_path: Path) -> None:
        if self.workers == 0:
            _matlab_call(self.matlab, self.code_dir,
                         f"shape.production_e4_stage({_quote(index_file)},{_quote(calibration_path)})")
            return
        if self.engine is None:
            self._start()
        self.engine.eval(
            f"shape.production_e4_stage({_quote(index_file)},{_quote(calibration_path)},{self.workers});",
            nargout=0,
        )


def _quote(path: Path) -> str:
    return "'" + str(path.resolve()).replace("'", "''") + "'"


def verify_calibration(path: Path, index_path: Path, train: pd.DataFrame, index_sha: str) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if (value.get("state"), value.get("scope"), value.get("units")) != (
        "PRODUCTION_E4_CALIBRATION_FROZEN", "PRIMARY_TRAIN", "rad/s"
    ):
        raise ValueError("E4 calibration is not production-frozen PRIMARY Train in rad/s")
    if value.get("run_count") != 14000 or value.get("sample_count_per_joint") != 14000 * 10001:
        raise ValueError("E4 calibration counts conflict with production membership")
    if value.get("input_index_sha256") != index_sha or Path(value.get("input_index_path", "")).resolve() != index_path.resolve():
        raise ValueError("Frozen calibration index path/SHA differs from current index")
    rms = np.asarray(value.get("pooled_velocity_rms"), dtype=float).reshape(-1)
    if rms.shape != (6,) or not np.isfinite(rms).all() or (rms < 0).any():
        raise ValueError("Frozen calibration requires six finite nonnegative RMS values")
    # MATLAB aggregate_e4_calibration hashes sorted UIDs joined by newline, no trailing newline.
    import hashlib
    membership = hashlib.sha256("\n".join(sorted(train.run_uid.astype(str))).encode()).hexdigest()
    if value.get("run_uids_sha256") != membership:
        raise ValueError("Frozen calibration Train UID membership differs")
    return value


def stage_rows(test: pd.DataFrame, stage_dir: Path) -> pd.DataFrame:
    records = []
    for row in test.itertuples(index=False):
        for condition, snr, sigma in CONDITIONS:
            uid = str(uuid.uuid5(NAMESPACE, f"{row.run_uid}|{condition}"))
            record = row._asdict().copy()
            record.update(
                path=str(stage_dir / f"run_{uid}.h5"), clean_path=str(row.path),
                clean_run_uid=str(row.run_uid), run_uid=uid, cohort="E4", split="test",
                e4_condition=condition, velocity_snr_db=snr,
                position_sigma_deg=sigma, position_noise_std_rad=math.radians(sigma),
            )
            records.append(record)
    result = pd.DataFrame.from_records(records)
    if result.run_uid.duplicated().any() or len(result) != 10 * len(test):
        raise ValueError("E4 identity collision or condition count mismatch")
    return result


def _validate_stage(index: pd.DataFrame) -> None:
    for row in index.itertuples(index=False):
        path = Path(row.path)
        observed = inspect_run(path, verify_core=True, derive_dq2=False, cohort_override="E4")
        if observed["run_uid"] != row.run_uid or observed["e4_condition"] != row.e4_condition:
            raise ValueError(f"Staged E4 identity/condition mismatch: {path}")
        if observed["noise_seed"] != row.noise_seed:
            raise ValueError(f"Staged E4 noise seed mismatch: {path}")
        if observed["fault_class"] != row.fault_class or observed["parent_trajectory_id"] != row.parent_trajectory_id:
            raise ValueError(f"Staged E4 class/parent mismatch: {path}")


def _uid_sha(uids: pd.Series) -> str:
    return hashlib.sha256("\n".join(sorted(uids.astype(str))).encode()).hexdigest()


class _E4BatchSampler:
    """Retain the accepted four-clean-run batch boundaries within a larger stage."""

    def __init__(self, rows: int, batch_size: int):
        if rows < 1 or rows % 10 or batch_size < 1:
            raise ValueError("E4 batches require ten conditions per clean run")
        self.rows = rows
        self.batch_size = batch_size

    def __iter__(self):
        for group_start in range(0, self.rows, 40):
            group_end = min(group_start + 40, self.rows)
            for start in range(group_start, group_end, self.batch_size):
                yield list(range(start, min(start + self.batch_size, group_end)))

    def __len__(self) -> int:
        return sum(math.ceil(min(40, self.rows - start) / self.batch_size)
                   for start in range(0, self.rows, 40))


def _completed(
    output: Path, expected: int, checkpoint_sha: str, index_sha: str,
    *, calibration_sha: str | None = None, expected_uids: pd.Series | None = None,
    representation: str | None = None, seed: int | None = None,
) -> bool:
    if not output.exists():
        return False
    predictions = output / "predictions.parquet"
    metrics = output / "metrics.json"
    if not predictions.is_file() or not metrics.is_file():
        raise RuntimeError(f"Incomplete evaluation output needs operator review: {output}")
    receipt = json.loads(metrics.read_text(encoding="utf-8"))
    if receipt.get("checkpoint_sha256") != checkpoint_sha or receipt.get("index_sha256") != index_sha:
        raise RuntimeError(f"Existing E4 chunk has conflicting checkpoint/index provenance: {output}")
    frame = pd.read_parquet(predictions)
    if len(frame) != expected:
        raise RuntimeError(f"Existing E4 chunk prediction count mismatch: {output}")
    if calibration_sha is not None:
        receipt_path = output / "e4_bridge_receipt.json"
        if not receipt_path.is_file() or expected_uids is None or representation is None or seed is None:
            raise RuntimeError(f"Existing E4 chunk lacks complete bridge provenance: {output}")
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        expected_receipt = dict(
            checkpoint_sha256=checkpoint_sha, index_sha256=index_sha,
            calibration_sha256=calibration_sha, representation=representation,
            seed=seed, expected_rows=expected, run_uids_sha256=_uid_sha(expected_uids),
        )
        if any(receipt.get(key) != value for key, value in expected_receipt.items()):
            raise RuntimeError(f"Existing E4 chunk has conflicting bridge provenance: {output}")
        if ("run_uid" not in frame or frame.run_uid.duplicated().any()
                or _uid_sha(frame.run_uid) != expected_receipt["run_uids_sha256"]
                or "representation" not in frame or not frame.representation.eq(representation).all()
                or "seed" not in frame or not frame.seed.eq(seed).all()):
            raise RuntimeError(f"Existing E4 chunk prediction identity mismatch: {output}")
    return True


def _evaluate_pending(
    index_file: Path, chunk_index: pd.DataFrame, stage_dir: Path,
    pending: list[tuple[tuple[str, int], Path, str, Path]],
    args: argparse.Namespace, chunk_sha: str, calibration_sha: str,
) -> None:
    """Reuse one evaluator process and one DataLoader per representation."""
    from .data import ShapeH5Dataset, load_index, make_loader
    from .evaluate import evaluate

    frame = load_index(index_file, cohort="E4", split="test")
    for representation in REPRESENTATIONS:
        jobs = [job for job in pending if job[0][0] == representation]
        if not jobs:
            continue
        loader = make_loader(
            ShapeH5Dataset(frame, representation), batch_size=args.batch_size,
            shuffle=False, num_workers=args.workers, seed=jobs[0][0][1],
            pin_memory=True, persistent_workers=True, prefetch_factor=2,
            batch_sampler=_E4BatchSampler(len(frame), args.batch_size),
        )
        try:
            for (_, seed), checkpoint, checkpoint_sha, destination in jobs:
                temporary = stage_dir / f"eval_{representation}_{seed}"
                if temporary.exists():
                    raise RuntimeError(f"Incomplete E4 evaluation stage needs operator review: {temporary}")
                evaluate(
                    checkpoint, index_file, temporary, "E4", "test",
                    args.batch_size, args.workers, "fp16",
                    prepared_frame=frame, prepared_loader=loader,
                )
                if not _completed(temporary, len(chunk_index), checkpoint_sha, chunk_sha):
                    raise RuntimeError(f"E4 evaluation did not complete: {temporary}")
                atomic_json(temporary / "e4_bridge_receipt.json", dict(
                    checkpoint_sha256=checkpoint_sha, index_sha256=chunk_sha,
                    calibration_sha256=calibration_sha, representation=representation,
                    seed=seed, expected_rows=len(chunk_index),
                    run_uids_sha256=_uid_sha(chunk_index.run_uid),
                ))
                _completed(
                    temporary, len(chunk_index), checkpoint_sha, chunk_sha,
                    calibration_sha=calibration_sha, expected_uids=chunk_index.run_uid,
                    representation=representation, seed=seed,
                )
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists():
                    raise RuntimeError(f"E4 output appeared during evaluation: {destination}")
                os.replace(temporary, destination)
        finally:
            del loader
            gc.collect()


def _run_chunk_job(job_file: Path) -> None:
    job = json.loads(job_file.read_text(encoding="utf-8"))
    index_file = Path(job["index_file"])
    stage_dir = Path(job["stage_dir"])
    if sha256_file(index_file) != job["chunk_sha"]:
        raise RuntimeError("E4 evaluator job has a stale chunk index")
    if sha256_file(Path(job["calibration_path"])) != job["calibration_sha"]:
        raise RuntimeError("E4 evaluator job has a stale calibration")
    chunk_index = pd.read_parquet(index_file)
    _validate_stage(chunk_index)
    pending = []
    for item in job["checkpoints"]:
        key = (item["representation"], int(item["seed"]))
        checkpoint = Path(item["checkpoint"])
        digest = item["checkpoint_sha"]
        destination = Path(item["destination"])
        if sha256_file(checkpoint) != digest:
            raise RuntimeError(f"E4 evaluator job has a stale checkpoint: {checkpoint}")
        if not _completed(
            destination, len(chunk_index), digest, job["chunk_sha"],
            calibration_sha=job["calibration_sha"], expected_uids=chunk_index.run_uid,
            representation=key[0], seed=key[1],
        ):
            pending.append((key, checkpoint, digest, destination))
    if pending:
        args = argparse.Namespace(batch_size=int(job["batch_size"]), workers=int(job["workers"]))
        _evaluate_pending(index_file, chunk_index, stage_dir, pending, args,
                          job["chunk_sha"], job["calibration_sha"])
    print(f"E4 evaluator chunk PASS: {len(job['checkpoints'])} checkpoints; {len(chunk_index)} rows each")


def _write_json_once(payload: dict, destination: Path) -> None:
    if destination.exists():
        if json.loads(destination.read_text(encoding="utf-8")) != payload:
            raise RuntimeError(f"Existing E4 job conflicts: {destination}")
    else:
        atomic_json(destination, payload)


def _write_parquet_once(frame: pd.DataFrame, destination: Path) -> None:
    if destination.exists():
        old = pd.read_parquet(destination)
        if not old.equals(frame):
            raise RuntimeError(f"Existing E4 artifact conflicts: {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".parquet.tmp")
    if temporary.exists():
        raise RuntimeError(f"Incomplete temporary E4 artifact: {temporary}")
    frame.to_parquet(temporary, index=False)
    os.replace(temporary, destination)


def run(args: argparse.Namespace) -> None:
    run_start = time.perf_counter()
    index_path = args.index.resolve()
    train, test, index_sha = select_production(index_path)
    code_dir = Path(__file__).resolve().parents[4] / "Code_Image"
    calibration_path = args.calibration.resolve()
    if args.command == "calibrate":
        _matlab_call(args.matlab, code_dir,
                     f"shape.production_e4_calibrate({_quote(index_path)},{_quote(calibration_path)})")
    calibration = verify_calibration(calibration_path, index_path, train, index_sha)
    print(f"E4 calibration PASS: {calibration_path}; 14,000 PRIMARY Train records")
    if args.command != "evaluate":
        return
    if args.python.resolve() != Path(os.sys.executable).resolve():
        raise ValueError("Persistent E4 evaluation must use the running Python interpreter")
    calibration_sha = sha256_file(calibration_path)
    checkpoints = {}
    for representation in REPRESENTATIONS:
        for seed in SEEDS:
            path = args.run_root / representation / f"seed_{seed}" / "best.pt"
            if not path.is_file():
                raise FileNotFoundError(path)
            checkpoints[(representation, seed)] = (path, sha256_file(path))
    if args.smoke_runs:
        if args.smoke_runs < 1 or args.smoke_runs > 3000:
            raise ValueError("smoke-runs must be 1..3000")
        test = test.head(args.smoke_runs)
    if args.chunk_runs < 1:
        raise ValueError("chunk-runs must be positive")
    if args.matlab_workers < 0 or args.matlab_workers > 10:
        raise ValueError("matlab-workers must be 0..10 on this qualified host")
    if args.retain_smoke_stage and not args.smoke_runs:
        raise ValueError("Retaining E4 stage is allowed only for bounded smoke benchmarks")
    output_root = args.output_root.resolve()
    stage_root = args.stage_root.resolve()
    primary_root = Path(os.path.commonpath(test.path.astype(str).tolist())).resolve()
    for target in (output_root, stage_root):
        if target == primary_root or target in primary_root.parents or primary_root in target.parents:
            raise ValueError(f"E4 output/stage path must be separate from PRIMARY data: {target}")
        run_root = args.run_root.resolve()
        if target == run_root or target in run_root.parents or run_root in target.parents:
            raise ValueError(f"E4 output/stage path must be separate from frozen checkpoints: {target}")
    if output_root == stage_root or output_root in stage_root.parents or stage_root in output_root.parents:
        raise ValueError("Stage and output roots must be separate")
    with _MatlabStageSession(args.matlab, code_dir, args.matlab_workers) as matlab_stage:
        _evaluate_campaign(args, test, index_path, index_sha, calibration_path,
                           calibration_sha, checkpoints, output_root, stage_root,
                           matlab_stage, run_start)


def _evaluate_campaign(
    args: argparse.Namespace, test: pd.DataFrame, index_path: Path,
    index_sha: str, calibration_path: Path, calibration_sha: str,
    checkpoints: dict, output_root: Path, stage_root: Path,
    matlab_stage: _MatlabStageSession, run_start: float,
) -> None:
    all_indices = []
    for start in range(0, len(test), args.chunk_runs):
        chunk_start = time.perf_counter()
        matlab_seconds = 0.0
        inference_seconds = 0.0
        chunk_id = f"chunk_{start // args.chunk_runs:04d}"
        chunk_test = test.iloc[start:start + args.chunk_runs]
        stage_dir = stage_root / chunk_id
        chunk_index = stage_rows(chunk_test, stage_dir)
        all_indices.append(chunk_index.drop(columns=["path", "clean_path"]))
        index_file = output_root / "_chunks" / chunk_id / "index.parquet"
        _write_parquet_once(chunk_index, index_file)
        chunk_sha = sha256_file(index_file)
        pending = []
        all_jobs = []
        for key, (checkpoint, checkpoint_sha) in checkpoints.items():
            representation, seed = key
            destination = output_root / "_chunks" / chunk_id / representation / f"seed_{seed}"
            all_jobs.append(dict(
                representation=representation, seed=seed, checkpoint=str(checkpoint.resolve()),
                checkpoint_sha=checkpoint_sha, destination=str(destination),
            ))
            if not _completed(
                destination, len(chunk_index), checkpoint_sha, chunk_sha,
                calibration_sha=calibration_sha, expected_uids=chunk_index.run_uid,
                representation=representation, seed=seed,
            ):
                pending.append((key, checkpoint, checkpoint_sha, destination))
        if not pending:
            print(f"E4 resume: {chunk_id} already complete")
            continue
        if stage_dir.exists():
            existing = list(stage_dir.iterdir())
            expected_names = {Path(path).name for path in chunk_index.path}
            if stage_dir.parent != stage_root:
                raise RuntimeError("Unsafe E4 stage path")
            temporary_eval_names = {f"eval_{rep}_{seed}" for rep, seed in checkpoints}
            for path in existing:
                if path.is_dir() and path.name in temporary_eval_names:
                    shutil.rmtree(path)
            existing = list(stage_dir.iterdir())
            if existing and {path.name for path in existing} != expected_names:
                if stage_dir.parent != stage_root or not all(
                    path.is_file() and (path.name in expected_names or path.name.endswith(".h5.tmp"))
                    for path in existing
                ):
                    raise RuntimeError(f"Unexpected contents in E4 stage: {stage_dir}")
                shutil.rmtree(stage_dir)
                stage_dir.mkdir()
            elif existing:
                _validate_stage(chunk_index)
        else:
            stage_dir.mkdir(parents=True)
        if not all(Path(path).is_file() for path in chunk_index.path):
            if any(stage_dir.iterdir()):
                raise RuntimeError(f"Partial E4 stage needs operator review: {stage_dir}")
            matlab_start = time.perf_counter()
            matlab_stage.stage(index_file, calibration_path)
            matlab_seconds = time.perf_counter() - matlab_start
            if sha256_file(calibration_path) != calibration_sha:
                raise RuntimeError("E4 calibration changed during MATLAB staging")
        _validate_stage(chunk_index)
        peak_stage_bytes = sum(Path(path).stat().st_size for path in chunk_index.path)
        job_file = output_root / "_chunks" / chunk_id / "e4_eval_job.json"
        _write_json_once(dict(
            index_file=str(index_file), stage_dir=str(stage_dir), chunk_sha=chunk_sha,
            calibration_path=str(calibration_path), calibration_sha=calibration_sha,
            batch_size=args.batch_size, workers=args.workers, checkpoints=all_jobs,
        ), job_file)
        inference_start = time.perf_counter()
        subprocess.run([str(args.python), "-m", "shape_ai.e4_production", "evaluate-chunk",
                        "--job-file", str(job_file)], check=True)
        inference_seconds = time.perf_counter() - inference_start
        for (representation, seed), _, checkpoint_sha, destination in pending:
            if not _completed(
                destination, len(chunk_index), checkpoint_sha, chunk_sha,
                calibration_sha=calibration_sha, expected_uids=chunk_index.run_uid,
                representation=representation, seed=seed,
            ):
                raise RuntimeError(f"E4 evaluator did not complete: {representation}, seed {seed}")
        # Only this dedicated, exact chunk staging directory is disposable.
        if stage_dir.parent != stage_root:
            raise RuntimeError("Unsafe E4 stage deletion target")
        cleanup_start = time.perf_counter()
        if not args.retain_smoke_stage:
            shutil.rmtree(stage_dir)
        cleanup_seconds = time.perf_counter() - cleanup_start
        print(f"E4 chunk complete: {chunk_id}, {len(chunk_test)} clean Test runs")
        print("E4_TIMING " + json.dumps(dict(
            chunk=chunk_id, clean_runs=len(chunk_test), matlab_seconds=matlab_seconds,
            inference_seconds=inference_seconds, cleanup_seconds=cleanup_seconds,
            peak_stage_bytes=peak_stage_bytes,
            total_seconds=time.perf_counter() - chunk_start,
        )), flush=True)
    aggregation_start = time.perf_counter()
    final_index = pd.concat(all_indices, ignore_index=True)
    _write_parquet_once(final_index, output_root / "e4_index.parquet")
    for (representation, seed), (checkpoint, checkpoint_sha) in checkpoints.items():
        frames = [pd.read_parquet(output_root / "_chunks" / f"chunk_{i:04d}" /
                                  representation / f"seed_{seed}" / "predictions.parquet")
                  for i in range(len(all_indices))]
        predictions = pd.concat(frames, ignore_index=True)
        expected_uids = set(final_index.run_uid.astype(str))
        if (len(predictions) != 10 * len(test) or predictions.run_uid.duplicated().any()
                or set(predictions.run_uid.astype(str)) != expected_uids):
            raise ValueError("Final E4 prediction count/identity mismatch")
        destination = output_root / representation / f"seed_{seed}"
        _write_parquet_once(predictions, destination / "predictions.parquet")
        probs = predictions[[f"prob_{name.lower()}" for name in CLASS_NAMES]].to_numpy()
        metrics = classification_metrics(predictions.label.to_numpy(), predictions.prediction.to_numpy(), probs)
        metrics.update(representation=representation, seed=seed, cohort="E4", split="test",
                       checkpoint_sha256=checkpoint_sha, calibration_sha256=calibration_sha,
                       clean_index_sha256=index_sha, runs=len(predictions))
        metrics_path = destination / "metrics.json"
        if metrics_path.exists():
            old = json.loads(metrics_path.read_text(encoding="utf-8"))
            if old != metrics:
                raise RuntimeError(f"Existing E4 metrics conflict: {metrics_path}")
        else:
            atomic_json(metrics_path, metrics)
        robustness = destination / "analysis" / "e4_noise_robustness.csv"
        if robustness.exists():
            table = pd.read_csv(robustness)
            if (len(table) != 10 or set(table.e4_condition) != {name for name, _, _ in CONDITIONS}
                    or int(table.runs.sum()) != len(predictions)):
                raise RuntimeError(f"Existing E4 robustness table is incomplete: {robustness}")
        else:
            analyze(destination / "predictions.parquet", output_root / "e4_index.parquet",
                    destination / "analysis", bootstrap=0)
    if sha256_file(index_path) != index_sha or sha256_file(calibration_path) != calibration_sha:
        raise RuntimeError("Frozen E4 input index or calibration changed during evaluation")
    if any(sha256_file(path) != digest for path, digest in checkpoints.values()):
        raise RuntimeError("Frozen E4 checkpoint changed during evaluation")
    print("E4_AGGREGATION_TIMING " + json.dumps(dict(
        aggregation_seconds=time.perf_counter() - aggregation_start,
        total_seconds=time.perf_counter() - run_start,
    )), flush=True)
    print(f"E4 evaluation PASS: {len(test)} PRIMARY Test runs x 10 conditions; {output_root}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("calibrate", "verify", "evaluate", "evaluate-chunk"))
    parser.add_argument("--job-file", type=Path)
    parser.add_argument("--index", type=Path, default=Path(r"C:\KinovaProduction\AI\index\full_index.parquet"))
    parser.add_argument("--calibration", type=Path, default=Path(r"C:\KinovaProduction\AI\e4\production_e4_calibration.json"))
    parser.add_argument("--run-root", type=Path, default=Path(r"C:\KinovaProduction\AI\runs"))
    parser.add_argument("--output-root", type=Path, default=Path(r"C:\KinovaProduction\AI\evaluation\E4"))
    parser.add_argument("--stage-root", type=Path, default=Path(r"C:\KinovaProduction\AI\e4\stage"))
    parser.add_argument("--matlab", default="matlab")
    parser.add_argument("--python", type=Path, default=Path(os.sys.executable))
    parser.add_argument("--chunk-runs", type=int, default=4)
    parser.add_argument("--smoke-runs", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--matlab-workers", type=int, default=0,
                        help="MATLAB process workers for independent clean runs; separate from --workers")
    parser.add_argument("--retain-smoke-stage", action="store_true",
                        help="Keep bounded smoke staging for numerical equivalence checks")
    args = parser.parse_args()
    if args.command == "evaluate-chunk":
        if args.job_file is None:
            parser.error("evaluate-chunk requires --job-file")
        _run_chunk_job(args.job_file)
    else:
        run(args)


if __name__ == "__main__":
    main()
