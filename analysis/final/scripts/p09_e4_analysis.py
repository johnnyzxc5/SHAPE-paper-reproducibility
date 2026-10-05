import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, f1_score,
    recall_score, precision_score, confusion_matrix,
    roc_auc_score, brier_score_loss
)

ROOT = Path(r"C:\Users\Johnny\Desktop\KINOVA_FINAL_ANALYSIS_ANTIGRAVITY")
DERIVED_DIR = ROOT / "derived"
TABLES_DIR = ROOT / "tables"
FIGURES_DIR = ROOT / "figures" / "E4"
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

CLASS_NAMES = ["Nominal", "LoE", "Friction", "Vibration"]

CONDITIONS_ORDER = [
    "clean",
    "position_0.01deg", "position_0.05deg", "position_0.2deg",
    "velocity_40dB", "velocity_30dB", "velocity_20dB", "velocity_10dB",
    "combined_40dB_0.01deg", "combined_40dB_0.05deg", "combined_40dB_0.2deg"
]

def analyze_e4():
    print("--- Running E4 Sensor Noise Forensic Analysis ---")
    df_e0 = pd.read_parquet(DERIVED_DIR / "canonical_e0_primary.parquet")
    df_e4 = pd.read_parquet(DERIVED_DIR / "canonical_e4.parquet")
    
    # Tag e0 as clean condition
    df_e0_cwt = df_e0[df_e0["representation"].isin(METHOD_COLORS.keys())].copy()
    df_e0_cwt["e4_condition"] = "clean"
    df_e0_cwt["velocity_snr_db"] = np.inf
    df_e0_cwt["position_sigma_deg"] = 0.0
    
    full_df = pd.concat([df_e0_cwt, df_e4], ignore_index=True)
    
    reps = ["shape_cwt", "torque_cwt", "gmo_cwt", "energy_cwt"]
    seeds = [1729, 2027, 4099, 7919, 104729]
    
    # 1. Overall Noise Table T11
    t11_records = []
    t12_records = []
    
    print("Computing T11 overall and T12 per-class metrics across conditions...")
    for cond in CONDITIONS_ORDER:
        for r in reps:
            acc_list = []
            bal_list = []
            f1_list = []
            sens_list = []
            spec_list = []
            far_list = []
            mdr_list = []
            auc_list = []
            brier_list = []
            
            per_class_rec = {c: [] for c in CLASS_NAMES}
            per_class_prec = {c: [] for c in CLASS_NAMES}
            per_class_f1 = {c: [] for c in CLASS_NAMES}
            
            for s in seeds:
                sub = full_df[(full_df["e4_condition"] == cond) & (full_df["representation"] == r) & (full_df["seed"] == s)]
                y_t = sub["label"].to_numpy()
                y_p = sub["prediction"].to_numpy()
                y_prob = sub["prob_fault"].to_numpy()
                
                acc_list.append(accuracy_score(y_t, y_p))
                bal_list.append(balanced_accuracy_score(y_t, y_p))
                f1_list.append(f1_score(y_t, y_p, average="macro"))
                
                tb = (y_t != 0).astype(int)
                pb = (y_p != 0).astype(int)
                sens = float(recall_score(tb, pb, pos_label=1))
                spec = float(recall_score(tb, pb, pos_label=0))
                sens_list.append(sens)
                spec_list.append(spec)
                far_list.append(1.0 - spec)
                mdr_list.append(1.0 - sens)
                auc_list.append(roc_auc_score(tb, y_prob))
                brier_list.append(brier_score_loss(tb, y_prob))
                
                # Per class
                rec_c = recall_score(y_t, y_p, labels=[0, 1, 2, 3], average=None, zero_division=0)
                prec_c = precision_score(y_t, y_p, labels=[0, 1, 2, 3], average=None, zero_division=0)
                f1_c = f1_score(y_t, y_p, labels=[0, 1, 2, 3], average=None, zero_division=0)
                
                for idx, c in enumerate(CLASS_NAMES):
                    per_class_rec[c].append(rec_c[idx])
                    per_class_prec[c].append(prec_c[idx])
                    per_class_f1[c].append(f1_c[idx])
                    
            t11_records.append({
                "Condition": cond,
                "Evaluation_Source": "E0_CANONICAL" if cond == "clean" else "E4_CANONICAL",
                "Representation": METHOD_LABELS[r],
                "rep_key": r,
                "Accuracy_Mean": np.mean(acc_list),
                "Accuracy_SD": np.std(acc_list, ddof=1),
                "Balanced_Acc_Mean": np.mean(bal_list),
                "Macro_F1_Mean": np.mean(f1_list),
                "Macro_F1_SD": np.std(f1_list, ddof=1),
                "Fault_Sensitivity_Mean": np.mean(sens_list),
                "Fault_Sensitivity_SD": np.std(sens_list, ddof=1),
                "Nominal_Specificity_Mean": np.mean(spec_list),
                "False_Alarm_Rate_Mean": np.mean(far_list),
                "False_Alarm_Rate_SD": np.std(far_list, ddof=1),
                "Missed_Detection_Rate_Mean": np.mean(mdr_list),
                "Missed_Detection_Rate_SD": np.std(mdr_list, ddof=1),
                "ROC_AUC_Mean": np.mean(auc_list),
                "Brier_Score_Mean": np.mean(brier_list)
            })
            
            for c in CLASS_NAMES:
                t12_records.append({
                    "Condition": cond,
                    "Evaluation_Source": "E0_CANONICAL" if cond == "clean" else "E4_CANONICAL",
                    "Representation": METHOD_LABELS[r],
                    "rep_key": r,
                    "Class": c,
                    "Recall_Mean": np.mean(per_class_rec[c]),
                    "Recall_SD": np.std(per_class_rec[c], ddof=1),
                    "Precision_Mean": np.mean(per_class_prec[c]),
                    "Precision_SD": np.std(per_class_prec[c], ddof=1),
                    "F1_Mean": np.mean(per_class_f1[c]),
                    "F1_SD": np.std(per_class_f1[c], ddof=1)
                })
                
    df_t11 = pd.DataFrame(t11_records)
    df_t11.to_csv(TABLES_DIR / "T11_E4_overall_noise.csv", index=False)
    print("Saved tables/T11_E4_overall_noise.csv")
    
    df_t12 = pd.DataFrame(t12_records)
    df_t12.to_csv(TABLES_DIR / "T12_E4_per_class_noise.csv", index=False)
    print("Saved tables/T12_E4_per_class_noise.csv")
    
    # 2. Table T13 Severity x Noise (for velocity_40dB and clean)
    print("Computing T13 noise x severity breakdown...")
    t13_records = []
    faults = ["LoE", "Friction", "Vibration"]
    sev_bins = {
        "LoE": ["[0.02, 0.05)", "[0.05, 0.10)", "[0.10, 0.20)", "[0.20, 0.30]"],
        "Friction": ["[0.02, 0.10)", "[0.10, 0.30)", "[0.30, 0.75)", "[0.75, 1.50]"],
        "Vibration": ["[0.10, 0.50)", "[0.50, 1.00)", "[1.00, 1.75)", "[1.75, 2.50]"]
    }
    
    for cond in CONDITIONS_ORDER:
        for fault in faults:
            for b in sev_bins[fault]:
                for r in reps:
                    recs = []
                    bin_dets = []
                    dest_nom = []
                    dest_vib = []
                    dest_loe = []
                    dest_fric = []
                    
                    for s in seeds:
                        sub = full_df[(full_df["e4_condition"] == cond) & (full_df["representation"] == r) & 
                                      (full_df["seed"] == s) & (full_df["fault_class"] == fault) & 
                                      (full_df["severity_bin"] == b)]
                        if len(sub) > 0:
                            recs.append((sub["prediction"] == sub["label"]).mean())
                            bin_dets.append((sub["prediction"] != 0).mean())
                            dest_nom.append((sub["prediction_class"] == "Nominal").mean())
                            dest_vib.append((sub["prediction_class"] == "Vibration").mean())
                            dest_loe.append((sub["prediction_class"] == "LoE").mean())
                            dest_fric.append((sub["prediction_class"] == "Friction").mean())
                            
                    t13_records.append({
                        "Condition": cond,
                        "Evaluation_Source": "E0_CANONICAL" if cond == "clean" else "E4_CANONICAL",
                        "Fault_Class": fault,
                        "Severity_Bin": b,
                        "Representation": METHOD_LABELS[r],
                        "rep_key": r,
                        "Recall_Mean": np.mean(recs),
                        "Recall_SD": np.std(recs, ddof=1) if len(recs)>1 else 0.0,
                        "Fault_Detection_Mean": np.mean(bin_dets),
                        "Dest_Nominal_Mean": np.mean(dest_nom),
                        "Dest_Vibration_Mean": np.mean(dest_vib),
                        "Dest_LoE_Mean": np.mean(dest_loe),
                        "Dest_Friction_Mean": np.mean(dest_fric)
                    })
                    
    df_t13 = pd.DataFrame(t13_records)
    df_t13.to_csv(TABLES_DIR / "T13_E4_severity_noise.csv", index=False)
    print("Saved tables/T13_E4_severity_noise.csv")
    
    # 3. Generating Figures
    print("Generating E4 Figures...")
    
    # Figure 1: Velocity Robustness Curve (Clean, 40dB, 30dB, 20dB, 10dB)
    v_conds = ["clean", "velocity_40dB", "velocity_30dB", "velocity_20dB", "velocity_10dB"]
    v_labels = ["E0 clean", "40 dB", "30 dB", "20 dB", "10 dB"]
    
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(v_conds))
    for r in reps:
        sub = df_t11[df_t11["rep_key"] == r].set_index("Condition").loc[v_conds]
        ax.plot(x, sub["Accuracy_Mean"] * 100, marker='o', linewidth=2.5, label=METHOD_LABELS[r], color=METHOD_COLORS[r])
        # fill error bands
        ax.fill_between(x, (sub["Accuracy_Mean"] - sub["Accuracy_SD"]) * 100,
                           (sub["Accuracy_Mean"] + sub["Accuracy_SD"]) * 100, color=METHOD_COLORS[r], alpha=0.15)
        
    ax.axhline(25.0, color='gray', linestyle=':', label='Random Chance (25%)')
    ax.set_ylabel('Overall Accuracy (%)', fontsize=12, fontweight='bold')
    ax.set_xlabel('Velocity Sensor SNR Condition', fontsize=12, fontweight='bold')
    ax.set_title('E4 Velocity Noise Robustness: Clean vs 40 dB to 10 dB SNR', fontsize=13, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(v_labels, fontsize=11)
    ax.set_ylim(20, 102)
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(loc='upper right', frameon=True)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "E4_velocity_robustness.png")
    fig.savefig(FIGURES_DIR / "E4_velocity_robustness.pdf")
    plt.close(fig)
    
    # Figure 2: Position Robustness Curve (Clean, 0.01 deg, 0.05 deg, 0.20 deg)
    p_conds = ["clean", "position_0.01deg", "position_0.05deg", "position_0.2deg"]
    p_labels = ["Clean (0°)", "0.01° (0.17 mrad)", "0.05° (0.87 mrad)", "0.20° (3.49 mrad)"]
    
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(p_conds))
    for r in reps:
        sub = df_t11[df_t11["rep_key"] == r].set_index("Condition").loc[p_conds]
        ax.plot(x, sub["Accuracy_Mean"] * 100, marker='s', linewidth=2.5, label=METHOD_LABELS[r], color=METHOD_COLORS[r])
        ax.fill_between(x, (sub["Accuracy_Mean"] - sub["Accuracy_SD"]) * 100,
                           (sub["Accuracy_Mean"] + sub["Accuracy_SD"]) * 100, color=METHOD_COLORS[r], alpha=0.15)
        
    ax.set_ylabel('Overall Accuracy (%)', fontsize=12, fontweight='bold')
    ax.set_xlabel('Position Sensor Noise Standard Deviation', fontsize=12, fontweight='bold')
    ax.set_title('E4 Position Noise Robustness: Clean vs 0.01° to 0.20°', fontsize=13, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(p_labels, fontsize=10)
    ax.set_ylim(40, 102)
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(loc='lower left', frameon=True)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "E4_position_robustness.png")
    fig.savefig(FIGURES_DIR / "E4_position_robustness.pdf")
    plt.close(fig)
    
    # Figure 3: Combined Robustness (Clean, 40dB, 40dB+0.01deg, 40dB+0.05deg, 40dB+0.20deg)
    c_conds = ["clean", "velocity_40dB", "combined_40dB_0.01deg", "combined_40dB_0.05deg", "combined_40dB_0.2deg"]
    c_labels = ["Clean", "40 dB Only", "40 dB + 0.01°", "40 dB + 0.05°", "40 dB + 0.20°"]
    
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(c_conds))
    w = 0.18
    for i, r in enumerate(reps):
        sub = df_t11[df_t11["rep_key"] == r].set_index("Condition").loc[c_conds]
        pos = x + (i - 1.5) * w
        ax.bar(pos, sub["Accuracy_Mean"] * 100, w, yerr=sub["Accuracy_SD"] * 100, capsize=3,
               label=METHOD_LABELS[r], color=METHOD_COLORS[r], alpha=0.85, edgecolor='black')
        
    ax.set_ylabel('Overall Accuracy (%)', fontsize=12, fontweight='bold')
    ax.set_title('E4 Combined Velocity & Position Noise Robustness', fontsize=13, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(c_labels, fontsize=10)
    ax.set_ylim(20, 102)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    ax.legend(loc='upper right', frameon=True)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "E4_combined_robustness.png")
    fig.savefig(FIGURES_DIR / "E4_combined_robustness.pdf")
    plt.close(fig)
    
    # Figure 4: Per-Class Robustness Breakdown (Clean vs Pos 0.05 vs Vel 40dB)
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), sharey=True)
    comp_conds = ["clean", "position_0.05deg", "velocity_40dB"]
    comp_labels = ["Clean", "Pos 0.05°", "Vel 40 dB"]
    
    for idx, c in enumerate(CLASS_NAMES):
        ax = axes[idx // 2, idx % 2]
        x = np.arange(len(comp_conds))
        w = 0.18
        for i, r in enumerate(reps):
            sub = df_t12[(df_t12["rep_key"] == r) & (df_t12["Class"] == c)].set_index("Condition").loc[comp_conds]
            pos = x + (i - 1.5) * w
            ax.bar(pos, sub["Recall_Mean"] * 100, w, yerr=sub["Recall_SD"] * 100, capsize=3,
                   label=METHOD_LABELS[r], color=METHOD_COLORS[r], alpha=0.85, edgecolor='black')
            
        ax.set_title(f'Class: {c}', fontsize=12, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(comp_labels, fontsize=10)
        ax.grid(axis='y', linestyle='--', alpha=0.5)
        if idx % 2 == 0:
            ax.set_ylabel('Class Recall (%)', fontsize=11)
        if idx == 0:
            ax.legend(loc='upper right', fontsize=9)
            
    fig.suptitle('E4 Per-Class Recall Degradation Under Position vs Velocity Noise', fontsize=14, fontweight='bold')
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "E4_per_class_robustness.png")
    fig.savefig(FIGURES_DIR / "E4_per_class_robustness.pdf")
    plt.close(fig)
    
    # Figure 5: Binary FAR vs MDR Under Noise
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    x = np.arange(len(CONDITIONS_ORDER))
    for r in reps:
        sub = df_t11[df_t11["rep_key"] == r].set_index("Condition").loc[CONDITIONS_ORDER]
        ax1.plot(x, sub["False_Alarm_Rate_Mean"] * 100, marker='o', linewidth=2, label=METHOD_LABELS[r], color=METHOD_COLORS[r])
        ax2.plot(x, sub["Missed_Detection_Rate_Mean"] * 100, marker='s', linewidth=2, label=METHOD_LABELS[r], color=METHOD_COLORS[r])
        
    cond_short = ["Clean", "P0.01", "P0.05", "P0.20", "V40", "V30", "V20", "V10", "Comb.01", "Comb.05", "Comb.20"]
    ax1.set_ylabel('False Alarm Rate (%)', fontsize=11, fontweight='bold')
    ax1.set_title('False Alarm Rate on Nominal Runs', fontsize=11, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(cond_short, rotation=35, ha='right', fontsize=9)
    ax1.grid(True, linestyle='--', alpha=0.5)
    ax1.legend(loc='upper left')
    
    ax2.set_ylabel('Missed Detection Rate (%)', fontsize=11, fontweight='bold')
    ax2.set_title('Missed Detection Rate on Fault Runs', fontsize=11, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(cond_short, rotation=35, ha='right', fontsize=9)
    ax2.grid(True, linestyle='--', alpha=0.5)
    ax2.legend(loc='upper left')
    
    fig.suptitle('E4 Binary Diagnostic Error Rates Across All 10 Noise Conditions', fontsize=13, fontweight='bold')
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "E4_binary_far_mdr.png")
    fig.savefig(FIGURES_DIR / "E4_binary_far_mdr.pdf")
    plt.close(fig)
    
    # Figure 6: Noise x Severity Heatmap for velocity_40dB
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)
    for idx, fault in enumerate(faults):
        ax = axes[idx]
        bins = sev_bins[fault]
        sub = df_t13[(df_t13["Condition"] == "velocity_40dB") & (df_t13["Fault_Class"] == fault)]
        piv = sub.pivot(index="rep_key", columns="Severity_Bin", values="Recall_Mean").reindex(index=reps, columns=bins) * 100
        
        im = ax.imshow(piv.values, cmap='YlOrRd_r', vmin=0, vmax=100)
        ax.set_title(f'{fault} Recall (%) at 40 dB SNR', fontsize=12, fontweight='bold')
        ax.set_xticks(range(len(bins)))
        ax.set_xticklabels(bins, rotation=25, ha='right', fontsize=9)
        if idx == 0:
            ax.set_yticks(range(len(reps)))
            ax.set_yticklabels([METHOD_LABELS[r] for r in reps], fontsize=10, fontweight='bold')
        else:
            ax.set_yticks([])
            
        for r_i in range(len(reps)):
            for c_i in range(len(bins)):
                val = piv.values[r_i, c_i]
                color = 'white' if val < 50 else 'black'
                ax.text(c_i, r_i, f"{val:.1f}%", ha='center', va='center', color=color, fontsize=9.5)
                
    fig.subplots_adjust(right=0.9)
    cbar_ax = fig.add_axes([0.92, 0.15, 0.02, 0.7])
    fig.colorbar(im, cax=cbar_ax, label='Recall (%)')
    fig.suptitle('E4 Severity x Noise: Diagnostic Recall Under 40 dB Velocity Noise', fontsize=13, fontweight='bold')
    fig.savefig(FIGURES_DIR / "E4_noise_x_severity_heatmap.png", bbox_inches='tight')
    fig.savefig(FIGURES_DIR / "E4_noise_x_severity_heatmap.pdf", bbox_inches='tight')
    plt.close(fig)
    
    # Figure 7: Confusion Matrices at velocity_40dB (for each of the 4 CWT methods)
    for r in reps:
        sub_v40 = full_df[(full_df["e4_condition"] == "velocity_40dB") & (full_df["representation"] == r)]
        cm = confusion_matrix(sub_v40["label"], sub_v40["prediction"], labels=[0, 1, 2, 3])
        cm_norm = cm.astype(float) / cm.sum(axis=1, keepdims=True) * 100
        
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
        ax.set_title(f'E4 Confusion Matrix (Vel 40 dB): {METHOD_LABELS[r]}\n(Pooled 5 seeds, N=15,000 predictions)', fontsize=11, fontweight='bold')
        
        for row_i in range(4):
            for col_i in range(4):
                val = cm_norm[row_i, col_i]
                cnt = cm[row_i, col_i]
                color = 'white' if val > 50 else 'black'
                ax.text(col_i, row_i, f"{val:.1f}%\n({cnt:,})", ha='center', va='center', color=color, fontsize=9)
                
        fig.tight_layout()
        fig.savefig(FIGURES_DIR / f"E4_40dB_confusion_{r}.png")
        fig.savefig(FIGURES_DIR / f"E4_40dB_confusion_{r}.pdf")
        plt.close(fig)
        
    # Figure 8: Predicted Class Destination Under 40 dB (Where do predictions go?)
    fig, axes = plt.subplots(1, 4, figsize=(16, 4.5), sharey=True)
    for idx, r in enumerate(reps):
        ax = axes[idx]
        sub_v40 = full_df[(full_df["e4_condition"] == "velocity_40dB") & (full_df["representation"] == r)]
        crosstab = pd.crosstab(sub_v40["fault_class"], sub_v40["prediction_class"], normalize="index").reindex(index=CLASS_NAMES, columns=CLASS_NAMES, fill_value=0) * 100
        
        bottom = np.zeros(len(CLASS_NAMES))
        palette = {"Nominal": "#1f77b4", "LoE": "#ff7f0e", "Friction": "#d62728", "Vibration": "#2ca02c"}
        for pred_c in CLASS_NAMES:
            values = crosstab[pred_c].values
            ax.bar(CLASS_NAMES, values, bottom=bottom, label=pred_c, color=palette[pred_c], alpha=0.85, edgecolor='black')
            bottom += values
            
        ax.set_title(METHOD_LABELS[r], fontsize=11, fontweight='bold')
        ax.set_ylim(0, 100)
        ax.grid(axis='y', linestyle='--', alpha=0.5)
        if idx == 0:
            ax.set_ylabel('Predicted Class Destination (%)', fontsize=11)
            ax.legend(title='Predicted As', loc='upper right', fontsize=8.5)
            
    fig.suptitle('E4 Velocity 40 dB Collapse Destination Breakdown Across True Classes', fontsize=13, fontweight='bold')
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "E4_predicted_class_destination.png")
    fig.savefig(FIGURES_DIR / "E4_predicted_class_destination.pdf")
    plt.close(fig)
    
    # Figure 9: Clean-to-Noise Accuracy Deltas (Impact of Each Perturbation)
    fig, ax = plt.subplots(figsize=(11, 5))
    noise_conds = CONDITIONS_ORDER[1:]
    x = np.arange(len(noise_conds))
    w = 0.18
    
    for i, r in enumerate(reps):
        clean_acc = df_t11[(df_t11["rep_key"] == r) & (df_t11["Condition"] == "clean")]["Accuracy_Mean"].values[0] * 100
        deltas = []
        for cond in noise_conds:
            cond_acc = df_t11[(df_t11["rep_key"] == r) & (df_t11["Condition"] == cond)]["Accuracy_Mean"].values[0] * 100
            deltas.append(cond_acc - clean_acc)
        pos = x + (i - 1.5) * w
        ax.bar(pos, deltas, w, label=METHOD_LABELS[r], color=METHOD_COLORS[r], alpha=0.85, edgecolor='black')
        
    ax.axhline(0, color='black', linewidth=1)
    ax.set_ylabel('Accuracy Difference vs Separate E0 Clean Pass (pp)', fontsize=11, fontweight='bold')
    ax.set_title('E4 Perturbation Accuracy Minus Separately Evaluated E0 Clean', fontsize=13, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(cond_short[1:], rotation=30, ha='right', fontsize=9.5)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    ax.legend(loc='lower left', frameon=True)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "E4_clean_to_noise_deltas.png")
    fig.savefig(FIGURES_DIR / "E4_clean_to_noise_deltas.pdf")
    plt.close(fig)
    
    print("E4 Sensor Noise Forensic Analysis Complete.")

def refresh_provenance_and_delta_figure():
    """Narrow metadata refresh without recalculating the frozen E4 metrics."""
    for name in ["T11_E4_overall_noise.csv", "T12_E4_per_class_noise.csv",
                 "T13_E4_severity_noise.csv"]:
        path = TABLES_DIR / name
        table = pd.read_csv(path)
        expected = np.where(table["Condition"].eq("clean"), "E0_CANONICAL", "E4_CANONICAL")
        if "Evaluation_Source" in table:
            assert np.array_equal(table["Evaluation_Source"].to_numpy(), expected)
        else:
            table.insert(1, "Evaluation_Source", expected)
            table.to_csv(path, index=False)
    table = pd.read_csv(TABLES_DIR / "T11_E4_overall_noise.csv")
    fig, ax = plt.subplots(figsize=(11, 5))
    noise_conds = CONDITIONS_ORDER[1:]
    x = np.arange(len(noise_conds))
    width = 0.18
    for i, rep in enumerate(["shape_cwt", "torque_cwt", "gmo_cwt", "energy_cwt"]):
        rows = table[table["rep_key"] == rep].set_index("Condition")
        clean = float(rows.loc["clean", "Accuracy_Mean"])
        assert rows.loc["clean", "Evaluation_Source"] == "E0_CANONICAL"
        delta = [(float(rows.loc[cond, "Accuracy_Mean"]) - clean) * 100 for cond in noise_conds]
        ax.bar(x + (i - 1.5) * width, delta, width, label=METHOD_LABELS[rep], color=METHOD_COLORS[rep])
    ax.axhline(0, color="black", linewidth=1)
    ax.set_ylabel("Accuracy Difference vs Separate E0 Clean Pass (pp)")
    ax.set_title("E4 Perturbation Accuracy Minus Separately Evaluated E0 Clean")
    ax.set_xticks(x)
    ax.set_xticklabels(noise_conds, rotation=35, ha="right")
    ax.legend()
    ax.grid(axis="y", alpha=0.35)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "E4_clean_to_noise_deltas.png")
    fig.savefig(FIGURES_DIR / "E4_clean_to_noise_deltas.pdf")
    plt.close(fig)


if __name__ == "__main__":
    if "--provenance-only" in sys.argv:
        refresh_provenance_and_delta_figure()
    else:
        analyze_e4()
