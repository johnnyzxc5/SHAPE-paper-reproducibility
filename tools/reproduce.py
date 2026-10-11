"""Plan a new, isolated reproduction; scientific steps require --execute.

Planning/prepare uses only the Python standard library and never starts MATLAB,
imports torch, reads simulation HDF5, trains, or installs dependencies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REPS = ("shape_cwt", "torque_cwt", "gmo_cwt", "energy_cwt", "shape_temporal", "shape_fft")
SEEDS = (1729, 2027, 4099, 7919, 104729)
STEPS = ("inputs", "qualify", "simulate", "index", "train", "evaluate", "calibrate", "e4", "tables")
MARKER = ".shape-reproduction.json"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_payload() -> None:
    for line in (ROOT / "provenance/SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file() or sha(path) != expected:
            raise RuntimeError(f"Packaged source changed or missing: {relative}")


def records():
    for rep in REPS:
        for seed in SEEDS:
            path = ROOT / "metadata/AI/runs" / rep / f"seed_{seed}" / "config.resolved.json"
            record = json.loads(path.read_text(encoding="utf-8"))
            if record["representation"] != rep or record["seed"] != seed:
                raise ValueError(f"Configuration identity mismatch: {path}")
            yield rep, seed, record


def validate_work(work: Path) -> None:
    # Source, outputs and generated Simulink caches must have separate roots.
    if work == Path(work.anchor) or work.is_relative_to(ROOT) or ROOT.is_relative_to(work):
        raise ValueError("Work root must be a dedicated directory outside the repository")
    if work.exists() and not (work / MARKER).is_file() and any(work.iterdir()):
        raise ValueError("Refusing an existing nonempty directory without a reproduction marker")
    if (work / MARKER).is_file():
        owner = json.loads((work / MARKER).read_text(encoding="utf-8"))
        if owner.get("repository_root") != str(ROOT) or owner.get("work_root") != str(work):
            raise ValueError("Work directory belongs to another reproduction")


def config_path(work: Path, rep: str, seed: int) -> Path:
    return work / "configs" / f"{rep}_{seed}.json"


def prepare(work: Path) -> None:
    validate_work(work)
    work.mkdir(parents=True, exist_ok=True)
    marker = work / MARKER
    if not marker.exists():
        marker.write_text(json.dumps(dict(schema_version="shape-reproduction-v1",
            repository_root=str(ROOT), work_root=str(work)), indent=2) + "\n", encoding="utf-8")
    for rep, seed, original in records():
        adapted = dict(original, index_path=str(work / "AI/index/full_index.parquet"),
                       output_root=str(work / "AI/runs"))
        path = config_path(work, rep, seed)
        if path.exists():
            if json.loads(path.read_text(encoding="utf-8")) != adapted:
                raise ValueError(f"Existing config conflicts; refusing overwrite: {path}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(adapted, indent=2) + "\n", encoding="utf-8")


def matlab_text(value: Path | str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def commands(step: str, work: Path, python: str, matlab: str) -> list[list[str]]:
    index = work / "AI/index/full_index.parquet"
    runs = work / "AI/runs"
    calibration = work / "AI/e4/calibration.json"
    if step in ("inputs", "qualify", "simulate"):
        code = (f"addpath({matlab_text(ROOT / 'Code_Image')}); "
                f"run_reproduction('Stage',{matlab_text(step.upper())},"
                f"'WorkRoot',{matlab_text(work)},'Arm','I_REQUEST_THIS_REPRODUCTION_STAGE');")
        return [[matlab, "-batch", code]]
    if step == "index":
        return [[python, "-m", "shape_ai.indexing", "--root", str(work / "outputs/PRIMARY"),
                 "--root", str(work / "outputs/E2B"), "--output", str(index),
                 "--mode", "full", "--verify-core", "--derive-dq2"]]
    if step == "train":
        return [[python, "-m", "shape_ai.train", "--config", str(config_path(work, rep, seed))]
                for rep, seed, _ in records()]
    if step == "evaluate":
        result = []
        for rep, seed, _ in records():
            for cohort, split in (("PRIMARY", "test"), ("E2B", "none")):
                if cohort == "E2B" and rep not in REPS[:4]:
                    continue
                result.append([python, "-m", "shape_ai.evaluate", "--checkpoint",
                    str(runs / rep / f"seed_{seed}" / "best.pt"), "--index", str(index),
                    "--output", str(work / "AI/evaluation" / cohort / rep / f"seed_{seed}"),
                    "--cohort", cohort, "--split", split,
                    "--batch-size", "32", "--num-workers", "4", "--amp", "fp16"])
        return result
    if step in ("calibrate", "e4"):
        return [[python, "-m", "shape_ai.e4_production",
                 "calibrate" if step == "calibrate" else "evaluate", "--index", str(index),
                 "--calibration", str(calibration), "--run-root", str(runs),
                 "--output-root", str(work / "AI/evaluation/E4"),
                 "--stage-root", str(work / "AI/e4/stage"), "--matlab", matlab,
                 "--chunk-runs", "4", "--batch-size", "32", "--workers", "4",
                 "--matlab-workers", "0"]]
    if step == "tables":
        return [[python, str(ROOT / "tools/reproduce_tables.py"), "--work-root", str(work), "--execute"]]
    raise ValueError(step)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("plan",) + STEPS, nargs="?", default="plan")
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--matlab", default="matlab")
    parser.add_argument("--prepare", action="store_true", help="Write 30 path-adapted configs only")
    parser.add_argument("--execute", action="store_true", help="Explicitly execute this one scientific stage")
    args = parser.parse_args()
    work = args.work_root.resolve()
    validate_work(work)
    verify_payload()
    if args.step == "plan" and args.execute:
        parser.error("Choose one stage; there is no execute-all command")
    stages = STEPS if args.step == "plan" else (args.step,)
    plan = {step: commands(step, work, args.python, args.matlab) for step in stages}
    if args.prepare:
        prepare(work)
        (work / "command_plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    if not args.execute:
        print(json.dumps(dict(status="PLAN_ONLY", work_root=str(work),
                              configs_prepared=args.prepare, commands=plan), indent=2))
        return
    if not (work / MARKER).exists():
        parser.error("Prepare the work directory first with plan --prepare")
    env = os.environ.copy()
    # Use this checkout even when the selected Python has another editable checkout installed.
    source = ROOT / "Fault_Diagnosis/shape_ai/src"
    env["PYTHONPATH"] = str(source) + os.pathsep + env.get("PYTHONPATH", "")
    env["MPLBACKEND"] = "Agg"
    for command in plan[args.step]:
        subprocess.run(command, check=True, cwd=ROOT, env=env)


if __name__ == "__main__":
    main()
