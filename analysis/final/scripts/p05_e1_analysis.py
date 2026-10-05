import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

ROOT = Path(r"C:\Users\Johnny\Desktop\KINOVA_FINAL_ANALYSIS_ANTIGRAVITY")
DERIVED_DIR = ROOT / "derived"
TABLES_DIR = ROOT / "tables"
FIGURES_DIR = ROOT / "figures" / "E1"
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

FAULT_CLASSES = ["LoE", "Friction", "Vibration"]
FAULTS_BINS_ORDER = {
    "LoE": ["[0.02, 0.05)", "[0.05, 0.10)", "[0.10, 0.20)", "[0.20, 0.30]"],
    "Friction": ["[0.02, 0.10)", "[0.10, 0.30)", "[0.30, 0.75)", "[0.75, 1.50]"],
    "Vibration": ["[0.10, 0.50)", "[0.50, 1.00)", "[1.00, 1.75)", "[1.75, 2.50]"]
}

SEVERITY_UNITS = {
    "LoE": "s_LoE (fractional torque loss)",
    "Friction": "s_Friction (relative to nominal Fc)",
    "Vibration": "A_d (amplitude, N*m)"
}

def analyze_e1():
    print("--- Running E1 Severity Forensic Analysis ---")
    df = pd.read_parquet(DERIVED_DIR / "canonical_e0_primary.parquet")
    
    reps = ["shape_cwt", "torque_cwt", "gmo_cwt", "energy_cwt", "shape_temporal", "shape_fft"]
    seeds = [1729, 2027, 4099, 7919, 104729]
    
    t06_records = []
    
    for fault in FAULT_CLASSES:
        bins = FAULTS_BINS_ORDER[fault]
        for b in bins:
            for r in reps:
                # across 5 seeds
                recalls = []
                binary_detections = []
                missed_rates = []
                confused_rates = []
                dest_nominal = []
                dest_other_fault = []
                
                for s in seeds:
                    sub = df[(df["representation"] == r) & (df["seed"] == s) & (df["fault_class"] == fault) & (df["severity_bin"] == b)]
                    n_samples = len(sub)
                    if n_samples == 0:
                        continue
                    
                    # Multiclass recall
                    rec = (sub["prediction"] == sub["label"]).mean()
                    recalls.append(rec)
                    
                    # Binary detection (predicted != 0)
                    bin_det = (sub["prediction"] != 0).mean()
                    binary_detections.append(bin_det)
                    
                    # Missed detection (predicted == 0)
                    md = (sub["prediction"] == 0).mean()
                    missed_rates.append(md)
                    
                    # Mechanism confusion (predicted != 0 and predicted != label)
                    mc = ((sub["prediction"] != 0) & (sub["prediction"] != sub["label"])).mean()
                    confused_rates.append(mc)
                    
                    # Destination
                    dest_nom = (sub["prediction_class"] == "Nominal").mean()
                    dest_oth = ((sub["prediction_class"] != "Nominal") & (sub["prediction_class"] != fault)).mean()
                    dest_nominal.append(dest_nom)
                    dest_other_fault.append(dest_oth)
                    
                t06_records.append({
                    "Fault_Class": fault,
                    "Severity_Bin": b,
                    "N_per_Seed": n_samples,
                    "Representation": METHOD_LABELS[r],
                    "rep_key": r,
                    "Multiclass_Recall_Mean": np.mean(recalls),
                    "Multiclass_Recall_SD": np.std(recalls, ddof=1),
                    "Binary_Detection_Mean": np.mean(binary_detections),
                    "Binary_Detection_SD": np.std(binary_detections, ddof=1),
                    "Missed_Detection_Mean": np.mean(missed_rates),
                    "Missed_Detection_SD": np.std(missed_rates, ddof=1),
                    "Mechanism_Confusion_Mean": np.mean(confused_rates),
                    "Mechanism_Confusion_SD": np.std(confused_rates, ddof=1),
                    "Destination_Nominal_Mean": np.mean(dest_nominal),
                    "Destination_OtherFault_Mean": np.mean(dest_other_fault)
                })
                
    df_t06 = pd.DataFrame(t06_records)
    df_t06.to_csv(TABLES_DIR / "T06_E1_severity.csv", index=False)
    print("Saved tables/T06_E1_severity.csv")
    
    # 2. Plotting per fault
    print("Generating E1 Figures...")
    for fault in FAULT_CLASSES:
        bins = FAULTS_BINS_ORDER[fault]
        x = np.arange(len(bins))
        
        # Figure A: Multiclass Recall vs Severity
        fig, ax = plt.subplots(figsize=(8.5, 5))
        for r in reps:
            sub = df_t06[(df_t06["Fault_Class"] == fault) & (df_t06["rep_key"] == r)]
            # align bins
            sub = sub.set_index("Severity_Bin").loc[bins].reset_index()
            y = sub["Multiclass_Recall_Mean"] * 100
            yerr = sub["Multiclass_Recall_SD"] * 100
            ax.errorbar(x, y, yerr=yerr, marker='o', linewidth=2, capsize=4, label=METHOD_LABELS[r], color=METHOD_COLORS[r])
            
        ax.set_ylabel(f'{fault} Recall (%)', fontsize=12)
        ax.set_xlabel(f'Severity Stratum [{SEVERITY_UNITS[fault]}]', fontsize=11, fontweight='bold')
        ax.set_title(f'E1 {fault}: Multiclass Recall vs Severity (Test Set, 5 Seeds)', fontsize=12, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(bins, fontsize=10)
        ax.set_ylim(-2, 104)
        ax.grid(True, linestyle='--', alpha=0.5)
        ax.legend(loc='lower right' if fault != 'Vibration' else 'lower left', frameon=True)
        fig.tight_layout()
        fig.savefig(FIGURES_DIR / f"E1_{fault}_multiclass_recall_vs_severity.png")
        fig.savefig(FIGURES_DIR / f"E1_{fault}_multiclass_recall_vs_severity.pdf")
        plt.close(fig)
        
        # Figure B: Binary Detection vs Severity
        fig, ax = plt.subplots(figsize=(8.5, 5))
        for r in reps:
            sub = df_t06[(df_t06["Fault_Class"] == fault) & (df_t06["rep_key"] == r)]
            sub = sub.set_index("Severity_Bin").loc[bins].reset_index()
            y = sub["Binary_Detection_Mean"] * 100
            yerr = sub["Binary_Detection_SD"] * 100
            ax.errorbar(x, y, yerr=yerr, marker='s', linewidth=2, capsize=4, label=METHOD_LABELS[r], color=METHOD_COLORS[r])
            
        ax.set_ylabel(f'Binary Fault Detection Rate (%)', fontsize=12)
        ax.set_xlabel(f'Severity Stratum [{SEVERITY_UNITS[fault]}]', fontsize=11, fontweight='bold')
        ax.set_title(f'E1 {fault}: Binary Fault Detection vs Severity (Test Set, 5 Seeds)', fontsize=12, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(bins, fontsize=10)
        ax.set_ylim(-2, 104)
        ax.grid(True, linestyle='--', alpha=0.5)
        ax.legend(loc='lower right' if fault != 'Vibration' else 'lower left', frameon=True)
        fig.tight_layout()
        fig.savefig(FIGURES_DIR / f"E1_{fault}_binary_detection_vs_severity.png")
        fig.savefig(FIGURES_DIR / f"E1_{fault}_binary_detection_vs_severity.pdf")
        plt.close(fig)
        
        # Figure C: Misclassification Destination (Nominal vs Other Fault Class) for the 4 primary CWT methods
        fig, axes = plt.subplots(2, 2, figsize=(11, 8), sharey=True)
        cwt_reps = ["shape_cwt", "torque_cwt", "gmo_cwt", "energy_cwt"]
        w = 0.35
        for idx, r in enumerate(cwt_reps):
            ax = axes[idx // 2, idx % 2]
            sub = df_t06[(df_t06["Fault_Class"] == fault) & (df_t06["rep_key"] == r)]
            sub = sub.set_index("Severity_Bin").loc[bins].reset_index()
            
            p_nom = sub["Destination_Nominal_Mean"] * 100
            p_oth = sub["Destination_OtherFault_Mean"] * 100
            
            ax.bar(x - w/2, p_nom, w, label='Missed (Nominal)', color='#d62728', alpha=0.85, edgecolor='black')
            ax.bar(x + w/2, p_oth, w, label='Confused (Other Fault)', color='#ff7f0e', alpha=0.85, edgecolor='black')
            
            ax.set_title(f'{METHOD_LABELS[r]}', fontsize=11, fontweight='bold')
            ax.set_xticks(x)
            ax.set_xticklabels(bins, fontsize=9)
            ax.grid(axis='y', linestyle='--', alpha=0.5)
            if idx % 2 == 0:
                ax.set_ylabel('Error Destination (%)', fontsize=10)
            if idx // 2 == 1:
                ax.set_xlabel(f'Severity [{SEVERITY_UNITS[fault]}]', fontsize=9)
            if idx == 0:
                ax.legend(loc='upper right', fontsize=9)
                
        fig.suptitle(f'E1 {fault}: Misclassification Destination Breakdown (Missed vs Confused)', fontsize=13, fontweight='bold')
        fig.tight_layout()
        fig.savefig(FIGURES_DIR / f"E1_{fault}_misclassification_destination.png")
        fig.savefig(FIGURES_DIR / f"E1_{fault}_misclassification_destination.pdf")
        plt.close(fig)
        
    # Figure D: Global Severity Heatmap across all faults and methods
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.5), sharey=True)
    for idx, fault in enumerate(FAULT_CLASSES):
        ax = axes[idx]
        bins = FAULTS_BINS_ORDER[fault]
        sub = df_t06[df_t06["Fault_Class"] == fault]
        piv = sub.pivot(index="rep_key", columns="Severity_Bin", values="Multiclass_Recall_Mean")
        piv = piv.reindex(index=reps, columns=bins) * 100
        
        im = ax.imshow(piv.values, cmap='YlGnBu', vmin=0, vmax=100)
        ax.set_title(f'{fault} Recall (%)', fontsize=12, fontweight='bold')
        ax.set_xticks(range(len(bins)))
        ax.set_xticklabels(bins, rotation=25, ha='right', fontsize=9)
        if idx == 0:
            ax.set_yticks(range(len(reps)))
            ax.set_yticklabels([METHOD_LABELS[r] for r in reps], fontsize=10, fontweight='bold')
        else:
            ax.set_yticks([])
        ax.set_xlabel(f'Severity Stratum', fontsize=10)
        
        for r_i in range(len(reps)):
            for c_i in range(len(bins)):
                val = piv.values[r_i, c_i]
                color = 'white' if val > 60 else 'black'
                ax.text(c_i, r_i, f"{val:.1f}%", ha='center', va='center', color=color, fontsize=9)
                
    fig.subplots_adjust(right=0.9)
    cbar_ax = fig.add_axes([0.92, 0.15, 0.02, 0.7])
    cbar = fig.colorbar(im, cax=cbar_ax)
    cbar.set_label('Multiclass Recall (%)', fontsize=11)
    fig.suptitle('E1 Global Severity Sensitivity Heatmap (Mean across 5 Seeds)', fontsize=14, fontweight='bold')
    fig.savefig(FIGURES_DIR / "E1_severity_heatmap.png", bbox_inches='tight')
    fig.savefig(FIGURES_DIR / "E1_severity_heatmap.pdf", bbox_inches='tight')
    plt.close(fig)
    
    print("E1 Severity Analysis Complete.")

if __name__ == "__main__":
    analyze_e1()
