"""Paired E0 inference for the mean effect across five frozen training seeds.

This module can regenerate T05 and E0_F06 without rerunning other E0 outputs.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score

ROOT = Path(__file__).resolve().parents[1]
SEEDS = (1729, 2027, 4099, 7919, 104729)
BOOTSTRAP_SEED = 20260927
BOOTSTRAP_REPLICATES = 10000
LEGACY_REPLICATES = 1000
PAIRS = (
    ("shape_cwt", "torque_cwt"),
    ("shape_cwt", "gmo_cwt"),
    ("shape_cwt", "energy_cwt"),
    ("gmo_cwt", "torque_cwt"),
    ("gmo_cwt", "energy_cwt"),
    ("torque_cwt", "energy_cwt"),
)
LABELS = {
    "shape_cwt": "SHAPE-CWT", "torque_cwt": "Torque-CWT",
    "gmo_cwt": "GMO-CWT", "energy_cwt": "EO-CWT",
}


def compute_pairwise_table(df):
    """Use one paired parent draw per replicate for every method and seed."""
    base = df[(df.representation == "shape_cwt") & (df.seed == SEEDS[0])].set_index("run_uid")
    if not base.index.is_unique or len(base) != 3000:
        raise ValueError("Expected 3000 distinct PRIMARY test run_uids")
    parents = pd.Index(base.parent_trajectory_id.drop_duplicates())
    if len(parents) != 750 or not (base.groupby("parent_trajectory_id").size() == 4).all():
        raise ValueError("Expected exactly 750 parent clusters of four siblings")
    if not (base.groupby("parent_trajectory_id").label.nunique() == 4).all():
        raise ValueError("Each parent must contain one run of every class")
    parent_index = parents.get_indexer(base.parent_trajectory_id)

    # Every cell refers to the same physical run_uid; a seed only changes predictions.
    correct = {}
    macro_f1 = {}
    for method in LABELS:
        for seed in SEEDS:
            sub = df[(df.representation == method) & (df.seed == seed)].set_index("run_uid")
            if not sub.index.is_unique or len(sub) != 3000 or not sub.index.isin(base.index).all():
                raise ValueError(f"Physical run mismatch: {method}, {seed}")
            sub = sub.reindex(base.index)
            if not sub.label.equals(base.label) or not sub.parent_trajectory_id.equals(base.parent_trajectory_id):
                raise ValueError(f"Label or parent mismatch: {method}, {seed}")
            correct[method, seed] = (sub.prediction.to_numpy() == base.label.to_numpy()).astype(np.int8)
            macro_f1[method, seed] = f1_score(base.label, sub.prediction, average="macro")

    # One sampled sequence of 750 parent IDs is reused for both methods and all five seeds.
    draws = np.random.default_rng(BOOTSTRAP_SEED).integers(
        0, len(parents), size=(BOOTSTRAP_REPLICATES, len(parents)), dtype=np.int16
    )
    legacy_rng = np.random.default_rng(BOOTSTRAP_SEED)
    records = []
    for method_1, method_2 in PAIRS:
        accuracy_deltas = []
        f1_deltas = []
        per_parent = []
        for seed in SEEDS:
            run_delta = correct[method_1, seed].astype(np.int16) - correct[method_2, seed]
            accuracy_deltas.append(float(run_delta.mean()))
            f1_deltas.append(float(macro_f1[method_1, seed] - macro_f1[method_2, seed]))
            # Sum the four siblings before drawing a parent, preserving the cluster.
            per_parent.append(np.bincount(parent_index, weights=run_delta, minlength=750) / 4.0)
        parent_by_seed = np.stack(per_parent)
        five_seed_parent_mean = parent_by_seed.mean(axis=0)
        boot = five_seed_parent_mean[draws].mean(axis=1)
        low, high = np.quantile(boot, (0.025, 0.975))

        # Retain the old, correctly computed conditional interval only under explicit names.
        legacy_draws = legacy_rng.integers(0, 750, size=(LEGACY_REPLICATES, 750))
        old_boot = parent_by_seed[0, legacy_draws].mean(axis=1)
        old_low, old_high = np.quantile(old_boot, (0.025, 0.975))
        records.append({
            "Comparison": f"{LABELS[method_1]} - {LABELS[method_2]}",
            "Method_1": LABELS[method_1], "Method_2": LABELS[method_2],
            "Delta_Accuracy_Mean": float(np.mean(accuracy_deltas)),
            "Delta_Accuracy_SD": float(np.std(accuracy_deltas, ddof=1)),
            "Seed_Delta_Accuracy_Min": float(np.min(accuracy_deltas)),
            "Seed_Delta_Accuracy_Max": float(np.max(accuracy_deltas)),
            "Delta_Macro_F1_Mean": float(np.mean(f1_deltas)),
            "Delta_Macro_F1_SD": float(np.std(f1_deltas, ddof=1)),
            "Seed_Delta_Macro_F1_Min": float(np.min(f1_deltas)),
            "Seed_Delta_Macro_F1_Max": float(np.max(f1_deltas)),
            "ParentClusterBootstrap_CI95_of_FiveSeedMean_Lower": float(low),
            "ParentClusterBootstrap_CI95_of_FiveSeedMean_Upper": float(high),
            "ParentClusterBootstrap_Resamples": BOOTSTRAP_REPLICATES,
            "ParentClusterBootstrap_RNGSeed": BOOTSTRAP_SEED,
            "Seed1729_ParentBootstrap_CI95_Lower": float(old_low),
            "Seed1729_ParentBootstrap_CI95_Upper": float(old_high),
            "Seed1729_ParentBootstrap_Resamples": LEGACY_REPLICATES,
        })
    return pd.DataFrame(records)


def plot_pairwise_figure(table):
    point = table.Delta_Accuracy_Mean.to_numpy() * 100
    low = table.ParentClusterBootstrap_CI95_of_FiveSeedMean_Lower.to_numpy() * 100
    high = table.ParentClusterBootstrap_CI95_of_FiveSeedMean_Upper.to_numpy() * 100
    if np.any(low > point) or np.any(high < point):
        raise ValueError("A five-seed mean lies outside its paired parent bootstrap interval")
    fig, ax = plt.subplots(figsize=(10, 5))
    y = np.arange(len(table))
    ax.errorbar(point, y, xerr=np.vstack((point - low, high - point)), fmt="o",
                color="#1f77b4", ecolor="black", elinewidth=2, capsize=5, markersize=8)
    ax.axvline(0, color="red", linestyle="--", linewidth=1.5)
    ax.set_yticks(y)
    ax.set_yticklabels(table.Comparison, fontsize=11, fontweight="bold")
    ax.set_xlabel("Five-seed mean paired Accuracy delta (percentage points)\n"
                  "95% paired parent-cluster bootstrap CI of that mean (B=10,000)")
    ax.set_title("E0 paired differences on the PRIMARY test set")
    ax.grid(axis="x", linestyle="--", alpha=0.5)
    fig.tight_layout()
    out = ROOT / "figures" / "E0"
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / "E0_F06_pairwise_deltas.png", dpi=300)
    fig.savefig(out / "E0_F06_pairwise_deltas.pdf")
    plt.close(fig)


def regenerate_pairwise_only():
    cols = ["representation", "seed", "run_uid", "parent_trajectory_id", "label", "prediction"]
    df = pd.read_parquet(ROOT / "derived" / "canonical_e0_primary.parquet", columns=cols)
    table = compute_pairwise_table(df)
    table.to_csv(ROOT / "tables" / "T05_E0_pairwise_deltas.csv", index=False)
    plot_pairwise_figure(table)
    return table


if __name__ == "__main__":
    print(regenerate_pairwise_only().to_string(index=False))
