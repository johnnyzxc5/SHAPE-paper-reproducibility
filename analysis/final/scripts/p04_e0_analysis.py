import sys
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from e0_pairwise_stats import compute_pairwise_table, plot_pairwise_figure
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, f1_score,
    recall_score, precision_score, confusion_matrix,
    roc_auc_score, average_precision_score, brier_score_loss
)

ROOT = Path(r"C:\Users\Johnny\Desktop\KINOVA_FINAL_ANALYSIS_ANTIGRAVITY")
DERIVED_DIR = ROOT / "derived"
TABLES_DIR = ROOT / "tables"
FIGURES_DIR = ROOT / "figures" / "E0"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

# Standard styling
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

CLASS_NAMES = ["Nominal", "LoE", "Friction", "Vibration"]

def compute_binary_metrics(y_true, y_pred, y_prob):
    # True binary: 0=Nominal, 1=Fault
    tb = (y_true != 0).astype(int)
    pb = (y_pred != 0).astype(int)
    
    sens = float(recall_score(tb, pb, pos_label=1)) # TPR / Sensitivity / Fault Recall
    spec = float(recall_score(tb, pb, pos_label=0)) # TNR / Specificity / Nominal Recall
    far = 1.0 - spec                                 # False Alarm Rate on Nominal
    mdr = 1.0 - sens                                 # Missed Detection Rate on Faults
    prec = float(precision_score(tb, pb, pos_label=1, zero_division=0))
    f1 = float(f1_score(tb, pb, pos_label=1))
    bal_acc = 0.5 * (sens + spec)
    
    auc = float(roc_auc_score(tb, y_prob)) if len(np.unique(tb)) > 1 else np.nan
    pr_auc = float(average_precision_score(tb, y_prob)) if len(np.unique(tb)) > 1 else np.nan
    brier = float(brier_score_loss(tb, y_prob))
    
    return {
        "sensitivity_fault_recall": sens,
        "specificity_nominal_recall": spec,
        "false_alarm_rate": far,
        "missed_detection_rate": mdr,
        "binary_precision": prec,
        "binary_f1": f1,
        "binary_balanced_acc": bal_acc,
        "binary_roc_auc": auc,
        "binary_pr_auc": pr_auc,
        "binary_brier_score": brier
    }

def analyze_e0():
    print("--- Running E0 Forensic Analysis ---")
    df = pd.read_parquet(DERIVED_DIR / "canonical_e0_primary.parquet")
    
    reps = ["shape_cwt", "torque_cwt", "gmo_cwt", "energy_cwt", "shape_temporal", "shape_fft"]
    seeds = [1729, 2027, 4099, 7919, 104729]
    
    # 1. Overall & Per-Class Metrics per seed
    seed_records = []
    binary_records = []
    per_class_records = []
    
    conf_matrices = {r: np.zeros((4, 4), dtype=int) for r in reps}
    
    for r in reps:
        for s in seeds:
            sub = df[(df["representation"] == r) & (df["seed"] == s)].sort_values("run_uid").reset_index(drop=True)
            y_true = sub["label"].to_numpy()
            y_pred = sub["prediction"].to_numpy()
            y_prob_fault = sub["prob_fault"].to_numpy()
            
            acc = float(accuracy_score(y_true, y_pred))
            bal_acc = float(balanced_accuracy_score(y_true, y_pred))
            macro_f1 = float(f1_score(y_true, y_pred, average="macro"))
            
            seed_records.append({
                "representation": r,
                "seed": s,
                "accuracy": acc,
                "balanced_accuracy": bal_acc,
                "macro_f1": macro_f1
            })
            
            # Binary
            bin_m = compute_binary_metrics(y_true, y_pred, y_prob_fault)
            bin_m["representation"] = r
            bin_m["seed"] = s
            binary_records.append(bin_m)
            
            # Per class
            cm = confusion_matrix(y_true, y_pred, labels=[0, 1, 2, 3])
            conf_matrices[r] += cm
            
            rec = recall_score(y_true, y_pred, labels=[0, 1, 2, 3], average=None, zero_division=0)
            prec = precision_score(y_true, y_pred, labels=[0, 1, 2, 3], average=None, zero_division=0)
            f1_c = f1_score(y_true, y_pred, labels=[0, 1, 2, 3], average=None, zero_division=0)
            
            for c_idx, c_name in enumerate(CLASS_NAMES):
                per_class_records.append({
                    "representation": r,
                    "seed": s,
                    "class_name": c_name,
                    "recall": float(rec[c_idx]),
                    "precision": float(prec[c_idx]),
                    "f1": float(f1_c[c_idx])
                })
                
    df_seed = pd.DataFrame(seed_records)
    df_bin = pd.DataFrame(binary_records)
    df_per_class = pd.DataFrame(per_class_records)
    
    # Save seed-level derived tables
    df_seed.to_csv(DERIVED_DIR / "e0_metrics_by_seed.csv", index=False)
    df_bin.to_csv(DERIVED_DIR / "e0_binary_by_seed.csv", index=False)
    df_per_class.to_csv(DERIVED_DIR / "e0_per_class_by_seed.csv", index=False)
    
    # 2. Build T02_E0_overall.csv (mean, std, median, min, max across 5 seeds)
    t02_list = []
    for r in reps:
        sub = df_seed[df_seed["representation"] == r]
        t02_list.append({
            "Representation": METHOD_LABELS[r],
            "rep_key": r,
            "Accuracy_Mean": sub["accuracy"].mean(),
            "Accuracy_SD": sub["accuracy"].std(),
            "Accuracy_Median": sub["accuracy"].median(),
            "Accuracy_Min": sub["accuracy"].min(),
            "Accuracy_Max": sub["accuracy"].max(),
            "Balanced_Acc_Mean": sub["balanced_accuracy"].mean(),
            "Balanced_Acc_SD": sub["balanced_accuracy"].std(),
            "Macro_F1_Mean": sub["macro_f1"].mean(),
            "Macro_F1_SD": sub["macro_f1"].std(),
            "Macro_F1_Median": sub["macro_f1"].median(),
            "Macro_F1_Min": sub["macro_f1"].min(),
            "Macro_F1_Max": sub["macro_f1"].max()
        })
    df_t02 = pd.DataFrame(t02_list)
    df_t02.to_csv(TABLES_DIR / "T02_E0_overall.csv", index=False)
    print("Saved tables/T02_E0_overall.csv")
    
    # 3. Build T03_E0_per_class.csv
    t03_list = []
    for r in reps:
        for c in CLASS_NAMES:
            sub = df_per_class[(df_per_class["representation"] == r) & (df_per_class["class_name"] == c)]
            t03_list.append({
                "Representation": METHOD_LABELS[r],
                "Class": c,
                "Recall_Mean": sub["recall"].mean(),
                "Recall_SD": sub["recall"].std(),
                "Recall_Min": sub["recall"].min(),
                "Recall_Max": sub["recall"].max(),
                "Precision_Mean": sub["precision"].mean(),
                "Precision_SD": sub["precision"].std(),
                "F1_Mean": sub["f1"].mean(),
                "F1_SD": sub["f1"].std()
            })
    df_t03 = pd.DataFrame(t03_list)
    df_t03.to_csv(TABLES_DIR / "T03_E0_per_class.csv", index=False)
    print("Saved tables/T03_E0_per_class.csv")
    
    # 4. Build T04_E0_binary_detection.csv
    t04_list = []
    for r in reps:
        sub = df_bin[df_bin["representation"] == r]
        t04_list.append({
            "Representation": METHOD_LABELS[r],
            "Sensitivity_FaultRecall_Mean": sub["sensitivity_fault_recall"].mean(),
            "Sensitivity_FaultRecall_SD": sub["sensitivity_fault_recall"].std(),
            "Specificity_NominalRecall_Mean": sub["specificity_nominal_recall"].mean(),
            "Specificity_NominalRecall_SD": sub["specificity_nominal_recall"].std(),
            "False_Alarm_Rate_Mean": sub["false_alarm_rate"].mean(),
            "False_Alarm_Rate_SD": sub["false_alarm_rate"].std(),
            "Missed_Detection_Rate_Mean": sub["missed_detection_rate"].mean(),
            "Missed_Detection_Rate_SD": sub["missed_detection_rate"].std(),
            "Binary_F1_Mean": sub["binary_f1"].mean(),
            "Binary_F1_SD": sub["binary_f1"].std(),
            "Binary_BalancedAcc_Mean": sub["binary_balanced_acc"].mean(),
            "Binary_BalancedAcc_SD": sub["binary_balanced_acc"].std(),
            "Binary_ROC_AUC_Mean": sub["binary_roc_auc"].mean(),
            "Binary_ROC_AUC_SD": sub["binary_roc_auc"].std(),
            "Binary_BrierScore_Mean": sub["binary_brier_score"].mean(),
            "Binary_BrierScore_SD": sub["binary_brier_score"].std()
        })
    df_t04 = pd.DataFrame(t04_list)
    df_t04.to_csv(TABLES_DIR / "T04_E0_binary_detection.csv", index=False)
    print("Saved tables/T04_E0_binary_detection.csv")
    
    # 5. Build T05: parent bootstrap of the five-seed mean, with paired runs.
    df_t05 = compute_pairwise_table(df)
    df_t05.to_csv(TABLES_DIR / "T05_E0_pairwise_deltas.csv", index=False)
    print("Saved tables/T05_E0_pairwise_deltas.csv")
    
    # 6. Generate Figures
    print("Generating Figures for E0...")
    
    # E0_F01_overall_metrics
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(reps))
    width = 0.35
    
    acc_means = [df_t02.loc[df_t02["rep_key"] == r, "Accuracy_Mean"].values[0] * 100 for r in reps]
    acc_sds = [df_t02.loc[df_t02["rep_key"] == r, "Accuracy_SD"].values[0] * 100 for r in reps]
    f1_means = [df_t02.loc[df_t02["rep_key"] == r, "Macro_F1_Mean"].values[0] * 100 for r in reps]
    f1_sds = [df_t02.loc[df_t02["rep_key"] == r, "Macro_F1_SD"].values[0] * 100 for r in reps]
    
    rects1 = ax.bar(x - width/2, acc_means, width, yerr=acc_sds, capsize=4, label='Accuracy (%)', color='#2b5c8f', edgecolor='black', alpha=0.85)
    rects2 = ax.bar(x + width/2, f1_means, width, yerr=f1_sds, capsize=4, label='Macro-F1 (%)', color='#d95f02', edgecolor='black', alpha=0.85)
    
    # Overlay individual seed points
    for idx, r in enumerate(reps):
        sub = df_seed[df_seed["representation"] == r]
        ax.scatter([x[idx] - width/2] * len(sub), sub["accuracy"] * 100, color='black', s=20, zorder=5, alpha=0.7)
        ax.scatter([x[idx] + width/2] * len(sub), sub["macro_f1"] * 100, color='black', s=20, zorder=5, alpha=0.7)
        
    ax.set_ylabel('Score (%)', fontsize=12)
    ax.set_title('E0 Clean Primary Benchmark: Overall Accuracy & Macro-F1 (N=3,000 test runs, 5 seeds)', fontsize=13, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels([METHOD_LABELS[r] for r in reps], rotation=15, ha='right', fontsize=11)
    ax.set_ylim(40, 102)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    ax.legend(loc='lower right', frameon=True)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "E0_F01_overall_metrics.png")
    fig.savefig(FIGURES_DIR / "E0_F01_overall_metrics.pdf")
    plt.close(fig)
    
    # E0_F02_per_class_recall
    fig, ax = plt.subplots(figsize=(11, 5.5))
    x = np.arange(len(CLASS_NAMES))
    n_reps = len(reps)
    w = 0.13
    
    for i, r in enumerate(reps):
        means = []
        sds = []
        for c in CLASS_NAMES:
            sub = df_per_class[(df_per_class["representation"] == r) & (df_per_class["class_name"] == c)]
            means.append(sub["recall"].mean() * 100)
            sds.append(sub["recall"].std() * 100)
        pos = x + (i - (n_reps-1)/2) * w
        ax.bar(pos, means, w, yerr=sds, capsize=3, label=METHOD_LABELS[r], color=METHOD_COLORS[r], edgecolor='black', alpha=0.85)
        # scatter seed points
        for c_idx, c in enumerate(CLASS_NAMES):
            sub = df_per_class[(df_per_class["representation"] == r) & (df_per_class["class_name"] == c)]
            ax.scatter([pos[c_idx]] * len(sub), sub["recall"] * 100, color='black', s=12, zorder=5, alpha=0.6)
            
    ax.set_ylabel('Class Recall (%)', fontsize=12)
    ax.set_title('E0 Per-Class Recall Breakdown Across Representations (N=750 per class, 5 seeds)', fontsize=13, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(CLASS_NAMES, fontsize=11, fontweight='bold')
    ax.set_ylim(15, 105)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left', frameon=True)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "E0_F02_per_class_recall.png")
    fig.savefig(FIGURES_DIR / "E0_F02_per_class_recall.pdf")
    plt.close(fig)
    
    # E0_F03_confusion_<method> (Aggregated over 5 seeds = 15,000 predictions)
    for r in reps:
        cm_norm = conf_matrices[r].astype(float) / conf_matrices[r].sum(axis=1, keepdims=True) * 100
        fig, ax = plt.subplots(figsize=(6, 5))
        im = ax.imshow(cm_norm, cmap='Blues', vmin=0, vmax=100)
        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label('Recall (%)', fontsize=10)
        
        ax.set_xticks(range(4))
        ax.set_yticks(range(4))
        ax.set_xticklabels(CLASS_NAMES, fontsize=10)
        ax.set_yticklabels(CLASS_NAMES, fontsize=10)
        ax.set_xlabel('Predicted Class', fontsize=11, fontweight='bold')
        ax.set_ylabel('True Class', fontsize=11, fontweight='bold')
        ax.set_title(f'E0 Confusion Matrix: {METHOD_LABELS[r]}\n(Pooled 5 seeds, N=15,000 predictions)', fontsize=11, fontweight='bold')
        
        for row in range(4):
            for col in range(4):
                val = cm_norm[row, col]
                cnt = conf_matrices[r][row, col]
                color = 'white' if val > 50 else 'black'
                ax.text(col, row, f"{val:.1f}%\n({cnt:,})", ha='center', va='center', color=color, fontsize=9)
                
        fig.tight_layout()
        fig.savefig(FIGURES_DIR / f"E0_F03_confusion_{r}.png")
        fig.savefig(FIGURES_DIR / f"E0_F03_confusion_{r}.pdf")
        plt.close(fig)
        
    # E0_F04_binary_detection (Sensitivity, Specificity, FAR, MDR)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    x = np.arange(len(reps))
    w = 0.35
    
    sens_m = [df_bin[df_bin["representation"] == r]["sensitivity_fault_recall"].mean() * 100 for r in reps]
    sens_sd = [df_bin[df_bin["representation"] == r]["sensitivity_fault_recall"].std() * 100 for r in reps]
    spec_m = [df_bin[df_bin["representation"] == r]["specificity_nominal_recall"].mean() * 100 for r in reps]
    spec_sd = [df_bin[df_bin["representation"] == r]["specificity_nominal_recall"].std() * 100 for r in reps]
    
    ax1.bar(x - w/2, sens_m, w, yerr=sens_sd, capsize=4, label='Fault Sensitivity (Recall %)', color='#2ca02c', alpha=0.85, edgecolor='black')
    ax1.bar(x + w/2, spec_m, w, yerr=spec_sd, capsize=4, label='Nominal Specificity (%)', color='#1f77b4', alpha=0.85, edgecolor='black')
    for i, r in enumerate(reps):
        sub = df_bin[df_bin["representation"] == r]
        ax1.scatter([x[i] - w/2] * len(sub), sub["sensitivity_fault_recall"] * 100, color='black', s=16, zorder=5)
        ax1.scatter([x[i] + w/2] * len(sub), sub["specificity_nominal_recall"] * 100, color='black', s=16, zorder=5)
    ax1.set_ylabel('Rate (%)', fontsize=11)
    ax1.set_title('Fault Sensitivity vs Nominal Specificity', fontsize=11, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels([METHOD_LABELS[r] for r in reps], rotation=20, ha='right', fontsize=9)
    ax1.set_ylim(60, 102)
    ax1.grid(axis='y', linestyle='--', alpha=0.5)
    ax1.legend(loc='lower right')
    
    far_m = [df_bin[df_bin["representation"] == r]["false_alarm_rate"].mean() * 100 for r in reps]
    far_sd = [df_bin[df_bin["representation"] == r]["false_alarm_rate"].std() * 100 for r in reps]
    mdr_m = [df_bin[df_bin["representation"] == r]["missed_detection_rate"].mean() * 100 for r in reps]
    mdr_sd = [df_bin[df_bin["representation"] == r]["missed_detection_rate"].std() * 100 for r in reps]
    
    ax2.bar(x - w/2, far_m, w, yerr=far_sd, capsize=4, label='False Alarm Rate (FAR %)', color='#d62728', alpha=0.85, edgecolor='black')
    ax2.bar(x + w/2, mdr_m, w, yerr=mdr_sd, capsize=4, label='Missed Detection Rate (MDR %)', color='#ff7f0e', alpha=0.85, edgecolor='black')
    for i, r in enumerate(reps):
        sub = df_bin[df_bin["representation"] == r]
        ax2.scatter([x[i] - w/2] * len(sub), sub["false_alarm_rate"] * 100, color='black', s=16, zorder=5)
        ax2.scatter([x[i] + w/2] * len(sub), sub["missed_detection_rate"] * 100, color='black', s=16, zorder=5)
    ax2.set_ylabel('Error Rate (%)', fontsize=11)
    ax2.set_title('False Alarm Rate vs Missed Detection Rate', fontsize=11, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels([METHOD_LABELS[r] for r in reps], rotation=20, ha='right', fontsize=9)
    ax2.grid(axis='y', linestyle='--', alpha=0.5)
    ax2.legend(loc='upper right')
    
    fig.suptitle('E0 Binary Fault Detection Performance (Frozen Argmax, 5 Seeds)', fontsize=13, fontweight='bold')
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "E0_F04_binary_detection.png")
    fig.savefig(FIGURES_DIR / "E0_F04_binary_detection.pdf")
    plt.close(fig)
    
    # E0_F05_seed_stability
    fig, ax = plt.subplots(figsize=(9, 5))
    for r in reps:
        sub = df_seed[df_seed["representation"] == r].sort_values("seed")
        ax.plot(range(len(seeds)), sub["accuracy"] * 100, marker='o', linewidth=2, label=METHOD_LABELS[r], color=METHOD_COLORS[r])
        
    ax.set_ylabel('Accuracy (%)', fontsize=12)
    ax.set_xlabel('Model Training Seed', fontsize=12)
    ax.set_title('E0 Seed Stability Across Representations (N=3,000 Test Runs per Seed)', fontsize=13, fontweight='bold')
    ax.set_xticks(range(len(seeds)))
    ax.set_xticklabels([str(s) for s in seeds], fontsize=11)
    ax.set_ylim(40, 100)
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(loc='lower right', frameon=True)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "E0_F05_seed_stability.png")
    fig.savefig(FIGURES_DIR / "E0_F05_seed_stability.pdf")
    plt.close(fig)
    
    # E0_F06: same five-seed estimand for point and uncertainty.
    plot_pairwise_figure(df_t05)
    
    # E0_F07_shape_representation_ablation (CWT vs Temporal vs FFT)
    fig, ax = plt.subplots(figsize=(9, 5))
    ablation_reps = ["shape_cwt", "shape_temporal", "shape_fft"]
    ab_labels = ["SHAPE-CWT (2D)", "SHAPE-Temporal (1D)", "SHAPE-FFT (1D)"]
    x = np.arange(len(ablation_reps))
    
    acc_ab = [df_t02.loc[df_t02["rep_key"] == r, "Accuracy_Mean"].values[0] * 100 for r in ablation_reps]
    acc_ab_sd = [df_t02.loc[df_t02["rep_key"] == r, "Accuracy_SD"].values[0] * 100 for r in ablation_reps]
    f1_ab = [df_t02.loc[df_t02["rep_key"] == r, "Macro_F1_Mean"].values[0] * 100 for r in ablation_reps]
    f1_ab_sd = [df_t02.loc[df_t02["rep_key"] == r, "Macro_F1_SD"].values[0] * 100 for r in ablation_reps]
    
    w = 0.35
    ax.bar(x - w/2, acc_ab, w, yerr=acc_ab_sd, capsize=4, label='Accuracy (%)', color='#1f77b4', edgecolor='black', alpha=0.85)
    ax.bar(x + w/2, f1_ab, w, yerr=f1_ab_sd, capsize=4, label='Macro-F1 (%)', color='#ff7f0e', edgecolor='black', alpha=0.85)
    for idx, r in enumerate(ablation_reps):
        sub = df_seed[df_seed["representation"] == r]
        ax.scatter([x[idx] - w/2] * len(sub), sub["accuracy"] * 100, color='black', s=20, zorder=5)
        ax.scatter([x[idx] + w/2] * len(sub), sub["macro_f1"] * 100, color='black', s=20, zorder=5)
        
    ax.set_ylabel('Score (%)', fontsize=12)
    ax.set_title('SHAPE Representation Ablation: CWT vs Temporal vs FFT Spectrum (5 Seeds)', fontsize=12, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(ab_labels, fontsize=11, fontweight='bold')
    ax.set_ylim(40, 95)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    ax.legend(loc='lower left')
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "E0_F07_shape_representation_ablation.png")
    fig.savefig(FIGURES_DIR / "E0_F07_shape_representation_ablation.pdf")
    plt.close(fig)
    
    print("E0 Forensic Analysis Complete. All figures and tables generated.")

if __name__ == "__main__":
    analyze_e0()
