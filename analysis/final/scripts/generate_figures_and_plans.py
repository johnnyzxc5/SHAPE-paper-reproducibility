"""Generate the thesis figure guide and workspace README from existing evidence.

The historical residual-benchmark planning document is preserved separately.
This generator does not create or propose a new experiment.
"""
from pathlib import Path

from e0_report_values import render_e0_tokens
from report_sync_values import render_sync_tokens


ROOT = Path(__file__).resolve().parents[1]


def build_thesis_figures_doc():
    figures = [
        ("E0 overall", "E0/E0_F01_overall_metrics.pdf", "Six-representation clean accuracy and seed SD; GMO [[E0_GMO_ACC]] ± [[E0_GMO_ACC_SD]]%, SHAPE [[E0_SHAPE_ACC]] ± [[E0_SHAPE_ACC_SD]]%, Torque [[E0_TORQUE_ACC]] ± [[E0_TORQUE_ACC_SD]]%."),
        ("E0 paired", "E0/E0_F06_pairwise_deltas.pdf", "Each point is the five-seed mean paired accuracy difference; each bar is its 95% paired parent-cluster bootstrap interval of that same mean (B=10,000, 750 parents, four siblings, RNG 20260927). SHAPE–Torque [[E0_ST_MEAN]] pp, CI [[E0_ST_LOW]] to [[E0_ST_HIGH]] pp."),
        ("E1 incipient LoE", "E1/E1_LoE_multiclass_recall_vs_severity.pdf", "Multiclass recall versus LoE severity. In [0.02,0.05), N=[[E1_LOE_SHAPE_N]] physical runs/seed, SHAPE [[E1_LOE_SHAPE_RECALL]]% and Torque [[E1_LOE_TORQUE_RECALL]]%; this is a descriptive difference."),
        ("E2-A exploratory grid", "E2A/E2A_diff_SHAPE_minus_Torque.pdf", "SHAPE minus Torque Vibration recall across 24 observational amplitude–frequency cells. At [0.1,0.5) N·m × [15,20) Hz, N=[[E2A_NOTCH_SHAPE_N]] physical runs/seed, SHAPE [[E2A_NOTCH_SHAPE_RECALL]]% and Torque [[E2A_NOTCH_TORQUE_RECALL]]%. No multiplicity correction or physical mechanism is implied."),
        ("E3 excitation", "E3/E3_metric_vs_excitation_quartile.pdf", "Accuracy and LoE recall stratified by post-fault measured joint-2 velocity RMS (`dq2_rms_post`), with boundaries fitted on PRIMARY/train. Q1 N=[[E3_Q1_EO_N]] and Q4 N=[[E3_Q4_EO_N]] runs/seed. Observational stratification."),
        ("E4 velocity perturbation", "E4/E4_velocity_robustness.pdf", "Accuracy across offline diagnostic-side velocity perturbations. The clean reference is a separate E0 evaluation pass. At 40 dB, SHAPE [[E4_V40_SHAPE_ACC]]%, GMO [[E4_V40_GMO_ACC]]%, Torque [[E4_V40_TORQUE_ACC]]%, EO [[E4_V40_EO_ACC]]%."),
        ("E4 clean reference delta", "E4/E4_clean_to_noise_deltas.pdf", "Perturbed E4 accuracy minus the separate E0 clean-pass accuracy. Torque predicted classes are identical across the ten E4 perturbation conditions, but the E0 clean pass differs from E4 on five Torque predictions; its delta from E0 is not exactly zero."),
        ("Structural and training scope", "COMPUTE/COMPUTE_performance_vs_training_cost.pdf", "Clean accuracy versus observed five-seed training wall-clock on an RTX 4090. This is a training-cost comparison, not a deployment or inference Pareto frontier; Level-2 residual runtime is NOT_MEASURED."),
    ]
    lines = ["# THESIS_MAIN_FIGURES — Evidence-linked figure guide", "", "Use the figure only for the population and estimand plotted. The list below prioritizes one panel per scientific question. E2-B can accompany E2-A as a controlled supporting panel.", "", "| Role | Existing figure | Scope-correct caption |", "|---|---|---|"]
    for role, rel, caption in figures:
        assert (ROOT / "figures" / rel).is_file(), rel
        lines.append(f"| {role} | `figures/{rel}` | {caption} |")
    lines += ["", "## Supporting figures and appendix", "", "- `figures/E2B/E2B_frequency_response.pdf`: controlled **classification recall versus frequency** at fixed 1.0 N·m. There are 30 physical parents, 300 physical runs and 6,000 canonical prediction rows across four CWT methods and five seeds. At 20 Hz, SHAPE's mean is [[E2B_F20_SHAPE_RECALL]]% with five-seed-mean parent-bootstrap CI [[E2B_F20_SHAPE_LOW]]–[[E2B_F20_SHAPE_HIGH]]%. The plotted error bars show seed SD, so do not describe them as bootstrap intervals.", "- `figures/E0/E0_F02_per_class_recall.pdf` and `figures/E0/E0_F04_binary_detection.pdf` show distinct multiclass and binary metrics. Friction is difficult for several CWT methods; no universal hardest class is claimed.", "- `figures/E3/E3_fly_stop.pdf` shows a descriptive T10 comparison without a significance test.", "- `figures/E4/E4_40dB_confusion_shape_cwt.pdf` and `figures/E4/E4_40dB_confusion_gmo_cwt.pdf` show a single plotted prediction population; captions must state the seed/population rather than attributing a single-seed percentage to all five seeds. The canonical 15,000-row predicted-class fractions are SHAPE Vibration [[E4_V40_SHAPE_PRED_VIB]]% and GMO Nominal [[E4_V40_GMO_PRED_NOM]]%.", "- `figures/COMPUTE/COMPUTE_performance_vs_throughput.pdf` and `figures/COMPUTE/COMPUTE_throughput.pdf` display measured PRIMARY/train **training-step** throughput only; Torque/GMO throughput and inference-only throughput are NOT_MEASURED.", "- `figures/CROSS_EXPERIMENT/CROSS_performance_profile_heatmap.pdf` presents raw measured dimensions from T19. Do not interpret it as an objective method ranking or proof that a hybrid method is required.", "", "E1/E3 numerical figures read T06/T09 and need no numerical regeneration for narrative synchronization. E0 and E2-B intervals belong to their explicitly named five-seed-mean estimands.", ""]
    content = render_sync_tokens(render_e0_tokens("\n".join(lines)))
    target = ROOT / "THESIS_MAIN_FIGURES.md"
    target.write_text(content, encoding="utf-8")
    print(f"Written {target}")


def build_readme_doc():
    figure_count = len(list((ROOT / "figures").rglob("*.pdf")))
    table_count = len(list((ROOT / "tables").glob("T*.csv")))
    content = f"""# Frozen thesis analysis workspace

This directory is the **analysis workspace** for Kinova Gen3 fault-diagnosis results. The scientific implementation is frozen at commit `5b4d09994fae40e2992d0e118cc9b31cd6cf90a1` in the separate source repository. The workspace contains canonical prediction tables, derived numerical tables, reports, figures and audit records; it is not itself a replacement for that source repository.

## Evidence and units

- PRIMARY: 5,000 parent trajectories × four physical siblings = **20,000 physical simulations** (Train 3,500/14,000; Val 750/3,000; Test 750/3,000).
- E2-B: 30 parents × ten physical frequency siblings = **300 additional physical simulations**. Only four CWT representations were evaluated across five model seeds: **6,000 canonical prediction rows**, 300 unique physical `run_uid` values.
- E1, E2-A and E3 are post-hoc analyses of PRIMARY Test; they add zero physical simulations or canonical predictions.
- E4 has ten offline diagnostic-side perturbations of retained PRIMARY Test trajectories: 30,000 perturbation views, **600,000 canonical prediction rows**, zero new physical simulations.
- Total: **20,300 physical simulations** and **696,000 canonical prediction rows** (90,000 E0 + 6,000 E2-B + 600,000 E4). These totals count different units and must not be conflated.

## Workspace contents

- `inputs/`: source artifact copies included in this workspace. Some referenced raw source archives or production artifacts may live outside this directory; consult `00_EVIDENCE_INVENTORY.md` before claiming that a package contains them.
- `derived/`: canonical prediction parquets; frozen for this documentation patch.
- `tables/`: {table_count} derived T-series CSV tables. T01 distinguishes physical simulations and prediction rows. T08 and T05 name the five-seed-mean parent-bootstrap intervals explicitly. T11 identifies the clean E0 reference separately from E4 perturbation rows.
- `figures/`: {figure_count} PDF figures, with PNG counterparts where produced. See `THESIS_MAIN_FIGURES.md` for scoped captions.
- `scripts/`: analysis and report generators. `scripts/p07_e2b_analysis.py` generates T08 and E2-B figures; `scripts/p09_e4_analysis.py` generates T11–T13 and E4 figures; `scripts/build_inventory.py` generates T01 and `00_EVIDENCE_INVENTORY.md`.
- `audit/`: provenance, corrections, hashes and scientific claim records. Historical Nico handoffs remain historical snapshots and are not current numerical authority.

## Reading order

1. `TRUSTED_CORE_RESULTS.md` for table-linked results.
2. `01_ANALYSIS_QUESTION_REGISTER.md` for scoped scientific questions.
3. `02_MASTER_RESULTS_REPORT.md` for experiment-level synthesis.
4. `03_COMPUTATIONAL_COST_REPORT.md` for measured and unmeasured compute stages.
5. `04_LIMITATIONS_AND_CLAIM_BOUNDARIES.md` and `05_KEY_FINDINGS.md` for claim boundaries.
6. `THESIS_MAIN_FIGURES.md` for the figure set.

All numerical claims should be checked against the canonical tables and the audit manifest. T15 measures training-step throughput, not inference-only speed; residual-generation runtime is NOT_MEASURED.
"""
    target = ROOT / "README.md"
    target.write_text(content, encoding="utf-8")
    print(f"Written {target}")


def build_benchmark_gap_doc():
    """Preserve the pre-existing historical planning document unchanged."""
    return ROOT / "RESIDUAL_BENCHMARK_GAP_AND_PLAN.md"


if __name__ == "__main__":
    build_thesis_figures_doc()
    build_readme_doc()
