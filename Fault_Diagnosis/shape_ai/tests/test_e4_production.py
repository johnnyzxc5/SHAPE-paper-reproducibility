from __future__ import annotations

import hashlib
import json
import sys
from argparse import Namespace
from pathlib import Path
from types import ModuleType

import h5py
import numpy as np
import pandas as pd
import pytest
import torch

from shape_ai.e4_production import (
    CONDITIONS, REPRESENTATIONS, SEEDS, _E4BatchSampler, _MatlabStageSession,
    _completed, _evaluate_pending,
    select_production, stage_rows, verify_calibration,
)
from shape_ai.data import ShapeH5Dataset, make_loader
from shape_ai.evaluate import evaluate
from shape_ai.models import build_model
from shape_ai.utils import sha256_file


def _index(tmp_path: Path) -> pd.DataFrame:
    rows = []
    for split, count in (("train", 14000), ("val", 3000), ("test", 3000)):
        for i in range(count):
            uid = f"{split}-{i}"
            rows.append(dict(cohort="PRIMARY", split=split, path=str(tmp_path / f"run_{uid}.h5"),
                             run_uid=uid, noise_seed=i + 1, parent_trajectory_id=i // 4 + 1,
                             fault_class="Nominal", label=0))
    return pd.DataFrame(rows)


def test_train_selection_and_production_count(tmp_path, monkeypatch):
    frame = _index(tmp_path)
    path = tmp_path / "index.parquet"
    frame.to_parquet(path, index=False)
    monkeypatch.setattr(Path, "is_file", lambda self: True)
    train, test, _ = select_production(path)
    assert len(train) == 14000 and len(test) == 3000
    assert set(train.split) == {"train"} and set(test.split) == {"test"}
    assert not set(train.run_uid) & set(test.run_uid)
    bad = frame[~frame.run_uid.eq("train-0")]
    bad.to_parquet(path, index=False)
    with pytest.raises(ValueError, match="14,000 Train"):
        select_production(path)


def test_frozen_calibration_membership_and_values(tmp_path):
    train = _index(tmp_path).query("split == 'train'")
    index = tmp_path / "index.parquet"
    index.write_bytes(b"index")
    digest = hashlib.sha256(index.read_bytes()).hexdigest()
    uids = hashlib.sha256("\n".join(sorted(train.run_uid)).encode()).hexdigest()
    artifact = tmp_path / "calibration.json"
    payload = dict(state="PRODUCTION_E4_CALIBRATION_FROZEN", scope="PRIMARY_TRAIN",
                   units="rad/s", run_count=14000, sample_count_per_joint=14000 * 10001,
                   input_index_sha256=digest, input_index_path=str(index),
                   pooled_velocity_rms=[0.1] * 6, run_uids_sha256=uids)
    artifact.write_text(json.dumps(payload))
    assert verify_calibration(artifact, index, train, digest) == payload
    assert verify_calibration(artifact, index, train, digest) == payload
    payload["run_uids_sha256"] = "wrong"
    artifact.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="membership"):
        verify_calibration(artifact, index, train, digest)
    payload["run_uids_sha256"] = uids
    payload["pooled_velocity_rms"][2] = np.nan
    artifact.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="six finite"):
        verify_calibration(artifact, index, train, digest)


def test_ten_conditions_and_deterministic_identity(tmp_path):
    test = _index(tmp_path).query("split == 'test'").head(1)
    first = stage_rows(test, tmp_path / "stage")
    second = stage_rows(test, tmp_path / "stage")
    pd.testing.assert_frame_equal(first, second)
    assert len(first) == 10
    assert first.e4_condition.tolist() == [item[0] for item in CONDITIONS]
    assert first.velocity_snr_db.tolist()[:4] == [40, 30, 20, 10]
    assert first.position_sigma_deg.tolist()[4:7] == [0.01, 0.05, 0.2]
    assert first.run_uid.is_unique
    assert first.clean_run_uid.nunique() == 1
    assert first.noise_seed.nunique() == 1


def test_clean_run_order_only_changes_stage_order(tmp_path):
    clean = _index(tmp_path).query("split == 'test'").head(3)
    forward = stage_rows(clean, tmp_path / "stage")
    reverse = stage_rows(clean.iloc[::-1], tmp_path / "stage")
    pd.testing.assert_frame_equal(
        forward.sort_values("run_uid").reset_index(drop=True),
        reverse.sort_values("run_uid").reset_index(drop=True),
        check_exact=True,
    )
    assert forward.groupby("clean_run_uid").size().eq(10).all()
    assert forward.path.is_unique
    assert forward.run_uid.is_unique


def test_matlab_process_pool_reused_and_closed(tmp_path, monkeypatch):
    class FakeEngine:
        def __init__(self):
            self.calls = []
            self.quits = 0

        def eval(self, expression, *, nargout):
            self.calls.append((expression, nargout))

        def quit(self):
            self.quits += 1

    engine = FakeEngine()
    starts = []
    session = _MatlabStageSession("matlab", tmp_path, 10)

    def start_once():
        starts.append(1)
        session.engine = engine

    monkeypatch.setattr(session, "_start", start_once)
    with session as active:
        active.stage(tmp_path / "chunk_0000.parquet", tmp_path / "calibration.json")
        active.stage(tmp_path / "chunk_0001.parquet", tmp_path / "calibration.json")
    assert len(starts) == 1
    assert len(engine.calls) == 2
    assert all("shape.production_e4_stage(" in call[0] and call[0].endswith(",10);")
               for call in engine.calls)
    assert engine.quits == 1


def test_matlab_workers_match_sequential_numerical_threads(tmp_path, monkeypatch):
    from shape_ai import e4_production

    executable = tmp_path / "MATLAB" / "bin" / "matlab.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"")
    (tmp_path / "MATLAB" / "extern" / "engines" / "python" / "dist" /
     "matlab" / "engine").mkdir(parents=True)
    monkeypatch.setattr(e4_production.shutil, "which", lambda _: str(executable))

    class FakeEngine:
        def __init__(self):
            self.commands = []
            self.closed = False

        def addpath(self, path, *, nargout):
            self.commands.append(("addpath", path))

        def maxNumCompThreads(self):
            return 24

        def eval(self, expression, *, nargout):
            self.commands.append(("eval", expression))

        def quit(self):
            self.closed = True

    engine = FakeEngine()
    matlab = ModuleType("matlab")
    matlab.__path__ = []
    matlab_engine = ModuleType("matlab.engine")
    matlab_engine.start_matlab = lambda _: engine
    matlab.engine = matlab_engine
    monkeypatch.setitem(sys.modules, "matlab", matlab)
    monkeypatch.setitem(sys.modules, "matlab.engine", matlab_engine)

    with _MatlabStageSession("matlab", tmp_path, 10) as session:
        session.stage(tmp_path / "chunk_0000.parquet", tmp_path / "calibration.json")
        session.stage(tmp_path / "chunk_0001.parquet", tmp_path / "calibration.json")
    commands = [value for kind, value in engine.commands if kind == "eval"]
    assert commands[:2] == ["parpool('Processes',10);",
                            "spmd, maxNumCompThreads(24); end;"]
    assert len(commands) == 4  # pool and thread setup happen once across chunks
    assert engine.closed


def test_matlab_pool_closes_after_staging_failure(tmp_path, monkeypatch):
    class FailingEngine:
        closed = False

        def eval(self, expression, *, nargout):
            raise RuntimeError("worker failed")

        def quit(self):
            self.closed = True

    engine = FailingEngine()
    session = _MatlabStageSession("matlab", tmp_path, 8)
    monkeypatch.setattr(session, "_start", lambda: setattr(session, "engine", engine))
    with pytest.raises(RuntimeError, match="worker failed"):
        with session as active:
            active.stage(tmp_path / "index.parquet", tmp_path / "calibration.json")
    assert engine.closed


def test_sequential_matlab_stage_still_uses_batch_launcher(tmp_path, monkeypatch):
    from shape_ai import e4_production

    calls = []
    monkeypatch.setattr(e4_production, "_matlab_call", lambda *a: calls.append(a))
    with _MatlabStageSession("matlab", tmp_path, 0) as session:
        session.stage(tmp_path / "index.parquet", tmp_path / "calibration.json")
    assert len(calls) == 1
    assert "shape.production_e4_stage(" in calls[0][2]


def test_parallel_stage_owns_unique_files_and_keeps_science_calls():
    repository = Path(__file__).resolve().parents[3]
    source = (repository / "Code_Image" / "+shape" / "production_e4_stage.m").read_text()
    assert "parfor run_i=1:run_count" in source
    assert "stage_clean_run(T(base:base+9,:)" in source
    assert "shape.offline_e4(clean,ref,models,cfg,double(rows.noise_seed(1)),calibration)" in source
    assert "shape.represent_e4_view(view,cfg)" in source
    assert "tmp=[path '.tmp']" in source and "movefile(tmp,path)" in source


def test_partial_worker_stage_is_removed_before_resume(tmp_path, monkeypatch):
    from shape_ai import e4_production

    clean = tmp_path / "primary" / "run_clean.h5"
    clean.parent.mkdir()
    clean.write_bytes(b"immutable PRIMARY fixture")
    clean_hash = sha256_file(clean)
    test = pd.DataFrame([dict(cohort="PRIMARY", split="test", path=str(clean),
                              run_uid="clean", noise_seed=17, parent_trajectory_id=1,
                              fault_class="Nominal", label=0)])
    index = tmp_path / "index.parquet"
    index.write_bytes(b"frozen index fixture")
    calibration = tmp_path / "calibration.json"
    calibration.write_text("{}")
    run_root = tmp_path / "runs"
    for representation in REPRESENTATIONS:
        for seed in SEEDS:
            checkpoint = run_root / representation / f"seed_{seed}" / "best.pt"
            checkpoint.parent.mkdir(parents=True)
            checkpoint.write_bytes(b"frozen checkpoint fixture")
    monkeypatch.setattr(e4_production, "select_production",
                        lambda _: (pd.DataFrame(), test, sha256_file(index)))
    monkeypatch.setattr(e4_production, "verify_calibration", lambda *a: {})
    stage_root = tmp_path / "stage"
    calls = []

    def fail_then_regenerate(self, index_file, calibration_path):
        paths = [Path(p) for p in pd.read_parquet(index_file).path]
        if not calls:
            paths[0].write_bytes(b"finished file before failure")
            Path(str(paths[1]) + ".tmp").write_bytes(b"incomplete worker file")
            calls.append("failed")
            raise RuntimeError("simulated MATLAB worker failure")
        assert not any(stage_root.rglob("*.h5"))
        assert not any(stage_root.rglob("*.tmp"))
        for path in paths:
            path.write_bytes(b"regenerated")
        calls.append("regenerated")
        raise RuntimeError("stop after regeneration fixture")

    monkeypatch.setattr(e4_production._MatlabStageSession, "stage", fail_then_regenerate)
    args = Namespace(command="evaluate", index=index, calibration=calibration,
                     run_root=run_root, output_root=tmp_path / "output",
                     stage_root=stage_root, matlab="matlab", python=Path(sys.executable),
                     chunk_runs=20, smoke_runs=1, workers=4, batch_size=32,
                     matlab_workers=8, retain_smoke_stage=False)
    with pytest.raises(RuntimeError, match="simulated MATLAB worker failure"):
        e4_production.run(args)
    assert len(list(stage_root.rglob("*.h5"))) == 1
    assert len(list(stage_root.rglob("*.tmp"))) == 1
    assert not list((tmp_path / "output").rglob("predictions.parquet"))
    with pytest.raises(RuntimeError, match="stop after regeneration fixture"):
        e4_production.run(args)
    assert calls == ["failed", "regenerated"]
    assert len(list(stage_root.rglob("*.h5"))) == 10
    assert not list(stage_root.rglob("*.tmp"))
    assert sha256_file(clean) == clean_hash


def test_resume_preserves_completed_prediction(tmp_path):
    folder = tmp_path / "done"
    folder.mkdir()
    pd.DataFrame({"run_uid": ["a", "b"]}).to_parquet(folder / "predictions.parquet")
    (folder / "metrics.json").write_text(json.dumps(dict(checkpoint_sha256="checkpoint",
                                                      index_sha256="index")))
    assert _completed(folder, 2, "checkpoint", "index")
    with pytest.raises(RuntimeError, match="conflicting"):
        _completed(folder, 2, "changed", "index")
    assert not _completed(tmp_path / "absent", 2, "checkpoint", "index")


def test_e4_bridge_excludes_simulation_and_training():
    repository = Path(__file__).resolve().parents[3]
    matlab = (repository / "Code_Image" / "+shape" / "production_e4_stage.m").read_text()
    python = (repository / "Fault_Diagnosis" / "shape_ai" / "src" / "shape_ai" /
              "e4_production.py").read_text()
    assert "sim(" not in matlab and "simulate_run" not in matlab
    assert "shape_ai.train" not in python and "torch.save" not in python
    assert "best.pt" in python and "from .evaluate import evaluate" in python


def test_reused_loader_matches_ordinary_evaluator(tmp_path):
    """The production call still executes the ordinary frozen forward pass and writer."""
    h5_path = tmp_path / "run.h5"
    with h5py.File(h5_path, "w") as handle:
        handle.create_dataset("/cwt/energy_log", data=np.zeros((448, 224, 1), dtype=np.float32))
    frame = pd.DataFrame([dict(path=str(h5_path), cohort="E4", split="test",
                               run_uid="one", parent_trajectory_id=1, label=0)])
    index = tmp_path / "index.parquet"
    frame.to_parquet(index, index=False)
    checkpoint = tmp_path / "best.pt"
    torch.save(dict(representation="energy_cwt", seed=1729, model_config={},
                    model_state=build_model("energy_cwt").state_dict()), checkpoint)
    original_hash = sha256_file(checkpoint)
    ordinary = tmp_path / "ordinary"
    reused = tmp_path / "reused"
    evaluate(checkpoint, index, ordinary, "E4", "test", 1, 0, "fp16")
    loader = make_loader(ShapeH5Dataset(frame, "energy_cwt"), batch_size=1,
                         shuffle=False, num_workers=0, seed=1729,
                         pin_memory=True, persistent_workers=True, prefetch_factor=2)
    evaluate(checkpoint, index, reused, "E4", "test", 1, 0, "fp16",
             prepared_frame=frame, prepared_loader=loader)
    pd.testing.assert_frame_equal(pd.read_parquet(ordinary / "predictions.parquet"),
                                  pd.read_parquet(reused / "predictions.parquet"), check_exact=True)
    assert json.loads((ordinary / "metrics.json").read_text()) == json.loads((reused / "metrics.json").read_text())
    assert sha256_file(checkpoint) == original_hash
    primary_index = tmp_path / "primary_index.parquet"
    frame.assign(cohort="PRIMARY").to_parquet(primary_index, index=False)
    evaluate(checkpoint, primary_index, tmp_path / "primary", "PRIMARY", "test", 1, 0, "fp16")
    assert len(pd.read_parquet(tmp_path / "primary" / "predictions.parquet")) == 1


def test_larger_stage_retains_accepted_batch_boundaries():
    batches = list(_E4BatchSampler(200, 32))
    assert len(batches) == 10
    assert [len(batch) for batch in batches] == [32, 8] * 5
    assert [item for batch in batches for item in batch] == list(range(200))
    assert [len(batch) for batch in _E4BatchSampler(500, 32)] == [32, 8] * 12 + [20]
    assert [len(batch) for batch in _E4BatchSampler(40, 64)] == [40]


def test_all_twenty_jobs_resume_and_fail_closed(tmp_path, monkeypatch):
    from shape_ai import data, evaluate as evaluation_module

    stage = tmp_path / "stage"
    stage.mkdir()
    staged = stage / "run_one.h5"
    staged.write_bytes(b"staged tensor marker")
    staged_hash = sha256_file(staged)
    frame = pd.DataFrame([dict(path=str(staged), cohort="E4", split="test", run_uid=f"one-{i}",
                               parent_trajectory_id=1, label=0) for i in range(10)])
    index = tmp_path / "index.parquet"
    frame.to_parquet(index, index=False)
    index_sha = sha256_file(index)
    calibration_sha = "calibration-sha"
    checkpoint_hashes = {}
    pending = []
    for representation in REPRESENTATIONS:
        for seed in SEEDS:
            checkpoint = tmp_path / "runs" / representation / f"seed_{seed}" / "best.pt"
            checkpoint.parent.mkdir(parents=True)
            checkpoint.write_bytes(f"{representation}|{seed}".encode())
            digest = sha256_file(checkpoint)
            checkpoint_hashes[checkpoint] = digest
            destination = tmp_path / "output" / representation / f"seed_{seed}"
            pending.append(((representation, seed), checkpoint, digest, destination))
    loader_calls = []
    monkeypatch.setattr(data, "make_loader", lambda *a, **kw: loader_calls.append(kw) or object())
    calls = []
    fail_once = [True]

    def fake_evaluate(checkpoint, index_path, output, cohort, split, batch_size, workers, amp,
                      *, prepared_frame, prepared_loader):
        if fail_once[0] and len(calls) == 7:
            fail_once[0] = False
            raise RuntimeError("simulated interruption")
        representation = checkpoint.parent.parent.name
        seed = int(checkpoint.parent.name.removeprefix("seed_"))
        calls.append((representation, seed, checkpoint, prepared_loader))
        result = prepared_frame.copy()
        result["representation"] = representation
        result["seed"] = seed
        result["prediction"] = 0
        output.mkdir()
        result.to_parquet(output / "predictions.parquet", index=False)
        (output / "metrics.json").write_text(json.dumps(dict(
            checkpoint_sha256=sha256_file(checkpoint), index_sha256=sha256_file(index_path))))

    monkeypatch.setattr(evaluation_module, "evaluate", fake_evaluate)
    args = Namespace(batch_size=32, workers=4)
    with pytest.raises(RuntimeError, match="simulated interruption"):
        _evaluate_pending(index, frame, stage, pending, args, index_sha, calibration_sha)
    assert len(calls) == 7
    remaining = []
    for key, checkpoint, digest, destination in pending:
        if not _completed(destination, 10, digest, index_sha, calibration_sha=calibration_sha,
                          expected_uids=frame.run_uid, representation=key[0], seed=key[1]):
            remaining.append((key, checkpoint, digest, destination))
    assert len(remaining) == 13
    _evaluate_pending(index, frame, stage, remaining, args, index_sha, calibration_sha)
    assert len(calls) == 20
    assert {item[:2] for item in calls} == {(representation, seed)
                                           for representation in REPRESENTATIONS for seed in SEEDS}
    assert len(loader_calls) == 5  # interrupted group is rebuilt once on resume
    assert sha256_file(staged) == staged_hash  # inference reused the same stage
    assert all(sha256_file(path) == digest for path, digest in checkpoint_hashes.items())
    assert all(_completed(destination, 10, digest, index_sha, calibration_sha=calibration_sha,
                          expected_uids=frame.run_uid, representation=key[0], seed=key[1])
               for key, _, digest, destination in pending)
    first_key, _, first_digest, first_destination = pending[0]
    with pytest.raises(RuntimeError, match="conflicting"):
        _completed(first_destination, 10, "stale", index_sha, calibration_sha=calibration_sha,
                   expected_uids=frame.run_uid, representation=first_key[0], seed=first_key[1])
    with pytest.raises(RuntimeError, match="conflicting"):
        _completed(first_destination, 10, first_digest, "stale", calibration_sha=calibration_sha,
                   expected_uids=frame.run_uid, representation=first_key[0], seed=first_key[1])
    with pytest.raises(RuntimeError, match="conflicting"):
        _completed(first_destination, 10, first_digest, index_sha, calibration_sha="stale",
                   expected_uids=frame.run_uid, representation=first_key[0], seed=first_key[1])
