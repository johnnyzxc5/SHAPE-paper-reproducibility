import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

ROOT = Path(r"C:\Users\Johnny\Desktop\KINOVA_FINAL_ANALYSIS_ANTIGRAVITY")
DERIVED_DIR = ROOT / "derived"
TABLES_DIR = ROOT / "tables"
FIGURES_DIR = ROOT / "figures" / "E2B"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300

METHOD_COLORS = {
    "shape_cwt": "#1f77b4",       # blue
    "torque_cwt": "#ff7f0e",      # orange
    "gmo_cwt": "#2ca02c",         # green
    "energy_cwt": "#d62728",      # red
}

METHOD_LABELS = {
    "shape_cwt": "SHAPE-CWT",
    "torque_cwt": "Torque-CWT",
    "gmo_cwt": "GMO-CWT",
    "energy_cwt": "EO-CWT",
}

FREQUENCIES = [2.0, 5.0, 8.0, 11.0, 14.0, 17.0, 20.0, 23.0, 26.0, 30.0]

def analyze_e2b():
    print("--- Running E2-B Controlled Frequency Sweep Analysis ---")
    df = pd.read_parquet(DERIVED_DIR / "canonical_e2b.parquet")
    
    reps = ["shape_cwt", "torque_cwt", "gmo_cwt", "energy_cwt"]
    seeds = [1729, 2027, 4099, 7919, 104729]
    
    # 1. Build Table T08_E2B_frequency.csv
    # Aggregated by frequency and overall / by mode
    t08_records = []
    
    # One paired parent draw matrix is reused for every method and frequency.
    unique_parents = np.array(sorted(df["parent_trajectory_id"].unique()))
    assert len(unique_parents) == 30
    B = 10000
    bootstrap_rng = 20260927
    draw_indices = np.random.default_rng(bootstrap_rng).integers(0, 30, size=(B, 30))
    # Reproduce the historical seed-1729 intervals with their original
    # sequential RNG stream. These are retained only under explicit names.
    legacy_rng = np.random.default_rng(20260927)
    
    for f in FREQUENCIES:
        frequency_run_uids = None
        for r in reps:
            recalls = []
            pred_dist = {"Nominal": [], "LoE": [], "Friction": [], "Vibration": []}
            seed_correctness = []
            common_run_uids = None
            
            for s in seeds:
                sub = df[(df["representation"] == r) & (df["seed"] == s) & (df["f_d"] == f)]
                sub = sub.sort_values("parent_trajectory_id")
                assert len(sub) == 30 and np.array_equal(sub["parent_trajectory_id"].to_numpy(), unique_parents)
                run_uids = sub["run_uid"].to_numpy()
                if common_run_uids is None:
                    common_run_uids = run_uids
                else:
                    assert np.array_equal(common_run_uids, run_uids), f"Seed pairing differs: {r}, {f}, {s}"
                if frequency_run_uids is None:
                    frequency_run_uids = run_uids
                else:
                    assert np.array_equal(frequency_run_uids, run_uids), f"Method pairing differs: {r}, {f}, {s}"
                # True class is always Vibration (label=3)
                assert (sub["label"] == 3).all()
                rec = (sub["prediction"] == 3).mean()
                recalls.append(rec)
                seed_correctness.append((sub["prediction"].to_numpy() == 3).astype(float))
                
                for c in ["Nominal", "LoE", "Friction", "Vibration"]:
                    pred_dist[c].append((sub["prediction_class"] == c).mean())
                    
            # CI of the five-seed mean: each replicate resamples the same 30
            # physical parents for all five seeds. One run per parent/frequency.
            correctness = np.stack(seed_correctness)
            five_seed_replicates = correctness[:, draw_indices].mean(axis=(0, 2))
            ci_low, ci_upp = np.quantile(five_seed_replicates, [0.025, 0.975])

            # Historical conditional CI: seed 1729 only, B=1000.
            sub_ref = df[(df["representation"] == r) & (df["seed"] == 1729) & (df["f_d"] == f)]
            parent_groups = {p: g["prediction"].to_numpy() for p, g in sub_ref.groupby("parent_trajectory_id")}
            boot_recalls = []
            for _ in range(1000):
                sampled_p = legacy_rng.choice(unique_parents, size=len(unique_parents), replace=True)
                preds = np.concatenate([parent_groups[p] for p in sampled_p])
                boot_recalls.append(np.mean(preds == 3))
            legacy_low, legacy_upp = np.quantile(boot_recalls, [0.025, 0.975])
            
            t08_records.append({
                "Frequency_Hz": f,
                "Representation": METHOD_LABELS[r],
                "rep_key": r,
                "Vibration_Recall_Mean": np.mean(recalls),
                "Vibration_Recall_SD": np.std(recalls, ddof=1),
                "ParentClusterBootstrap_CI95_of_FiveSeedMean_Lower": float(ci_low),
                "ParentClusterBootstrap_CI95_of_FiveSeedMean_Upper": float(ci_upp),
                "Bootstrap_B": B,
                "Bootstrap_RNG": bootstrap_rng,
                "Seed1729_ParentBootstrap_CI95_Lower": float(legacy_low),
                "Seed1729_ParentBootstrap_CI95_Upper": float(legacy_upp),
                "Seed1729_Bootstrap_B": 1000,
                "Pred_Vibration_Mean": np.mean(pred_dist["Vibration"]),
                "Pred_Nominal_Mean": np.mean(pred_dist["Nominal"]),
                "Pred_LoE_Mean": np.mean(pred_dist["LoE"]),
                "Pred_Friction_Mean": np.mean(pred_dist["Friction"])
            })
            
    df_t08 = pd.DataFrame(t08_records)
    df_t08.to_csv(TABLES_DIR / "T08_E2B_frequency.csv", index=False)
    print("Saved tables/T08_E2B_frequency.csv")
    
    # 2. Figures
    print("Generating E2-B Figures...")
    
    # Figure 1: Frequency Response (Recall vs Frequency)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))
    
    # Left: Overall frequency response across representations
    for r in reps:
        sub = df_t08[df_t08["rep_key"] == r].sort_values("Frequency_Hz")
        ax1.plot(sub["Frequency_Hz"], sub["Vibration_Recall_Mean"] * 100, marker='o', linewidth=2.5, label=METHOD_LABELS[r], color=METHOD_COLORS[r])
        # fill error bands (SD across seeds)
        y_low = (sub["Vibration_Recall_Mean"] - sub["Vibration_Recall_SD"]) * 100
        y_upp = (sub["Vibration_Recall_Mean"] + sub["Vibration_Recall_SD"]) * 100
        ax1.fill_between(sub["Frequency_Hz"], y_low, y_upp, color=METHOD_COLORS[r], alpha=0.15)
        
    ax1.set_xlabel('Vibration Frequency (Hz)', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Vibration Recall / Accuracy (%)', fontsize=12, fontweight='bold')
    ax1.set_title('E2-B Classification Recall vs Frequency (Fixed Ad = 1.0 N*m, N=30 parents)', fontsize=12, fontweight='bold')
    ax1.set_xticks(FREQUENCIES)
    ax1.set_ylim(80, 102)
    ax1.grid(True, linestyle='--', alpha=0.5)
    ax1.legend(loc='lower left', frameon=True)
    
    # Right: Fly vs Stop response comparison
    for r in ["shape_cwt", "torque_cwt"]:
        for mode, ls in [("fly", "-"), ("stop", "--")]:
            mode_recalls = []
            for f in FREQUENCIES:
                sub_mode = df[(df["representation"] == r) & (df["f_d"] == f) & (df["trajectory_mode"] == mode)]
                mode_recalls.append((sub_mode["prediction"] == 3).mean() * 100)
            ax2.plot(FREQUENCIES, mode_recalls, marker='s' if mode=='fly' else '^', linestyle=ls, linewidth=2,
                     label=f"{METHOD_LABELS[r]} ({mode.upper()})", color=METHOD_COLORS[r])
            
    ax2.set_xlabel('Vibration Frequency (Hz)', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Vibration Recall (%)', fontsize=12, fontweight='bold')
    ax2.set_title('E2-B Mode Interaction: Fly vs Stop (SHAPE vs Torque)', fontsize=12, fontweight='bold')
    ax2.set_xticks(FREQUENCIES)
    ax2.set_ylim(80, 102)
    ax2.grid(True, linestyle='--', alpha=0.5)
    ax2.legend(loc='lower left', frameon=True)
    
    fig.suptitle('E2-B Controlled Frequency Sweep Analysis', fontsize=14, fontweight='bold')
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "E2B_frequency_response.png")
    fig.savefig(FIGURES_DIR / "E2B_frequency_response.pdf")
    plt.close(fig)
    
    # Figure 2: Predicted Class Distribution across frequency (Stacked Bars)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharey=True, sharex=True)
    class_palette = {
        "Vibration": "#2ca02c",  # correct
        "Nominal": "#1f77b4",    # missed
        "LoE": "#ff7f0e",        # confused
        "Friction": "#d62728"    # confused
    }
    
    for idx, r in enumerate(reps):
        ax = axes[idx // 2, idx % 2]
        sub = df_t08[df_t08["rep_key"] == r].sort_values("Frequency_Hz")
        
        vib_pct = sub["Pred_Vibration_Mean"] * 100
        nom_pct = sub["Pred_Nominal_Mean"] * 100
        loe_pct = sub["Pred_LoE_Mean"] * 100
        fric_pct = sub["Pred_Friction_Mean"] * 100
        
        x = np.arange(len(FREQUENCIES))
        ax.bar(x, vib_pct, label='Vibration (Correct)', color=class_palette["Vibration"], alpha=0.85, edgecolor='black')
        ax.bar(x, nom_pct, bottom=vib_pct, label='Nominal (Missed)', color=class_palette["Nominal"], alpha=0.85, edgecolor='black')
        ax.bar(x, loe_pct, bottom=vib_pct+nom_pct, label='LoE (Confused)', color=class_palette["LoE"], alpha=0.85, edgecolor='black')
        ax.bar(x, fric_pct, bottom=vib_pct+nom_pct+loe_pct, label='Friction (Confused)', color=class_palette["Friction"], alpha=0.85, edgecolor='black')
        
        ax.set_title(METHOD_LABELS[r], fontsize=11, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels([f"{int(f)}" for f in FREQUENCIES])
        ax.set_ylim(80, 102)
        ax.grid(axis='y', linestyle='--', alpha=0.5)
        if idx % 2 == 0:
            ax.set_ylabel('Prediction Distribution (%)', fontsize=10)
        if idx // 2 == 1:
            ax.set_xlabel('Vibration Frequency (Hz)', fontsize=10)
        if idx == 0:
            ax.legend(loc='lower left', fontsize=9)
            
    fig.suptitle('E2-B Predicted Class Distribution Across Frequency (Fixed Ad = 1.0 N*m)', fontsize=13, fontweight='bold')
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "E2B_predicted_class_distribution.png")
    fig.savefig(FIGURES_DIR / "E2B_predicted_class_distribution.pdf")
    plt.close(fig)
    
    # Figure 3: Within-Parent Frequency Trajectories (Tracking individual parents)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), sharey=True)
    # Compare SHAPE vs Torque on seed 1729
    for ax_idx, (r, ax) in enumerate(zip(["shape_cwt", "torque_cwt"], axes)):
        sub_r = df[(df["representation"] == r) & (df["seed"] == 1729)]
        for p in unique_parents:
            parent_sub = sub_r[sub_r["parent_trajectory_id"] == p].sort_values("f_d")
            y_vals = (parent_sub["prediction"] == 3).astype(int) * 100
            # jitter slightly for visibility if overlap
            ax.plot(parent_sub["f_d"], y_vals, alpha=0.25, color=METHOD_COLORS[r], linewidth=1.5)
            
        mean_resp = sub_r.groupby("f_d").apply(lambda g: (g["prediction"] == 3).mean() * 100)
        ax.plot(mean_resp.index, mean_resp.values, color='black', linewidth=3, marker='o', label='Mean Response')
        ax.set_title(f'{METHOD_LABELS[r]} Within-Parent Trajectories (Seed 1729)', fontsize=11, fontweight='bold')
        ax.set_xlabel('Frequency (Hz)', fontsize=11)
        if ax_idx == 0:
            ax.set_ylabel('Vibration Recall (%)', fontsize=11)
        ax.set_xticks(FREQUENCIES)
        ax.set_ylim(-5, 105)
        ax.grid(True, linestyle='--', alpha=0.5)
        ax.legend(loc='lower left')
        
    fig.suptitle('E2-B Within-Parent Recall Across Controlled Frequencies', fontsize=13, fontweight='bold')
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "E2B_within_parent_frequency.png")
    fig.savefig(FIGURES_DIR / "E2B_within_parent_frequency.pdf")
    plt.close(fig)
    
    print("E2-B Controlled Frequency Sweep Analysis Complete.")

if __name__ == "__main__":
    analyze_e2b()
