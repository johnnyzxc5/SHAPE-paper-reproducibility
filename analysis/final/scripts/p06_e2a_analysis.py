import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

ROOT = Path(r"C:\Users\Johnny\Desktop\KINOVA_FINAL_ANALYSIS_ANTIGRAVITY")
DERIVED_DIR = ROOT / "derived"
TABLES_DIR = ROOT / "tables"
FIGURES_DIR = ROOT / "figures" / "E2A"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300

METHOD_LABELS = {
    "shape_cwt": "SHAPE-CWT",
    "torque_cwt": "Torque-CWT",
    "gmo_cwt": "GMO-CWT",
    "energy_cwt": "EO-CWT",
    "shape_temporal": "SHAPE-Temporal",
    "shape_fft": "SHAPE-FFT"
}

FREQ_LABELS = ["[2, 5)", "[5, 10)", "[10, 15)", "[15, 20)", "[20, 25)", "[25, 30]"]
AMP_LABELS = ["[0.1, 0.5)", "[0.5, 1.0)", "[1.0, 1.75)", "[1.75, 2.50]"]

def analyze_e2a():
    print("--- Running E2-A Vibration Grid Analysis ---")
    df = pd.read_parquet(DERIVED_DIR / "canonical_e0_primary.parquet")
    
    # Filter to Vibration test runs
    vib = df[df["fault_class"] == "Vibration"].copy()
    
    reps = ["shape_cwt", "torque_cwt", "gmo_cwt", "energy_cwt", "shape_temporal", "shape_fft"]
    seeds = [1729, 2027, 4099, 7919, 104729]
    
    # Check N per cell
    sample_sub = vib[(vib["representation"] == "shape_cwt") & (vib["seed"] == 1729)]
    cell_counts = sample_sub.groupby(["vibration_amp_bin", "vibration_freq_bin"]).size().unstack(fill_value=0)
    print("Cell counts (N per seed across 24 cells):")
    print(cell_counts)
    
    t07_records = []
    
    for a_bin in AMP_LABELS:
        for f_bin in FREQ_LABELS:
            n_cell = int(cell_counts.loc[a_bin, f_bin]) if (a_bin in cell_counts.index and f_bin in cell_counts.columns) else 0
            for r in reps:
                recalls = []
                binary_detections = []
                for s in seeds:
                    cell_sub = vib[(vib["representation"] == r) & (vib["seed"] == s) & 
                                   (vib["vibration_amp_bin"] == a_bin) & (vib["vibration_freq_bin"] == f_bin)]
                    if len(cell_sub) > 0:
                        rec = (cell_sub["prediction"] == cell_sub["label"]).mean()
                        bin_det = (cell_sub["prediction"] != 0).mean()
                        recalls.append(rec)
                        binary_detections.append(bin_det)
                
                t07_records.append({
                    "Amplitude_Bin": a_bin,
                    "Frequency_Bin": f_bin,
                    "N_per_Seed": n_cell,
                    "Representation": METHOD_LABELS[r],
                    "rep_key": r,
                    "Vibration_Recall_Mean": np.mean(recalls) if recalls else np.nan,
                    "Vibration_Recall_SD": np.std(recalls, ddof=1) if len(recalls)>1 else np.nan,
                    "Fault_Detection_Mean": np.mean(binary_detections) if binary_detections else np.nan,
                    "Fault_Detection_SD": np.std(binary_detections, ddof=1) if len(binary_detections)>1 else np.nan
                })
                
    df_t07 = pd.DataFrame(t07_records)
    df_t07.to_csv(TABLES_DIR / "T07_E2A_amplitude_frequency.csv", index=False)
    print("Saved tables/T07_E2A_amplitude_frequency.csv")
    
    # 2. Plotting heatmaps
    print("Generating E2-A Figures...")
    
    # Heatmaps for each method: Vibration Recall & Binary Fault Detection
    for r in reps:
        sub = df_t07[df_t07["rep_key"] == r]
        piv_rec = sub.pivot(index="Amplitude_Bin", columns="Frequency_Bin", values="Vibration_Recall_Mean").reindex(index=AMP_LABELS[::-1], columns=FREQ_LABELS) * 100
        piv_det = sub.pivot(index="Amplitude_Bin", columns="Frequency_Bin", values="Fault_Detection_Mean").reindex(index=AMP_LABELS[::-1], columns=FREQ_LABELS) * 100
        
        # A: Recall heatmap
        fig, ax = plt.subplots(figsize=(8, 5))
        im = ax.imshow(piv_rec.values, cmap='Blues', vmin=40, vmax=100)
        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label('Vibration Recall (%)', fontsize=10)
        
        ax.set_xticks(range(len(FREQ_LABELS)))
        ax.set_yticks(range(len(AMP_LABELS)))
        ax.set_xticklabels(FREQ_LABELS, fontsize=10)
        ax.set_yticklabels(AMP_LABELS[::-1], fontsize=10)
        ax.set_xlabel('Vibration Frequency Bin (Hz)', fontsize=11, fontweight='bold')
        ax.set_ylabel('Vibration Amplitude Bin (N*m)', fontsize=11, fontweight='bold')
        ax.set_title(f'E2-A Vibration Recall Grid: {METHOD_LABELS[r]}\n(Pooled 5 Seeds, N=750 runs per seed)', fontsize=11, fontweight='bold')
        
        for row_i in range(len(AMP_LABELS)):
            for col_i in range(len(FREQ_LABELS)):
                a_name = AMP_LABELS[::-1][row_i]
                f_name = FREQ_LABELS[col_i]
                n_val = cell_counts.loc[a_name, f_name] if (a_name in cell_counts.index and f_name in cell_counts.columns) else 0
                val = piv_rec.values[row_i, col_i]
                color = 'white' if val > 75 else 'black'
                ax.text(col_i, row_i, f"{val:.1f}%\n(N={n_val})", ha='center', va='center', color=color, fontsize=8.5)
                
        fig.tight_layout()
        fig.savefig(FIGURES_DIR / f"E2A_{r}_vibration_recall_heatmap.png")
        fig.savefig(FIGURES_DIR / f"E2A_{r}_vibration_recall_heatmap.pdf")
        plt.close(fig)
        
        # B: Binary detection heatmap
        fig, ax = plt.subplots(figsize=(8, 5))
        im = ax.imshow(piv_det.values, cmap='Greens', vmin=40, vmax=100)
        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label('Fault Detection Rate (%)', fontsize=10)
        
        ax.set_xticks(range(len(FREQ_LABELS)))
        ax.set_yticks(range(len(AMP_LABELS)))
        ax.set_xticklabels(FREQ_LABELS, fontsize=10)
        ax.set_yticklabels(AMP_LABELS[::-1], fontsize=10)
        ax.set_xlabel('Vibration Frequency Bin (Hz)', fontsize=11, fontweight='bold')
        ax.set_ylabel('Vibration Amplitude Bin (N*m)', fontsize=11, fontweight='bold')
        ax.set_title(f'E2-A Fault Detection Grid: {METHOD_LABELS[r]}\n(Anomaly detected as any fault)', fontsize=11, fontweight='bold')
        
        for row_i in range(len(AMP_LABELS)):
            for col_i in range(len(FREQ_LABELS)):
                a_name = AMP_LABELS[::-1][row_i]
                f_name = FREQ_LABELS[col_i]
                n_val = cell_counts.loc[a_name, f_name] if (a_name in cell_counts.index and f_name in cell_counts.columns) else 0
                val = piv_det.values[row_i, col_i]
                color = 'white' if val > 75 else 'black'
                ax.text(col_i, row_i, f"{val:.1f}%\n(N={n_val})", ha='center', va='center', color=color, fontsize=8.5)
                
        fig.tight_layout()
        fig.savefig(FIGURES_DIR / f"E2A_{r}_fault_detection_heatmap.png")
        fig.savefig(FIGURES_DIR / f"E2A_{r}_fault_detection_heatmap.pdf")
        plt.close(fig)

    # 3. Difference Heatmaps: SHAPE minus GMO, SHAPE minus Torque, SHAPE minus EO
    diff_pairs = [
        ("shape_cwt", "gmo_cwt", "SHAPE-CWT minus GMO-CWT", "E2A_diff_SHAPE_minus_GMO"),
        ("shape_cwt", "torque_cwt", "SHAPE-CWT minus Torque-CWT", "E2A_diff_SHAPE_minus_Torque"),
        ("shape_cwt", "energy_cwt", "SHAPE-CWT minus EO-CWT", "E2A_diff_SHAPE_minus_EO")
    ]
    
    for m1, m2, title_str, fname in diff_pairs:
        sub1 = df_t07[df_t07["rep_key"] == m1].pivot(index="Amplitude_Bin", columns="Frequency_Bin", values="Vibration_Recall_Mean").reindex(index=AMP_LABELS[::-1], columns=FREQ_LABELS) * 100
        sub2 = df_t07[df_t07["rep_key"] == m2].pivot(index="Amplitude_Bin", columns="Frequency_Bin", values="Vibration_Recall_Mean").reindex(index=AMP_LABELS[::-1], columns=FREQ_LABELS) * 100
        diff = sub1 - sub2
        
        fig, ax = plt.subplots(figsize=(8, 5))
        vmax = max(10.0, np.nanmax(np.abs(diff.values)))
        im = ax.imshow(diff.values, cmap='RdBu', vmin=-vmax, vmax=vmax)
        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.set_label('Delta Vibration Recall (%)', fontsize=10)
        
        ax.set_xticks(range(len(FREQ_LABELS)))
        ax.set_yticks(range(len(AMP_LABELS)))
        ax.set_xticklabels(FREQ_LABELS, fontsize=10)
        ax.set_yticklabels(AMP_LABELS[::-1], fontsize=10)
        ax.set_xlabel('Vibration Frequency Bin (Hz)', fontsize=11, fontweight='bold')
        ax.set_ylabel('Vibration Amplitude Bin (N*m)', fontsize=11, fontweight='bold')
        ax.set_title(f'E2-A Difference Grid: {title_str}\n(Positive = Method 1 higher)', fontsize=11, fontweight='bold')
        
        for row_i in range(len(AMP_LABELS)):
            for col_i in range(len(FREQ_LABELS)):
                val = diff.values[row_i, col_i]
                color = 'white' if abs(val) > vmax*0.6 else 'black'
                ax.text(col_i, row_i, f"{val:+.1f}%", ha='center', va='center', color=color, fontsize=9, fontweight='bold')
                
        fig.tight_layout()
        fig.savefig(FIGURES_DIR / f"{fname}.png")
        fig.savefig(FIGURES_DIR / f"{fname}.pdf")
        plt.close(fig)
        
    print("E2-A Vibration Grid Analysis Complete.")

if __name__ == "__main__":
    analyze_e2a()
