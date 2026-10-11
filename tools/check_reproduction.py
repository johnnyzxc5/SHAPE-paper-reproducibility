"""Static reproducibility audit: metadata, source closure and installed versions only.

Never calls MATLAB, imports torch, generates trajectories, simulates or trains.
"""
import argparse
import ast
import importlib.metadata as packages
import json
from pathlib import Path
import re
import sys

from reproduce import ROOT, REPS, SEEDS, records, verify_payload
from reproduce_tables import ANALYSIS_SCRIPTS, adapted_source


def audit(check_environment=False):
    verify_payload()
    configs = list(records())
    assert len(configs) == 30
    batch_sizes = dict(shape_cwt=32, torque_cwt=32, gmo_cwt=32, energy_cwt=64,
                       shape_temporal=16, shape_fft=64)
    for rep, seed, config in configs:
        assert config["training"]["batch_size"] == batch_sizes[rep]
        assert config["deterministic"] and not config["allow_cpu"]
        assert config["training"]["epochs"] == 50
    code = ROOT / "Code_Image"
    missing = []
    # Check package calls as text, including the E4 bridge and generator.
    for path in [*code.rglob("*.m"), *ROOT.joinpath("docs").rglob("*.m")]:
        for name in set(re.findall(r"\bshape\.([A-Za-z]\w*)\s*\(", path.read_text(encoding="utf-8-sig"))):
            if not (code / "+shape" / f"{name}.m").is_file():
                missing.append(f"{path.relative_to(ROOT)} -> shape.{name}")
    if missing:
        raise ValueError("Missing MATLAB package dependencies: " + "; ".join(missing))
    for name in ANALYSIS_SCRIPTS:
        ast.parse(adapted_source(name))
    for name in ("train", "evaluate", "indexing", "e4_production", "analysis"):
        ast.parse((ROOT / "Fault_Diagnosis/shape_ai/src/shape_ai" / f"{name}.py").read_text(encoding="utf-8"))
    signatures = json.loads((ROOT / "metadata/simulation/qualified_pilot_signatures.json").read_text())
    assert len(signatures["cases"]) == 2
    assert all(len(case["datasets"]) == 25 for case in signatures["cases"])
    result = dict(status="STATIC_SOURCE_AUDIT_PASS", training_configs=30,
                  seeds=list(SEEDS), representations=list(REPS),
                  matlab_package_dependencies="present", adapted_analysis_scripts=len(ANALYSIS_SCRIPTS),
                  simulations_executed=0, training_runs_executed=0,
                  trajectory_regeneration="NOT_RUN", scientific_equivalence="NOT_RUN")
    if check_environment:
        mismatches = []
        for line in (ROOT / "requirements/reproduction-win64-py312.lock").read_text().splitlines():
            if not line or line.startswith("#"):
                continue
            name, version = line.split("==")
            try:
                installed = packages.version(name)
            except packages.PackageNotFoundError:
                installed = "MISSING"
            if installed != version:
                mismatches.append(dict(package=name, expected=version, observed=installed))
        if sys.version_info[:2] != (3, 12) or sys.platform != "win32":
            mismatches.append(dict(platform=sys.platform, python=sys.version,
                                   expected="Windows x64 / Python 3.12"))
        result["environment_version_mismatches"] = mismatches
        result["environment_status"] = "VERSION_PROFILE_MATCH" if not mismatches else "VERSION_PROFILE_MISMATCH"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", action="store_true")
    args = parser.parse_args()
    result = audit(args.environment)
    print(json.dumps(result, indent=2))
    if result.get("environment_version_mismatches"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
