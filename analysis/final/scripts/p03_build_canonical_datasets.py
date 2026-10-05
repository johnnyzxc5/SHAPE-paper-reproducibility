import sys
import json
import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path(r"C:\Users\Johnny\Desktop\KINOVA_FINAL_ANALYSIS_ANTIGRAVITY")
INPUTS_PRIMARY = ROOT / "inputs" / "primary_zip"
INPUTS_E4 = ROOT / "inputs" / "e4_zip"
DERIVED_DIR = ROOT / "derived"
DERIVED_DIR.mkdir(parents=True, exist_ok=True)

# Train excitation thresholds
with open(INPUTS_PRIMARY / "E3_EXCITATION_MODE" / "shape_cwt_seed_1729_e3_train_quartile_thresholds.json", "r") as f:
    E3_THRESHOLDS = json.load(f)

# Severity definitions
SEVERITY_DEFS = {
    "LoE": ("s_LoE", [0.02, 0.05, 0.10, 0.20, 0.3000001], ["[0.02, 0.05)", "[0.05, 0.10)", "[0.10, 0.20)", "[0.20, 0.30]"]),
    "Friction": ("s_Friction", [0.02, 0.10, 0.30, 0.75, 1.5000001], ["[0.02, 0.10)", "[0.10, 0.30)", "[0.30, 0.75)", "[0.75, 1.50]"]),
    "Vibration": ("A_d", [0.10, 0.50, 1.00, 1.75, 2.500001], ["[0.10, 0.50)", "[0.50, 1.00)", "[1.00, 1.75)", "[1.75, 2.50]"])
}

# E2A grid definitions
FREQ_BINS = [2, 5, 10, 15, 20, 25, 30.000001]
FREQ_LABELS = ["[2, 5)", "[5, 10)", "[10, 15)", "[15, 20)", "[20, 25)", "[25, 30]"]
AMP_BINS = [0.1, 0.5, 1.0, 1.75, 2.500001]
AMP_LABELS = ["[0.1, 0.5)", "[0.5, 1.0)", "[1.0, 1.75)", "[1.75, 2.50]"]

def enrich_frame(df):
    # Binary detection
    # label: 0=Nominal, 1=LoE, 2=Friction, 3=Vibration
    df["true_binary"] = (df["label"] != 0).astype(int)
    df["predicted_binary"] = (df["prediction"] != 0).astype(int)
    df["prob_fault"] = (1.0 - df["prob_nominal"]).astype(float)
    
    df["is_correct_multiclass"] = (df["prediction"] == df["label"]).astype(int)
    df["is_correct_binary"] = (df["predicted_binary"] == df["true_binary"]).astype(int)
    df["is_false_alarm"] = ((df["label"] == 0) & (df["prediction"] != 0)).astype(int)
    df["is_missed_detection"] = ((df["label"] != 0) & (df["prediction"] == 0)).astype(int)
    df["is_mechanism_confusion"] = ((df["label"] != 0) & (df["prediction"] != 0) & (df["prediction"] != df["label"])).astype(int)
    
    # Severity bin
    df["severity_bin"] = "N/A"
    for fault_class, (col, bins, labels) in SEVERITY_DEFS.items():
        mask = (df["fault_class"] == fault_class) & df[col].notna()
        if mask.any():
            cats = pd.cut(df.loc[mask, col].astype(float), bins=bins, labels=labels, right=False)
            df.loc[mask, "severity_bin"] = cats.astype(str)
            
    # E2A grid for Vibration
    df["vibration_freq_bin"] = "N/A"
    df["vibration_amp_bin"] = "N/A"
    vib_mask = (df["fault_class"] == "Vibration") & df["f_d"].notna() & df["A_d"].notna()
    if vib_mask.any():
        df.loc[vib_mask, "vibration_freq_bin"] = pd.cut(
            df.loc[vib_mask, "f_d"].astype(float), bins=FREQ_BINS, labels=FREQ_LABELS, right=False
        ).astype(str)
        df.loc[vib_mask, "vibration_amp_bin"] = pd.cut(
            df.loc[vib_mask, "A_d"].astype(float), bins=AMP_BINS, labels=AMP_LABELS, right=False
        ).astype(str)
        
    # E3 Excitation quartiles from TRAIN thresholds
    df["excitation_quartile"] = "N/A"
    exc_mask = df["dq2_rms_post"].notna()
    if exc_mask.any():
        df.loc[exc_mask, "excitation_quartile"] = pd.cut(
            df.loc[exc_mask, "dq2_rms_post"].astype(float),
            bins=[-np.inf, *E3_THRESHOLDS, np.inf],
            labels=["Q1", "Q2", "Q3", "Q4"]
        ).astype(str)
        
    return df

def build_e0_canonical():
    print("Building canonical_e0_primary.parquet...")
    reps = ["energy_cwt", "gmo_cwt", "shape_cwt", "shape_fft", "shape_temporal", "torque_cwt"]
    seeds = [1729, 2027, 4099, 7919, 104729]
    parts = []
    for r in reps:
        for s in seeds:
            p = INPUTS_PRIMARY / "E0_PRIMARY" / r / f"seed_{s}" / "predictions.parquet"
            df = pd.read_parquet(p)
            assert len(df) == 3000, f"Expected 3000 rows in {p}, got {len(df)}"
            parts.append(df)
    full_e0 = pd.concat(parts, ignore_index=True)
    assert len(full_e0) == 30 * 3000, f"Expected 90,000 rows, got {len(full_e0)}"
    full_e0 = enrich_frame(full_e0)
    out_p = DERIVED_DIR / "canonical_e0_primary.parquet"
    full_e0.to_parquet(out_p, index=False)
    print(f"Saved canonical_e0_primary.parquet: {len(full_e0)} rows, {len(full_e0.columns)} cols.")

def build_e2b_canonical():
    print("Building canonical_e2b.parquet...")
    # E2B frequency sweep was evaluated on the four CWT representations
    reps = ["energy_cwt", "gmo_cwt", "shape_cwt", "torque_cwt"]
    seeds = [1729, 2027, 4099, 7919, 104729]
    parts = []
    for r in reps:
        for s in seeds:
            p = INPUTS_PRIMARY / "E2B_FREQUENCY" / r / f"seed_{s}" / "predictions.parquet"
            df = pd.read_parquet(p)
            assert len(df) == 300, f"Expected 300 rows in {p}, got {len(df)}"
            parts.append(df)
    full_e2b = pd.concat(parts, ignore_index=True)
    assert len(full_e2b) == 20 * 300, f"Expected 6,000 rows, got {len(full_e2b)}"
    full_e2b = enrich_frame(full_e2b)
    out_p = DERIVED_DIR / "canonical_e2b.parquet"
    full_e2b.to_parquet(out_p, index=False)
    print(f"Saved canonical_e2b.parquet: {len(full_e2b)} rows, {len(full_e2b.columns)} cols.")

def build_e4_canonical():
    print("Building canonical_e4.parquet...")
    reps = ["energy_cwt", "gmo_cwt", "shape_cwt", "torque_cwt"]
    seeds = [1729, 2027, 4099, 7919, 104729]
    parts = []
    for r in reps:
        for s in seeds:
            p = INPUTS_E4 / r / f"seed_{s}" / "predictions.parquet"
            df = pd.read_parquet(p)
            assert len(df) == 30000, f"Expected 30000 rows in {p}, got {len(df)}"
            parts.append(df)
    full_e4 = pd.concat(parts, ignore_index=True)
    assert len(full_e4) == 20 * 30000, f"Expected 600,000 rows, got {len(full_e4)}"
    full_e4 = enrich_frame(full_e4)
    out_p = DERIVED_DIR / "canonical_e4.parquet"
    full_e4.to_parquet(out_p, index=False)
    print(f"Saved canonical_e4.parquet: {len(full_e4)} rows, {len(full_e4.columns)} cols.")

if __name__ == "__main__":
    build_e0_canonical()
    build_e2b_canonical()
    build_e4_canonical()
    print("All canonical datasets successfully created and validated.")
