import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

ROOT = Path(r"C:\Users\Johnny\Desktop\KINOVA_FINAL_ANALYSIS_ANTIGRAVITY")
DERIVED_DIR = ROOT / "derived"
TABLES_DIR = ROOT / "tables"
FIGURES_DIR = ROOT / "figures" / "E3"
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
    "shape_temporal": "#9467bd",  # purple
    "shape_fft": "#8c564b"        # brown
}

METHOD_LABELS = {
    "shape_cwt": "SHAPE-CWT",
    "torque_cwt": "Torque-CWT",
    "gmo_cwt": "GMO-CWT",
    "energy_cwt": "EO-CWT",
    "shape_temporal": "SHAPE-Temporal",
    "shape_fft": "SHAPE-FFT"
}

QUARTILES = ["Q1", "Q2", "Q3", "Q4"]
CLASS_NAMES = ["Nominal", "LoE", "Friction", "Vibration"]

def analyze_e3():
    print("--- Running E3 Operating Excitation & Mode Forensic Analysis ---")
    df = pd.read_parquet(DERIVED_DIR / "canonical_e0_primary.parquet")
    
    reps = ["shape_cwt", "torque_cwt", "gmo_cwt", "energy_cwt", "shape_temporal", "shape_fft"]
    seeds = [1729, 2027, 4099, 7919, 104729]
    
    # 1. Table T09_E3_excitation.csv (Overall & Per-Class across Q1-Q4)
    t09_records = []
    
    # Check sample size N per quartile
    sample = df[(df["representation"] == "shape_cwt") & (df["seed"] == 1729)]
    q_counts = sample["excitation_quartile"].value_counts().to_dict()
    print("Test set runs per excitation quartile (per seed, total N=3,000):", q_counts)
    
    for q in QUARTILES:
        for r in reps:
            acc_list = []
            f1_list = []
            per_class_recalls = {c: [] for c in CLASS_NAMES}
            bin_det_list = []
            
            for s in seeds:
                sub = df[(df["representation"] == r) & (df["seed"] == s) & (df["excitation_quartile"] == q)]
                acc_list.append((sub["prediction"] == sub["label"]).mean())
                # binary fault detection on fault runs
                fault_sub = sub[sub["label"] != 0]
                bin_det_list.append((fault_sub["prediction"] != 0).mean())
                
                for c_idx, c in enumerate(CLASS_NAMES):
                    c_sub = sub[sub["label"] == c_idx]
                    if len(c_sub) > 0:
                        per_class_recalls[c].append((c_sub["prediction"] == c_idx).mean())
                        
            rec = {
                "Excitation_Quartile": q,
                "Representation": METHOD_LABELS[r],
                "rep_key": r,
                "N_per_Seed": q_counts.get(q, 0),
                "Accuracy_Mean": np.mean(acc_list),
                "Accuracy_SD": np.std(acc_list, ddof=1),
                "Fault_Detection_Mean": np.mean(bin_det_list),
                "Fault_Detection_SD": np.std(bin_det_list, ddof=1),
            }
            for c in CLASS_NAMES:
                rec[f"{c}_Recall_Mean"] = np.mean(per_class_recalls[c])
                rec[f"{c}_Recall_SD"] = np.std(per_class_recalls[c], ddof=1)
            t09_records.append(rec)
            
    df_t09 = pd.DataFrame(t09_records)
    df_t09.to_csv(TABLES_DIR / "T09_E3_excitation.csv", index=False)
    print("Saved tables/T09_E3_excitation.csv")
    
    # 2. Table T10_E3_mode.csv (Fly vs Stop)
    t10_records = []
    mode_counts = sample["trajectory_mode"].value_counts().to_dict()
    print("Test set runs per trajectory mode (per seed):", mode_counts)
    
    for mode in ["fly", "stop"]:
        for r in reps:
            acc_list = []
            per_class_recalls = {c: [] for c in CLASS_NAMES}
            for s in seeds:
                sub = df[(df["representation"] == r) & (df["seed"] == s) & (df["trajectory_mode"] == mode)]
                acc_list.append((sub["prediction"] == sub["label"]).mean())
                for c_idx, c in enumerate(CLASS_NAMES):
                    c_sub = sub[sub["label"] == c_idx]
                    per_class_recalls[c].append((c_sub["prediction"] == c_idx).mean())
                    
            rec = {
                "Trajectory_Mode": mode,
                "Representation": METHOD_LABELS[r],
                "rep_key": r,
                "N_per_Seed": mode_counts.get(mode, 0),
                "Accuracy_Mean": np.mean(acc_list),
                "Accuracy_SD": np.std(acc_list, ddof=1),
            }
            for c in CLASS_NAMES:
                rec[f"{c}_Recall_Mean"] = np.mean(per_class_recalls[c])
                rec[f"{c}_Recall_SD"] = np.std(per_class_recalls[c], ddof=1)
            t10_records.append(rec)
            
    df_t10 = pd.DataFrame(t10_records)
    df_t10.to_csv(TABLES_DIR / "T10_E3_mode.csv", index=False)
    print("Saved tables/T10_E3_mode.csv")
    
    # 3. Figures for E3
    print("Generating E3 Figures...")
    
    # Figure 1: Overall Accuracy vs Excitation Quartile Q1 -> Q4
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(QUARTILES))
    for r in reps:
        sub = df_t09[df_t09["rep_key"] == r].set_index("Excitation_Quartile").loc[QUARTILES]
        y = sub["Accuracy_Mean"] * 100
        yerr = sub["Accuracy_SD"] * 100
        ax.errorbar(x, y, yerr=yerr, marker='o', linewidth=2.2, capsize=4, label=METHOD_LABELS[r], color=METHOD_COLORS[r])
        
    ax.set_ylabel('Overall Accuracy (%)', fontsize=12, fontweight='bold')
    ax.set_xlabel('Operating Excitation Quartile [Joint 2 RMS Velocity]', fontsize=11, fontweight='bold')
    ax.set_title('E3 Overall Accuracy vs Excitation Quartile (Q1=Lowest, Q4=Highest)', fontsize=12, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels([f"{q}\n(N={q_counts[q]})" for q in QUARTILES], fontsize=10)
    ax.set_ylim(40, 100)
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(loc='lower right', frameon=True)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "E3_metric_vs_excitation_quartile.png")
    fig.savefig(FIGURES_DIR / "E3_metric_vs_excitation_quartile.pdf")
    plt.close(fig)
    
    # Figure 2: Per-Class Recall across Excitation Quartiles (4 Subplots)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharey=True, sharex=True)
    for idx, c in enumerate(CLASS_NAMES):
        ax = axes[idx // 2, idx % 2]
        for r in reps:
            sub = df_t09[df_t09["rep_key"] == r].set_index("Excitation_Quartile").loc[QUARTILES]
            y = sub[f"{c}_Recall_Mean"] * 100
            yerr = sub[f"{c}_Recall_SD"] * 100
            ax.errorbar(x, y, yerr=yerr, marker='o', linewidth=2, capsize=3, label=METHOD_LABELS[r], color=METHOD_COLORS[r])
            
        ax.set_title(f'Class: {c}', fontsize=12, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(QUARTILES, fontsize=10)
        ax.set_ylim(15, 103)
        ax.grid(True, linestyle='--', alpha=0.5)
        if idx % 2 == 0:
            ax.set_ylabel('Class Recall (%)', fontsize=11)
        if idx // 2 == 1:
            ax.set_xlabel('Excitation Quartile', fontsize=11)
        if idx == 0:
            ax.legend(loc='lower left', fontsize=9)
            
    fig.suptitle('E3 Per-Class Diagnostic Sensitivity Across Operating Excitation Quartiles', fontsize=14, fontweight='bold')
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "E3_per_class_vs_excitation.png")
    fig.savefig(FIGURES_DIR / "E3_per_class_vs_excitation.pdf")
    plt.close(fig)
    
    # Figure 3: Fly vs Stop Mode Comparison (Bar Chart)
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(reps))
    w = 0.35
    fly_acc = [df_t10[(df_t10["rep_key"] == r) & (df_t10["Trajectory_Mode"] == "fly")]["Accuracy_Mean"].values[0] * 100 for r in reps]
    fly_sd = [df_t10[(df_t10["rep_key"] == r) & (df_t10["Trajectory_Mode"] == "fly")]["Accuracy_SD"].values[0] * 100 for r in reps]
    stop_acc = [df_t10[(df_t10["rep_key"] == r) & (df_t10["Trajectory_Mode"] == "stop")]["Accuracy_Mean"].values[0] * 100 for r in reps]
    stop_sd = [df_t10[(df_t10["rep_key"] == r) & (df_t10["Trajectory_Mode"] == "stop")]["Accuracy_SD"].values[0] * 100 for r in reps]
    
    ax.bar(x - w/2, fly_acc, w, yerr=fly_sd, capsize=4, label='FLY (Dynamic Reversal)', color='#386cb0', alpha=0.85, edgecolor='black')
    ax.bar(x + w/2, stop_acc, w, yerr=stop_sd, capsize=4, label='STOP (Zero Boundary Velocity)', color='#f0027f', alpha=0.85, edgecolor='black')
    
    for i, r in enumerate(reps):
        sub_fly = df[(df["representation"] == r) & (df["trajectory_mode"] == "fly")].groupby("seed").apply(lambda g: (g["prediction"] == g["label"]).mean() * 100)
        sub_stop = df[(df["representation"] == r) & (df["trajectory_mode"] == "stop")].groupby("seed").apply(lambda g: (g["prediction"] == g["label"]).mean() * 100)
        ax.scatter([x[i] - w/2] * len(sub_fly), sub_fly.values, color='black', s=16, zorder=5)
        ax.scatter([x[i] + w/2] * len(sub_stop), sub_stop.values, color='black', s=16, zorder=5)
        
    ax.set_ylabel('Accuracy (%)', fontsize=12)
    ax.set_title('E3 Trajectory Boundary Mode: FLY vs STOP (N=1,500 test runs each, 5 seeds)', fontsize=12, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels([METHOD_LABELS[r] for r in reps], rotation=15, ha='right', fontsize=10)
    ax.set_ylim(40, 102)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    ax.legend(loc='lower right', frameon=True)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "E3_fly_stop.png")
    fig.savefig(FIGURES_DIR / "E3_fly_stop.pdf")
    plt.close(fig)
    
    # Figure 4: Severity x Excitation Interaction (For LoE and Friction where excitation interacts)
    for fault in ["LoE", "Friction"]:
        fig, axes = plt.subplots(1, 4, figsize=(16, 4.5), sharey=True)
        cwt_reps = ["shape_cwt", "torque_cwt", "gmo_cwt", "energy_cwt"]
        
        bins = ["[0.02, 0.05)", "[0.05, 0.10)", "[0.10, 0.20)", "[0.20, 0.30]"] if fault == "LoE" else ["[0.02, 0.10)", "[0.10, 0.30)", "[0.30, 0.75)", "[0.75, 1.50]"]
        
        for ax_i, r in enumerate(cwt_reps):
            ax = axes[ax_i]
            # plot lines for each quartile
            for q_idx, q in enumerate(QUARTILES):
                y_means = []
                for b in bins:
                    cell = df[(df["representation"] == r) & (df["fault_class"] == fault) & 
                              (df["severity_bin"] == b) & (df["excitation_quartile"] == q)]
                    y_means.append((cell["prediction"] == cell["label"]).mean() * 100 if len(cell)>0 else np.nan)
                ax.plot(range(len(bins)), y_means, marker='o', linewidth=2, label=f'{q}')
                
            ax.set_title(METHOD_LABELS[r], fontsize=11, fontweight='bold')
            ax.set_xticks(range(len(bins)))
            ax.set_xticklabels(bins, rotation=25, ha='right', fontsize=8.5)
            ax.grid(True, linestyle='--', alpha=0.5)
            if ax_i == 0:
                ax.set_ylabel(f'{fault} Recall (%)', fontsize=11)
            ax.set_xlabel('Severity Stratum', fontsize=10)
            if ax_i == 0:
                ax.legend(title='Excitation', loc='lower right', fontsize=8.5)
                
        fig.suptitle(f'E3 {fault}: Severity x Excitation Interaction Across Observers', fontsize=13, fontweight='bold')
        fig.tight_layout()
        fig.savefig(FIGURES_DIR / f"E3_{fault}_severity_x_excitation.png")
        fig.savefig(FIGURES_DIR / f"E3_{fault}_severity_x_excitation.pdf")
        plt.close(fig)
        
    print("E3 Operating Excitation & Mode Analysis Complete.")

if __name__ == "__main__":
    analyze_e3()
