import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

ROOT = Path(r"C:\Users\Johnny\Desktop\KINOVA_FINAL_ANALYSIS_ANTIGRAVITY")
DERIVED_DIR = ROOT / "derived"
TABLES_DIR = ROOT / "tables"
FIGURES_DIR = ROOT / "figures" / "CROSS_EXPERIMENT"
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

def analyze_cross_experiment():
    print("--- Running Cross-Experiment Synthesis Analysis ---")
    
    # 1. Build T18_sensor_dependencies.csv
    t18_records = [
        {
            "Method": "SHAPE-CWT",
            "Measured_q": "No",
            "Measured_dq": "Yes (Sensory Feedback)",
            "Measured_ddq": "No",
            "Commanded_tau": "Yes (Actuator Command)",
            "Reference_q": "No",
            "Reference_dq": "Yes (Planned Trajectory)",
            "Reference_ddq": "No",
            "Reference_tau_nom": "Yes (Planned Trajectory)",
            "Nominal_Dynamic_Model": "No (Online ID unneeded)",
            "Observer_Internal_State": "None (Pure Algebraic)",
            "Numerical_Integration": "None",
            "CWT_Input_Channels": 6,
            "Physical_Domain": "Port Power (Watts)",
            "Summary_Category": "Semi-Algebraic Port Observation"
        },
        {
            "Method": "Torque-CWT",
            "Measured_q": "No",
            "Measured_dq": "No",
            "Measured_ddq": "No",
            "Commanded_tau": "Yes (Actuator Command)",
            "Reference_q": "No",
            "Reference_dq": "No",
            "Reference_ddq": "No",
            "Reference_tau_nom": "Yes (Planned Trajectory)",
            "Nominal_Dynamic_Model": "No (Online ID unneeded)",
            "Observer_Internal_State": "None (Pure Algebraic)",
            "Numerical_Integration": "None",
            "CWT_Input_Channels": 6,
            "Physical_Domain": "Parity Torque (N*m)",
            "Summary_Category": "Pure Feedforward Command Parity"
        },
        {
            "Method": "GMO-CWT",
            "Measured_q": "Yes (Joint Encoder)",
            "Measured_dq": "Yes (Joint Tachometer/Deriv)",
            "Measured_ddq": "No",
            "Commanded_tau": "Yes (Actuator Command)",
            "Reference_q": "No",
            "Reference_dq": "No",
            "Reference_ddq": "No",
            "Reference_tau_nom": "No",
            "Nominal_Dynamic_Model": "Yes (Full M, g, C^T*dq, fric)",
            "Observer_Internal_State": "6-DOF Momentum State (xi)",
            "Numerical_Integration": "Tustin (Trapezoidal 1000 Hz)",
            "CWT_Input_Channels": 6,
            "Physical_Domain": "Momentum Residual (N*m)",
            "Summary_Category": "Full Dynamic State Observer"
        },
        {
            "Method": "EO-CWT",
            "Measured_q": "Yes (Joint Encoder)",
            "Measured_dq": "Yes (Joint Tachometer/Deriv)",
            "Measured_ddq": "No",
            "Commanded_tau": "Yes (Actuator Command)",
            "Reference_q": "No",
            "Reference_dq": "No",
            "Reference_ddq": "No",
            "Reference_tau_nom": "No",
            "Nominal_Dynamic_Model": "Yes (M, g, fric; Zero Coriolis)",
            "Observer_Internal_State": "Scalar Energy State (xi_E)",
            "Numerical_Integration": "Tustin (Trapezoidal 1000 Hz)",
            "CWT_Input_Channels": 1,
            "Physical_Domain": "Power Balance (Watts)",
            "Summary_Category": "Scalar Kinetic Energy Observer"
        }
    ]
    df_t18 = pd.DataFrame(t18_records)
    df_t18.to_csv(TABLES_DIR / "T18_sensor_dependencies.csv", index=False)
    print("Saved tables/T18_sensor_dependencies.csv")
    
    # 2. Build T19_cross_experiment_profile.csv
    # Read previous tables
    t02 = pd.read_csv(TABLES_DIR / "T02_E0_overall.csv").set_index("rep_key")
    t03 = pd.read_csv(TABLES_DIR / "T03_E0_per_class.csv")
    t04 = pd.read_csv(TABLES_DIR / "T04_E0_binary_detection.csv").set_index("Representation")
    t06 = pd.read_csv(TABLES_DIR / "T06_E1_severity.csv")
    t08 = pd.read_csv(TABLES_DIR / "T08_E2B_frequency.csv")
    t09 = pd.read_csv(TABLES_DIR / "T09_E3_excitation.csv")
    t11 = pd.read_csv(TABLES_DIR / "T11_E4_overall_noise.csv")
    t14 = pd.read_csv(TABLES_DIR / "T14_training_cost.csv")
    t15 = pd.read_csv(TABLES_DIR / "T15_inference_benchmark.csv").set_index("rep_key")
    
    cwt_reps = ["shape_cwt", "torque_cwt", "gmo_cwt", "energy_cwt"]
    
    t19_rows = []
    for r in cwt_reps:
        lbl = METHOD_LABELS[r]
        
        # Clean overall
        clean_acc = t02.loc[r, "Accuracy_Mean"] * 100
        clean_far = t04.loc[lbl, "False_Alarm_Rate_Mean"] * 100
        
        # Clean per class recall
        loe_clean = t03[(t03["Representation"] == lbl) & (t03["Class"] == "LoE")]["Recall_Mean"].values[0] * 100
        fric_clean = t03[(t03["Representation"] == lbl) & (t03["Class"] == "Friction")]["Recall_Mean"].values[0] * 100
        vib_clean = t03[(t03["Representation"] == lbl) & (t03["Class"] == "Vibration")]["Recall_Mean"].values[0] * 100
        
        # Low severity
        low_loe = t06[(t06["rep_key"] == r) & (t06["Fault_Class"] == "LoE") & (t06["Severity_Bin"] == "[0.02, 0.05)")]["Multiclass_Recall_Mean"].values[0] * 100
        low_fric = t06[(t06["rep_key"] == r) & (t06["Fault_Class"] == "Friction") & (t06["Severity_Bin"] == "[0.02, 0.10)")]["Multiclass_Recall_Mean"].values[0] * 100
        low_vib = t06[(t06["rep_key"] == r) & (t06["Fault_Class"] == "Vibration") & (t06["Severity_Bin"] == "[0.10, 0.50)")]["Multiclass_Recall_Mean"].values[0] * 100
        
        # Excitation
        low_exc = t09[(t09["rep_key"] == r) & (t09["Excitation_Quartile"] == "Q1")]["Accuracy_Mean"].values[0] * 100
        high_exc = t09[(t09["rep_key"] == r) & (t09["Excitation_Quartile"] == "Q4")]["Accuracy_Mean"].values[0] * 100
        
        # Frequency (E2B)
        low_freq = t08[(t08["rep_key"] == r) & (t08["Frequency_Hz"] == 2.0)]["Vibration_Recall_Mean"].values[0] * 100
        high_freq = t08[(t08["rep_key"] == r) & (t08["Frequency_Hz"] == 20.0)]["Vibration_Recall_Mean"].values[0] * 100
        
        # Noise
        pos_noise = t11[(t11["rep_key"] == r) & (t11["Condition"] == "position_0.05deg")]["Accuracy_Mean"].values[0] * 100
        vel_noise = t11[(t11["rep_key"] == r) & (t11["Condition"] == "velocity_40dB")]["Accuracy_Mean"].values[0] * 100
        comb_noise = t11[(t11["rep_key"] == r) & (t11["Condition"] == "combined_40dB_0.05deg")]["Accuracy_Mean"].values[0] * 100
        
        # Stability
        seed_sd = t02.loc[r, "Accuracy_SD"] * 100
        
        # Compute
        train_min = t14[t14["rep_key"] == r]["Training_Minutes"].mean()
        measured_training_step = t15.loc[r, "Status"] == "MEASURED_TRAINING_STEP_BENCHMARK"
        thru = t15.loc[r, "Samples_per_Second"] if measured_training_step else np.nan
        vram = t15.loc[r, "Peak_VRAM_GiB"] if measured_training_step else np.nan
        
        # Structural class only; no standalone residual runtime was measured.
        res_cost_map = {
            "shape_cwt": "O(n) algebraic; runtime NOT_MEASURED",
            "torque_cwt": "O(n) algebraic; runtime NOT_MEASURED",
            "gmo_cwt": "Dynamic observer; runtime NOT_MEASURED",
            "energy_cwt": "Dynamic observer; runtime NOT_MEASURED",
        }
        sensor_req_map = {
            "shape_cwt": "tau_cmd + dq_meas + planned ref",
            "torque_cwt": "tau_cmd + planned ref",
            "gmo_cwt": "tau_cmd + q_meas + dq_meas + full dynamics",
            "energy_cwt": "tau_cmd + q_meas + dq_meas + dynamics (no Coriolis)"
        }
        
        t19_rows.append({
            "Method": lbl,
            "Clean_Accuracy_Pct": clean_acc,
            "Clean_Nominal_FAR_Pct": clean_far,
            "Clean_LoE_Recall_Pct": loe_clean,
            "Clean_Friction_Recall_Pct": fric_clean,
            "Clean_Vibration_Recall_Pct": vib_clean,
            "Low_Severity_LoE_Pct": low_loe,
            "Low_Severity_Friction_Pct": low_fric,
            "Low_Amplitude_Vibration_Pct": low_vib,
            "Low_Excitation_Q1_Pct": low_exc,
            "High_Excitation_Q4_Pct": high_exc,
            "Low_Freq_2Hz_Pct": low_freq,
            "Controlled_Freq_20Hz_Pct": high_freq,
            "Position_Noise_0.05deg_Pct": pos_noise,
            "Velocity_Noise_40dB_Pct": vel_noise,
            "Combined_Noise_Pct": comb_noise,
            "Seed_Instability_SD_Pct": seed_sd,
            "Training_Minutes": train_min,
            "Training_Step_Throughput_sps": thru,
            "Peak_Training_Step_VRAM_GiB": vram,
            "Residual_Structural_Complexity": res_cost_map[r],
            "Residual_Runtime_Status": "NOT_MEASURED",
            "Final_Residual_Input_Requirements": sensor_req_map[r]
        })
        
    df_t19 = pd.DataFrame(t19_rows)
    df_t19.to_csv(TABLES_DIR / "T19_cross_experiment_profile.csv", index=False)
    print("Saved tables/T19_cross_experiment_profile.csv")
    
    # 3. Generate Synthesis Figures
    print("Generating Cross-Experiment Synthesis Figures...")
    
    # Heatmap of performance across operational regimes (Normalized to [0, 100])
    profile_features = [
        ("Clean Overall", "Clean_Accuracy_Pct"),
        ("Clean LoE", "Clean_LoE_Recall_Pct"),
        ("Clean Friction", "Clean_Friction_Recall_Pct"),
        ("Clean Vibration", "Clean_Vibration_Recall_Pct"),
        ("Low-Severity LoE", "Low_Severity_LoE_Pct"),
        ("Low-Severity Friction", "Low_Severity_Friction_Pct"),
        ("Low-Amplitude Vib", "Low_Amplitude_Vibration_Pct"),
        ("Low Excitation (Q1)", "Low_Excitation_Q1_Pct"),
        ("High Excitation (Q4)", "High_Excitation_Q4_Pct"),
        ("Vibration 2 Hz", "Low_Freq_2Hz_Pct"),
        ("Vibration 20 Hz", "Controlled_Freq_20Hz_Pct"),
        ("Position Noise 0.05°", "Position_Noise_0.05deg_Pct"),
        ("Velocity Noise 40dB", "Velocity_Noise_40dB_Pct"),
        ("Combined Noise", "Combined_Noise_Pct"),
    ]
    
    heat_matrix = []
    col_names = [f[0] for f in profile_features]
    for _, row in df_t19.iterrows():
        heat_matrix.append([row[f[1]] for f in profile_features])
    heat_df = pd.DataFrame(heat_matrix, index=df_t19["Method"], columns=col_names)
    
    fig, ax = plt.subplots(figsize=(14, 5.5))
    im = ax.imshow(heat_df.values, cmap='YlGnBu', vmin=15, vmax=100)
    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.04)
    cbar.set_label('Performance Metric / Recall (%)', fontsize=11)
    
    ax.set_xticks(range(len(col_names)))
    ax.set_xticklabels(col_names, rotation=35, ha='right', fontsize=9.5, fontweight='bold')
    ax.set_yticks(range(len(df_t19)))
    ax.set_yticklabels(df_t19["Method"], fontsize=11, fontweight='bold')
    
    for r_i in range(len(df_t19)):
        for c_i in range(len(col_names)):
            val = heat_df.values[r_i, c_i]
            color = 'white' if val > 65 else 'black'
            ax.text(c_i, r_i, f"{val:.1f}%", ha='center', va='center', color=color, fontsize=9)
            
    ax.set_title('Cross-Experiment Diagnostic Performance Profile Across Physical Regimes', fontsize=13, fontweight='bold')
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "CROSS_performance_profile_heatmap.png")
    fig.savefig(FIGURES_DIR / "CROSS_performance_profile_heatmap.pdf")
    plt.close(fig)
    
    # Trade-off Figure: Clean Accuracy vs Noise Robustness vs Computational Cost
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Bubble plot:
    # X-axis: Clean Accuracy (%)
    # Y-axis: Velocity Noise 40dB Accuracy (%)
    # Equal marker sizes: standalone residual runtime is NOT_MEASURED.
    
    for _, row in df_t19.iterrows():
        m = row["Method"]
        x_val = row["Clean_Accuracy_Pct"]
        y_val = row["Velocity_Noise_40dB_Pct"]
        sz = 160
        rep_k = [k for k, v in METHOD_LABELS.items() if v == m][0]
        
        ax.scatter(x_val, y_val, s=sz, color=METHOD_COLORS[rep_k], alpha=0.75, edgecolors='black', linewidth=1.5, label=m)
        ax.annotate(m, (x_val - 1.2, y_val + 2.5), fontsize=9.5, fontweight='bold')
        
    ax.axhline(81.66, color='#ff7f0e', linestyle=':', alpha=0.6, label='Torque Noise Immunity (81.66%)')
    ax.set_xlabel('Clean Diagnostic Accuracy (%) [Primary Benchmark]', fontsize=12, fontweight='bold')
    ax.set_ylabel('Velocity Noise Robustness Accuracy (%) [40 dB SNR]', fontsize=12, fontweight='bold')
    ax.set_title('Clean Accuracy vs Velocity-Noise Robustness (Residual Runtime NOT_MEASURED)', fontsize=12, fontweight='bold')
    ax.set_xlim(75, 100)
    ax.set_ylim(20, 90)
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(loc='lower left', frameon=True, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "CROSS_clean_vs_robustness_tradeoff.png")
    fig.savefig(FIGURES_DIR / "CROSS_clean_vs_robustness_tradeoff.pdf")
    plt.close(fig)
    
    print("Cross-Experiment Synthesis Complete.")

if __name__ == "__main__":
    analyze_cross_experiment()
