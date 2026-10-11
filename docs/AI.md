# AI workflow

The new [source/seed workflow](FROM_SEEDS.md) prepares the complete recorded configuration matrix with new paths and explicit commands for indexing, training, evaluation, fresh E4 calibration and analysis. Nothing executes by default. This route generates clean data first and never rebinds the historical calibration receipt.

The package stays at `Fault_Diagnosis/shape_ai`. This depth is executable: E4 resolves the MATLAB directory using `Path(__file__).resolve().parents[4] / 'Code_Image'`. Its source is the inspected working-tree snapshot, including changes after `f7f183f`; source hashes and normalized comparisons are in `provenance/`.

The six representations are `shape_cwt`, `torque_cwt`, `gmo_cwt`, `energy_cwt`, `shape_temporal`, `shape_fft`. The source uses a shared encoder with fixed-order concatenation in `MultiJointClassifier`; parameter sharing does not establish permutation equivariance/invariance of the complete classifier.

## Environment preparation (not performed)

Create a new environment, install an appropriate PyTorch build using its verified distribution channel, and from the package directory install `python -m pip install -e ".[test]"`. `pyproject.toml` provides lower bounds, not a historical lock. See `ENVIRONMENT.md` before choosing versions. Nothing automatically installs or upgrades the original environment.

## Frozen models and inputs

All 30 external `best.pt` hashes match PRIMARY and E2B evaluation metadata; the applicable 20 CWT checkpoints also match E4. `metadata/AI/index/full_index.parquet` is the original 20,300-row index, with its original absolute input paths. Every referenced PRIMARY/E2B path existed at assembly. It carries `dq2_rms_post` already computed during the campaign; do not rebuild it merely to view results.

Original configuration templates do not encode all launch overrides. Use `metadata/AI/runs/<representation>/seed_<seed>/config.resolved.json` as the recorded training configuration. The five seeds are 1729, 2027, 4099, 7919, 104729. Resolved batch sizes are SHAPE/Torque/GMO CWT 32, EO CWT 64, SHAPE temporal 16, SHAPE FFT 64, with four Python workers. Twenty of thirty runs differ from their template batch size. Other recorded hyperparameters include learning rate 1e-4, weight decay 1e-4, fp16 AMP, maximum 50 epochs and early-stop patience 10.

`tools/prepare_ai_config.py` creates a new config changing only `index_path` and `output_root`; it never edits the frozen record or runs training. Example:

```powershell
python tools/prepare_ai_config.py --record metadata/AI/runs/shape_cwt/seed_1729/config.resolved.json --index metadata/AI/index/full_index.parquet --output-root local/training --destination local/configs/shape_cwt_1729.json
```

## Costly future commands — NOT_RUN

From the package environment, with restored external assets and explicit new output paths:

```powershell
# Frozen evaluation; never overwrites a checkpoint.
python -m shape_ai.evaluate --checkpoint '<restored>/shape_cwt/seed_1729/best.pt' --index '<frozen-index>' --output '<new-output>/PRIMARY/shape_cwt/seed_1729' --cohort PRIMARY --split test --batch-size 32 --num-workers 4 --amp fp16
# Training only for a separately authorized new campaign.
python -m shape_ai.train --config '<path-adapted-resolved-config>'
```

Evaluate E2B with `--cohort E2B --split none`. Repeat the verified configuration matrix deliberately. These commands generate new results and were not invoked during assembly.

## E4

Use `python -m shape_ai.e4_production` with explicit index, calibration, run, output and stage paths; inspect its parser or retained launcher for the `verify`, `calibrate`, `evaluate` stages. `run_evaluation.ps1 -IncludeE4` intentionally refuses the old persistent-E4 workflow. E4 uses four CWT methods × five seeds, ten conditions × 3,000 clean test runs. It requires the later MATLAB `production_e4_stage`, `offline_e4`, `represent_e4_view` and calibration helpers included here.

The frozen calibration is linked to the exact full-index SHA and 14,000 training UIDs; both links were verified. The retained E4 index has 30,000 identities but no `path` column or tensor payload. The original bridge removes staged HDF5 after successful chunks. Restaging is a scientific computation and is NOT_RUN here. Keep the accepted fp16 inference batch boundaries (32 with 8-item tails at the original four-clean-run boundaries); changing them may change predictions. The 10-worker setting in old examples is host specific.

Relocating and rewriting the full index changes its hash and invalidates the frozen calibration/index link. Do not edit the receipt or remove its checks. On another machine, either restore paths compatible with the immutable index or introduce a separately reviewed relocation provenance contract. This first version does not silently rebind hashes. The recorded E4 code SHA `f86ad96327ee278b67c7808074f528b239bc5461` is unreadable in the historical object store; exact source identity at execution is therefore not fully proven.
