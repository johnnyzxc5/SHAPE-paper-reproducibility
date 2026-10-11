"""Adapt preserved E0-E4 analysis to newly generated predictions.

Default is a source/dependency plan only. --execute explicitly aggregates new
predictions, runs the preserved analysis calculations and writes new tables/plots.
It never simulates or trains, and never writes into frozen evidence.
"""
import argparse
import ast
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from reproduce import ROOT, REPS, SEEDS, MARKER, sha, validate_work, verify_payload

ANALYSIS_SCRIPTS = (
    "p03_build_canonical_datasets.py", "p04_e0_analysis.py", "p05_e1_analysis.py",
    "p06_e2a_analysis.py", "p07_e2b_analysis.py", "p08_e3_analysis.py", "p09_e4_analysis.py",
)
HISTORICAL_ROOT = 'ROOT = Path(r"C:\\Users\\Johnny\\Desktop\\KINOVA_FINAL_ANALYSIS_ANTIGRAVITY")'


def adapted_source(name):
    text = (ROOT / "analysis/final/scripts" / name).read_text(encoding="utf-8")
    if text.count(HISTORICAL_ROOT) != 1:
        raise ValueError(f"Unexpected analysis path contract: {name}")
    result = text.replace(HISTORICAL_ROOT, "ROOT = Path(__file__).resolve().parents[1]")
    if "C:\\Users\\Johnny" in result:
        raise ValueError(f"Unadapted historical path in {name}")
    ast.parse(result)
    return result


def joint_tables(canonical, destination):
    """Same physical denominators and seed-then-mean/SD used in the joint audit."""
    import pandas as pd
    frame = pd.read_parquet(canonical)
    frame = frame[frame.fault_class.isin(["LoE", "Friction", "Vibration"]) &
                  frame.representation.isin(REPS[:4])].copy()
    if len(frame) != 45000 or frame.duplicated(["run_uid", "representation", "seed"]).any():
        raise ValueError("Incomplete faulty PRIMARY/test CWT prediction population")
    if set(frame.seed) != set(SEEDS) or not frame.groupby("run_uid").size().eq(20).all():
        raise ValueError("Each physical run must have four CWT methods x five seeds")
    group = ["fault_class", "severity_bin", "excitation_quartile", "representation"]
    if frame[group].isna().any().any() or frame.severity_bin.eq("N/A").any():
        raise ValueError("Missing joint strata")
    aggregations = dict(N_unique_runs=("run_uid", "nunique"),
                        Recall=("is_correct_multiclass", "mean"),
                        Detection=("is_correct_binary", "mean"))
    for label, name in enumerate(["Nominal", "LoE", "Friction", "Vibration"]):
        frame[f"Fraction_{name}"] = (frame.prediction == label).astype(float)
        aggregations[f"Fraction_{name}"] = (f"Fraction_{name}", "mean")
    by_seed = frame.groupby(group + ["seed"], observed=True).agg(**aggregations).reset_index()
    if not by_seed.groupby(group, observed=True).N_unique_runs.nunique().eq(1).all():
        raise ValueError("Physical cell denominators differ across seeds")
    metrics = ["Recall", "Detection", "Fraction_Nominal", "Fraction_LoE", "Fraction_Friction", "Fraction_Vibration"]
    summary_agg = dict(N_unique_runs=("N_unique_runs", "first"), Seeds=("seed", "nunique"))
    for metric in metrics:
        summary_agg[metric + "_Mean"] = (metric, "mean")
        summary_agg[metric + "_SD"] = (metric, "std")
    summary = by_seed.groupby(group, observed=True).agg(**summary_agg).reset_index()
    if not summary.Seeds.eq(5).all():
        raise ValueError("Joint cell missing a training seed")
    destination.mkdir(parents=True, exist_ok=False)
    by_seed.to_csv(destination / "joint_metrics_by_seed.csv", index=False, float_format="%.17g")
    summary.to_csv(destination / "joint_severity_excitation.csv", index=False, float_format="%.17g")


def execute(work):
    import pandas as pd
    analysis = work / "analysis"
    if analysis.exists():
        raise FileExistsError("Analysis already exists; inspect it before choosing a new output/work root")
    # Validate every expected prediction before creating the analysis destination.
    copies = []
    for cohort, label in (("PRIMARY", "primary_zip/E0_PRIMARY"),
                          ("E2B", "primary_zip/E2B_FREQUENCY"), ("E4", "e4_zip")):
        for rep in REPS if cohort == "PRIMARY" else REPS[:4]:
            for seed in SEEDS:
                source = work / "AI/evaluation" / cohort / rep / f"seed_{seed}/predictions.parquet"
                if not source.is_file():
                    raise FileNotFoundError(source)
                copies.append((source, analysis / "inputs" / label / rep / f"seed_{seed}/predictions.parquet"))
    index_path = work / "AI/index/full_index.parquet"
    index = pd.read_parquet(index_path)
    train = index[(index.cohort == "PRIMARY") & index.split.eq("train")]
    if len(train) != 14000 or train.run_uid.nunique() != 14000 or train.dq2_rms_post.isna().any():
        raise ValueError("E3 thresholds require 14,000 unique newly indexed PRIMARY/train runs")
    thresholds = train.dq2_rms_post.quantile([.25, .5, .75]).tolist()
    (analysis / "scripts").mkdir(parents=True)
    (analysis / "tables").mkdir()
    for source, destination in copies:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    threshold_path = analysis / "inputs/primary_zip/E3_EXCITATION_MODE/shape_cwt_seed_1729_e3_train_quartile_thresholds.json"
    threshold_path.parent.mkdir(parents=True)
    threshold_path.write_text(json.dumps(thresholds) + "\n", encoding="utf-8")
    adaptations = []
    for name in ANALYSIS_SCRIPTS:
        destination = analysis / "scripts" / name
        destination.write_text(adapted_source(name), encoding="utf-8")
        adaptations.append(dict(file=name, source_sha256=sha(ROOT / "analysis/final/scripts" / name),
                                adapted_sha256=sha(destination), change="ROOT resolves relative to copied script"))
    shutil.copy2(ROOT / "analysis/final/scripts/e0_pairwise_stats.py", analysis / "scripts/e0_pairwise_stats.py")
    env = dict(os.environ, MPLBACKEND="Agg")
    for name in ANALYSIS_SCRIPTS:
        subprocess.run([sys.executable, str(analysis / "scripts" / name)], check=True, env=env, cwd=analysis)
    joint_tables(analysis / "derived/canonical_e0_primary.parquet", analysis / "joint")
    (analysis / "reproduction_provenance.json").write_text(json.dumps(dict(
        input_index_sha256=sha(index_path), train_thresholds=thresholds,
        scripts=adaptations, source_predictions=[dict(path=str(p), sha256=sha(p)) for p, _ in copies],
        scope="E0-E4 scientific tables/figures and joint numerical summaries; no simulation or training"), indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    work = args.work_root.resolve()
    validate_work(work)
    verify_payload()
    for name in ANALYSIS_SCRIPTS:
        adapted_source(name)
    if args.execute:
        if not (work / MARKER).is_file():
            parser.error("Prepare this dedicated work root first")
        execute(work)
    else:
        print(json.dumps(dict(status="PLAN_ONLY", scripts=ANALYSIS_SCRIPTS,
                              destination=str(work / "analysis")), indent=2))


if __name__ == "__main__":
    main()
