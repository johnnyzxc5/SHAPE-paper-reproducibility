import sys
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

ROOT = Path(r"C:\Users\Johnny\Desktop\KINOVA_FINAL_ANALYSIS_ANTIGRAVITY")
DERIVED_DIR = ROOT / "derived"
TABLES_DIR = ROOT / "tables"
FIGURES_DIR = ROOT / "figures" / "COMPUTE"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

RUNS_DIR = Path(r"C:\KinovaProduction\AI\runs")
BENCHMARKS_DIR = Path(r"C:\KinovaProduction\AI\benchmarks")

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

def analyze_computational_cost():
    print("--- Running Computational Cost Forensic Analysis ---")
    
    reps = ["shape_cwt", "torque_cwt", "gmo_cwt", "energy_cwt", "shape_temporal", "shape_fft"]
    seeds = [1729, 2027, 4099, 7919, 104729]
    
    # 1. Training Cost Table T14
    t14_records = []
    for r in reps:
        for s in seeds:
            run_p = RUNS_DIR / r / f"seed_{s}"
            with open(run_p / "TRAINING_COMPLETE.json", "r") as f:
                tc = json.load(f)
            with open(run_p / "provenance.json", "r") as f:
                prov = json.load(f)
            with open(run_p / "config.resolved.json", "r") as f:
                cfg = json.load(f)
                
            elapsed = tc["elapsed_seconds"]
            epochs = tc["epochs_completed"]
            best_ep = tc["best_epoch"]
            sec_per_epoch = elapsed / epochs if epochs > 0 else np.nan
            
            t14_records.append({
                "Representation": METHOD_LABELS[r],
                "rep_key": r,
                "Seed": s,
                "Elapsed_Seconds": elapsed,
                "Training_Minutes": elapsed / 60.0,
                "Epochs_Completed": epochs,
                "Best_Epoch": best_ep,
                "Seconds_per_Epoch": sec_per_epoch,
                "Best_Val_Loss": tc.get("best_validation_loss", np.nan),
                "Best_Val_Macro_F1": tc.get("best_validation_macro_f1", np.nan),
                "Parameter_Count": prov.get("parameter_count", np.nan),
                "Batch_Size": cfg["training"]["batch_size"],
                "Workers": cfg["data"]["num_workers"],
                "AMP": cfg["training"]["amp"],
                "GPU": prov["environment"]["gpu"]
            })
            
    df_t14 = pd.DataFrame(t14_records)
    df_t14.to_csv(TABLES_DIR / "T14_training_cost.csv", index=False)
    print("Saved tables/T14_training_cost.csv")
    
    # Summary of Training Cost across seeds
    t14_summary = df_t14.groupby("Representation").agg({
        "Training_Minutes": ["mean", "std", "median", "min", "max"],
        "Seconds_per_Epoch": ["mean", "std", "median"],
        "Epochs_Completed": ["mean", "min", "max"],
        "Best_Epoch": ["mean", "median"]
    }).round(2)
    print("\n=== Training Cost Summary across Seeds ===")
    print(t14_summary)
    
    # 2. Training-step throughput benchmark. The source benchmark executes
    # forward, loss, backward, and optimizer.step() on PRIMARY/train.
    t15_records = []
    for r in reps:
        csv_p = BENCHMARKS_DIR / f"{r}.csv"
        json_p = BENCHMARKS_DIR / f"{r}.json"
        if csv_p.exists() and json_p.exists():
            df_b = pd.read_csv(csv_p)
            with open(json_p, "r") as f:
                b_meta = json.load(f)
            # Select the recorded batch_size=32, num_workers=4 microbenchmark.
            sub = df_b[(df_b["batch_size"] == 32) & (df_b["num_workers"] == 4)]
            if len(sub) == 0:
                raise ValueError(f"No batch-32, four-worker training-step benchmark for {r}: {csv_p}")
            row = sub.iloc[0]
            t15_records.append({
                "Representation": METHOD_LABELS[r],
                "rep_key": r,
                "Status": "MEASURED_TRAINING_STEP_BENCHMARK",
                "Stage": "TRAINING_STEP_THROUGHPUT",
                "Source_Split": "PRIMARY/train",
                "Benchmark_Steps": int(row["steps"]),
                "Benchmark_Samples": int(row["samples"]),
                "Batch_Size": int(row["batch_size"]),
                "Num_Workers": int(row["num_workers"]),
                "AMP": str(row["amp"]),
                "Samples_per_Second": float(row["samples_per_second"]),
                "Elapsed_Seconds": float(row["elapsed_seconds"]),
                "Peak_VRAM_GiB": float(row["peak_vram_gib"]),
                "GPU": b_meta["environment"]["gpu"],
                "Notes": "Forward, loss, backward, optimizer step; not an inference benchmark"
            })
        else:
            t15_records.append({
                "Representation": METHOD_LABELS[r],
                "rep_key": r,
                "Status": "NOT_MEASURED",
                "Stage": "TRAINING_STEP_THROUGHPUT",
                "Source_Split": "NOT_MEASURED",
                "Benchmark_Steps": np.nan,
                "Benchmark_Samples": np.nan,
                "Batch_Size": np.nan,
                "Num_Workers": np.nan,
                "AMP": "NOT_MEASURED",
                "Samples_per_Second": np.nan,
                "Elapsed_Seconds": np.nan,
                "Peak_VRAM_GiB": np.nan,
                "GPU": "NOT_MEASURED",
                "Notes": "No direct training-step throughput benchmark file"
            })
    df_t15 = pd.DataFrame(t15_records)
    df_t15.to_csv(TABLES_DIR / "T15_inference_benchmark.csv", index=False)
    print("Saved tables/T15_inference_benchmark.csv")
    
    # 3. Model complexity: parameter counts and checkpoint bytes come from
    # frozen run artifacts. The shape descriptors are representation metadata.
    t16_records = []
    shapes = {
        "shape_cwt": ("2D", "(224, 448)", 6),
        "torque_cwt": ("2D", "(224, 448)", 6),
        "gmo_cwt": ("2D", "(224, 448)", 6),
        "energy_cwt": ("2D", "(224, 448)", 1),
        "shape_temporal": ("1D", "(10001,)", 6),
        "shape_fft": ("1D", "(1001,)", 6),
    }
    for r in reps:
        counts = [json.loads((RUNS_DIR / r / f"seed_{s}" / "provenance.json").read_text())["parameter_count"] for s in seeds]
        assert len(set(counts)) == 1, f"Parameter counts differ across seeds: {r}"
        checkpoint = RUNS_DIR / r / "seed_1729" / "best.pt"
        checkpoint_bytes = checkpoint.stat().st_size
        fam, in_dim, ch = shapes[r]
        t16_records.append({
            "Representation": METHOD_LABELS[r],
            "rep_key": r,
            "Architecture_Family": fam,
            "Input_Dimensions": in_dim,
            "Input_Channels": ch,
            "Parameter_Count": counts[0],
            "Checkpoint_Seed": 1729,
            "Checkpoint_Size_Bytes": checkpoint_bytes,
            "Checkpoint_Size_MB": checkpoint_bytes / 1_000_000,
        })
    df_t16 = pd.DataFrame(t16_records)
    df_t16.to_csv(TABLES_DIR / "T16_model_complexity.csv", index=False)
    print("Saved tables/T16_model_complexity.csv")
    
    # 4. Cost evidence. No standalone residual or inference runtime exists.
    # Untraced profile summaries are intentionally withheld, never promoted
    # to measured averages by rerunning this generator.
    t17_records = []
    def cost_row(level, component, method, source, value, units, status, notes):
        t17_records.append({"Level": level, "Component": component, "Method": method,
                            "Evidence_Source": source, "Measured_Value": value,
                            "Units": units, "Type": status, "Notes": notes})
    cost_row("Level 1: Simulation", "Simulink Plant Simulation", "All (Shared)",
             "Untraced HDF5 /profile_json claim", "UNVERIFIED", "UNVERIFIED", "UNVERIFIED",
             "No reproducible file population, sample count, or aggregation path supplied")
    for component, method, note in [
        ("Torque Residual (r_tau)", "Torque-CWT", "Algebraic vector difference; standalone runtime unmeasured"),
        ("SHAPE Power Residual (r_SHAPE)", "SHAPE-CWT", "Algebraic port-power difference; standalone runtime unmeasured"),
        ("GMO Observer (r_GMO)", "GMO-CWT", "Dynamic observer; standalone runtime unmeasured"),
        ("Energy Observer (r_EO)", "EO-CWT", "Dynamic observer; standalone runtime unmeasured"),
        ("EO Incremental Cost (Shared)", "EO-CWT", "Shared-dynamics incremental runtime unmeasured"),
    ]:
        cost_row("Level 2: Residual", component, method, "compute_residuals.m structural code",
                 "NOT_MEASURED", "NOT_MEASURED", "NOT_MEASURED", note)
    for component, method in [
        ("Physical Normalization", "All (Shared)"),
        ("FFT Spectrum (1D)", "SHAPE-FFT"),
        ("CWT + 2D Rebinning", "CWT Methods"),
        ("HDF5 Serialization", "All (Shared)"),
    ]:
        cost_row("Level 3: Representation/Serialization", component, method,
                 "Untraced HDF5 /profile_json claim", "UNVERIFIED", "UNVERIFIED",
                 "UNVERIFIED", "No reproducible file population, sample count, or aggregation path supplied")
    shape_training = df_t14.loc[df_t14["rep_key"] == "shape_cwt", "Training_Minutes"]
    cost_row("Level 4: CNN Training", "Five-seed training wall-clock mean", "SHAPE-CWT",
             "TRAINING_COMPLETE.json via T14", shape_training.mean(), "minutes",
             "MEASURED", f"n=5 frozen seeds; SD={shape_training.std(ddof=1):.6f} minutes")
    shape_benchmark = df_t15.loc[df_t15["rep_key"] == "shape_cwt"].iloc[0]
    cost_row("Level 4: Training-step throughput", "Forward/backward/optimizer throughput", "SHAPE-CWT",
             "AI/benchmarks/shape_cwt.csv via T15", shape_benchmark["Samples_per_Second"],
             "samples / second", "MEASURED", "PRIMARY/train; 30 measured steps; batch 32; 960 processed samples")
    cost_row("Level 4: CNN Inference", "Inference Throughput", "All Methods",
             "No standalone inference benchmark", "NOT_MEASURED", "NOT_MEASURED",
             "NOT_MEASURED", "Training-step benchmark cannot be used as inference")
    df_t17 = pd.DataFrame(t17_records)
    df_t17.to_csv(TABLES_DIR / "T17_residual_cost_evidence.csv", index=False)
    print("Saved tables/T17_residual_cost_evidence.csv")
    
    # 5. Generate Figures
    print("Generating COMPUTE Figures...")
    
    # Figure 1: Training Time across seeds (Bar chart with scatter)
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(reps))
    t_means = [df_t14[df_t14["rep_key"] == r]["Training_Minutes"].mean() for r in reps]
    t_sds = [df_t14[df_t14["rep_key"] == r]["Training_Minutes"].std() for r in reps]
    
    bars = ax.bar(x, t_means, 0.45, yerr=t_sds, capsize=4, color=[METHOD_COLORS[r] for r in reps], alpha=0.85, edgecolor='black')
    for i, r in enumerate(reps):
        sub = df_t14[df_t14["rep_key"] == r]
        ax.scatter([x[i]] * len(sub), sub["Training_Minutes"], color='black', s=25, zorder=5)
        
    ax.set_ylabel('Total Training Time (Minutes)', fontsize=12, fontweight='bold')
    ax.set_title('Observed Training Duration (NVIDIA RTX 4090, 5 Seeds)', fontsize=13, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels([METHOD_LABELS[r] for r in reps], rotation=15, ha='right', fontsize=11)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "COMPUTE_training_time.png")
    fig.savefig(FIGURES_DIR / "COMPUTE_training_time.pdf")
    plt.close(fig)
    
    # Figure 2: Seconds per Epoch
    fig, ax = plt.subplots(figsize=(10, 5))
    spe_means = [df_t14[df_t14["rep_key"] == r]["Seconds_per_Epoch"].mean() for r in reps]
    spe_sds = [df_t14[df_t14["rep_key"] == r]["Seconds_per_Epoch"].std() for r in reps]
    ax.bar(x, spe_means, 0.45, yerr=spe_sds, capsize=4, color=[METHOD_COLORS[r] for r in reps], alpha=0.85, edgecolor='black')
    for i, r in enumerate(reps):
        sub = df_t14[df_t14["rep_key"] == r]
        ax.scatter([x[i]] * len(sub), sub["Seconds_per_Epoch"], color='black', s=25, zorder=5)
    ax.set_ylabel('Seconds per Completed Epoch', fontsize=12, fontweight='bold')
    ax.set_title('Average Epoch Duration During Training (14,000 Train Runs)', fontsize=13, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels([METHOD_LABELS[r] for r in reps], rotation=15, ha='right', fontsize=11)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "COMPUTE_seconds_per_epoch.png")
    fig.savefig(FIGURES_DIR / "COMPUTE_seconds_per_epoch.pdf")
    plt.close(fig)
    
    # Figure 3: Epochs completed & Best Epoch
    fig, ax = plt.subplots(figsize=(10, 5))
    w = 0.35
    be_means = [df_t14[df_t14["rep_key"] == r]["Best_Epoch"].mean() for r in reps]
    be_sds = [df_t14[df_t14["rep_key"] == r]["Best_Epoch"].std() for r in reps]
    ax.bar(x, be_means, w, yerr=be_sds, capsize=4, label='Best Validation Epoch', color='#2b5c8f', alpha=0.85, edgecolor='black')
    ax.axhline(50, color='red', linestyle='--', linewidth=1.5, label='Max Epochs (50)')
    for i, r in enumerate(reps):
        sub = df_t14[df_t14["rep_key"] == r]
        ax.scatter([x[i]] * len(sub), sub["Best_Epoch"], color='black', s=20, zorder=5)
    ax.set_ylabel('Epoch Index', fontsize=12, fontweight='bold')
    ax.set_title('Best Epoch Reached Prior to 50-Epoch Freeze', fontsize=13, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels([METHOD_LABELS[r] for r in reps], rotation=15, ha='right', fontsize=11)
    ax.set_ylim(0, 55)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    ax.legend(loc='lower right', frameon=True)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "COMPUTE_epochs_completed.png")
    fig.savefig(FIGURES_DIR / "COMPUTE_epochs_completed.pdf")
    plt.close(fig)
    
    # Figure 4: Performance vs Training Cost Trade-off
    df_e0_summary = pd.read_csv(TABLES_DIR / "T02_E0_overall.csv").set_index("rep_key")
    fig, ax = plt.subplots(figsize=(9, 5.5))
    for r in reps:
        t_cost = df_t14[df_t14["rep_key"] == r]["Training_Minutes"].mean()
        acc = df_e0_summary.loc[r, "Accuracy_Mean"] * 100
        acc_sd = df_e0_summary.loc[r, "Accuracy_SD"] * 100
        t_sd = df_t14[df_t14["rep_key"] == r]["Training_Minutes"].std()
        
        ax.errorbar(t_cost, acc, xerr=t_sd, yerr=acc_sd, fmt='o', color=METHOD_COLORS[r],
                    markersize=10, capsize=4, label=METHOD_LABELS[r], elinewidth=1.5)
        ax.annotate(METHOD_LABELS[r], (t_cost + 1.5, acc - 0.5), fontsize=10, fontweight='bold')
        
    ax.set_xlabel('Training Time (Minutes on RTX 4090)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Clean Test Accuracy (%)', fontsize=12, fontweight='bold')
    ax.set_title('Clean Diagnostic Accuracy vs Neural Training Cost', fontsize=13, fontweight='bold')
    ax.set_ylim(45, 100)
    ax.grid(True, linestyle='--', alpha=0.5)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "COMPUTE_performance_vs_training_cost.png")
    fig.savefig(FIGURES_DIR / "COMPUTE_performance_vs_training_cost.pdf")
    plt.close(fig)
    
    # Figure 5 & 6: Training-step throughput and VRAM for directly measured methods
    measured_df = df_t15[df_t15["Status"] == "MEASURED_TRAINING_STEP_BENCHMARK"].copy()
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    m_reps = measured_df["rep_key"].tolist()
    m_labels = [METHOD_LABELS[r] for r in m_reps]
    x_m = np.arange(len(m_reps))
    
    ax1.bar(x_m, measured_df["Samples_per_Second"], 0.4, color=[METHOD_COLORS[r] for r in m_reps], edgecolor='black', alpha=0.85)
    ax1.set_ylabel('Throughput (Samples / Second)', fontsize=11, fontweight='bold')
    ax1.set_title('Measured Training-Step Throughput (BatchSize=32)', fontsize=11, fontweight='bold')
    ax1.set_xticks(x_m)
    ax1.set_xticklabels(m_labels, rotation=15, ha='right', fontsize=10)
    ax1.grid(axis='y', linestyle='--', alpha=0.5)
    
    ax2.bar(x_m, measured_df["Peak_VRAM_GiB"], 0.4, color=[METHOD_COLORS[r] for r in m_reps], edgecolor='black', alpha=0.85)
    ax2.set_ylabel('Peak GPU Memory (GiB)', fontsize=11, fontweight='bold')
    ax2.set_title('Measured Peak Training-Step VRAM Allocation', fontsize=11, fontweight='bold')
    ax2.set_xticks(x_m)
    ax2.set_xticklabels(m_labels, rotation=15, ha='right', fontsize=10)
    ax2.grid(axis='y', linestyle='--', alpha=0.5)
    
    fig.suptitle('Training-Step Benchmark Metrics (NVIDIA RTX 4090, PRIMARY/train)', fontsize=13, fontweight='bold')
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "COMPUTE_throughput.png")
    fig.savefig(FIGURES_DIR / "COMPUTE_throughput.pdf")
    plt.close(fig)
    
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(x_m, measured_df["Peak_VRAM_GiB"], 0.4, color=[METHOD_COLORS[r] for r in m_reps], edgecolor='black', alpha=0.85)
    ax.set_ylabel('Peak GPU Memory (GiB)', fontsize=11, fontweight='bold')
    ax.set_title('Measured Peak VRAM During Training Steps', fontsize=12, fontweight='bold')
    ax.set_xticks(x_m)
    ax.set_xticklabels(m_labels, fontsize=10)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "COMPUTE_peak_vram.png")
    fig.savefig(FIGURES_DIR / "COMPUTE_peak_vram.pdf")
    plt.close(fig)
    
    # Figure 7: Performance vs Throughput
    fig, ax = plt.subplots(figsize=(9, 5))
    for r in m_reps:
        thru = measured_df.loc[measured_df["rep_key"] == r, "Samples_per_Second"].values[0]
        acc = df_e0_summary.loc[r, "Accuracy_Mean"] * 100
        ax.scatter(thru, acc, color=METHOD_COLORS[r], s=120, edgecolors='black', label=METHOD_LABELS[r])
        ax.annotate(METHOD_LABELS[r], (thru + 3, acc - 0.5), fontsize=10, fontweight='bold')
        
    ax.set_xlabel('Training-Step Throughput (Samples / Second)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Clean Test Accuracy (%)', fontsize=12, fontweight='bold')
    ax.set_title('Clean Accuracy vs Training-Step Throughput', fontsize=13, fontweight='bold')
    ax.grid(True, linestyle='--', alpha=0.5)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "COMPUTE_performance_vs_throughput.png")
    fig.savefig(FIGURES_DIR / "COMPUTE_performance_vs_throughput.pdf")
    plt.close(fig)
    
    # Figure 8: Performance vs VRAM
    fig, ax = plt.subplots(figsize=(9, 5))
    for r in m_reps:
        vram = measured_df.loc[measured_df["rep_key"] == r, "Peak_VRAM_GiB"].values[0]
        acc = df_e0_summary.loc[r, "Accuracy_Mean"] * 100
        ax.scatter(vram, acc, color=METHOD_COLORS[r], s=120, edgecolors='black', label=METHOD_LABELS[r])
        ax.annotate(METHOD_LABELS[r], (vram + 0.02, acc - 0.5), fontsize=10, fontweight='bold')
        
    ax.set_xlabel('Peak Training-Step VRAM Allocation (GiB)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Clean Test Accuracy (%)', fontsize=12, fontweight='bold')
    ax.set_title('Clean Accuracy vs Training-Step VRAM Allocation', fontsize=13, fontweight='bold')
    ax.grid(True, linestyle='--', alpha=0.5)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "COMPUTE_performance_vs_vram.png")
    fig.savefig(FIGURES_DIR / "COMPUTE_performance_vs_vram.pdf")
    plt.close(fig)
    
    print("COMPUTE Analysis Complete. All tables and figures generated.")

if __name__ == "__main__":
    analyze_computational_cost()
