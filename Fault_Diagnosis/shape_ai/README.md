# SHAPE downstream AI pipeline

This package trains and evaluates the new numerical-tensor benchmark defined by scientific release
`5b4d09994fae40e2992d0e118cc9b31cd6cf90a1`. It is independent from the historical PNG/Jet
notebooks. The old SVM comparison is not part of this pipeline.

## Scientific matrix

| Configuration | HDF5 dataset | PyTorch sample | Model |
|---|---|---:|---|
| `shape_cwt` | `/cwt/shape_log` | `[6,224,448]` | shared 2D encoder + six-joint late fusion |
| `torque_cwt` | `/cwt/torque_log` | `[6,224,448]` | identical to SHAPE CWT |
| `gmo_cwt` | `/cwt/gmo_log` | `[6,224,448]` | identical to SHAPE CWT |
| `energy_cwt` | `/cwt/energy_log` | `[1,224,448]` | the same 2D encoder with one physical branch |
| `shape_temporal` | `/temporal/shape` | `[6,10001]` | shared 1D encoder + six-joint late fusion |
| `shape_fft` | `/views/shape_fft_amplitude` | `[6,1001]` | the same 1D architecture |

The loader performs the audited MATLAB/HDF5 transpositions. It never renders images, applies Jet,
quantizes tensors, or fits per-sample min/max scaling. A1 linear CWT magnitude remains stored upstream
but is intentionally absent from the requested primary training matrix.

## Leakage and test governance

- The canonical split embedded in `manifest_record_json` is authoritative.
- Every sibling of a parent must remain in one split.
- Training uses only PRIMARY `train`; checkpoint selection uses only PRIMARY `val`.
- `shape-train` never reads the test partition.
- PRIMARY test, E2B and E4 are evaluated only by `shape-evaluate` from a frozen `best.pt`.
- E1, E2-A and E3 are analyses of frozen predictions; they do not retrain a model.
- E2B is evaluation-only: 30 parents (`5001..5030`) x 10 frequencies = 300 runs.
- Production E4 is regenerated in bounded temporary HDF5 chunks from PRIMARY Test. Its own E4 index
  and predictions are retained under `AI/evaluation/E4`; no permanent 30,000-file E4Root is required.

## Installation on the production PC

Use a local project checkout and keep HDF5 files on local NVMe/SSD, not inside a ZIP or a live OneDrive
folder. From `Fault_Diagnosis/shape_ai`:

```powershell
.\scripts\setup_windows.ps1 `
  -Python 'C:\Path\To\python.exe' `
  -TorchIndexUrl 'THE_OFFICIAL_PYTORCH_CUDA_INDEX_SELECTED_FOR_THIS_HOST'
```

The setup script intentionally requires the PyTorch CUDA index as an argument; it does not guess a
CUDA build. Confirm that the final line reports `cuda=True` and the RTX 4090.

## Initial campaign execution order

Production E4 uses the existing completed index and trained checkpoints; begin at the E4 section
below when operating on the completed campaign.

### 1. Full scientific index and preflight

```powershell
.\scripts\run_preflight.ps1 `
  -PrimaryRoot 'C:\KinovaProduction\PRIMARY' `
  -E2BRoot 'C:\KinovaProduction\E2B' `
  -AiRoot 'C:\KinovaProduction\AI'
```

Do not pass `-E4Root` for the bounded production E4 workflow. This stage scans the
actual files, validates the 20,000 + 300 campaign counts, verifies all 25 datasets and 40 root
attributes, detects split leakage, checks E2B frequencies, and derives `dq2_rms_post` from Train and
Test telemetry for E3. Training refuses a nonconforming PRIMARY index.

Expected outputs:

```text
C:\KinovaProduction\AI\index\full_index.parquet
C:\KinovaProduction\AI\index\full_index.audit.json
C:\KinovaProduction\AI\index\full_preflight.json
```

### 2. Targeted RTX 4090 benchmarks

```powershell
.\scripts\run_benchmarks.ps1 `
  -IndexPath 'C:\KinovaProduction\AI\index\full_index.parquet' `
  -BatchSizes '8,16,32,64' `
  -Workers '0,2,4,8' `
  -Amp fp16
```

The script benchmarks four distinct workload shapes: six-joint CWT, scalar EO CWT, long temporal 1D,
and FFT 1D. Torque and GMO reuse the SHAPE-CWT result because their tensor shapes and architecture are
identical. Select a stable configuration with high throughput and reasonable VRAM margin; do not pick
the largest batch merely because it fits.

### 3. Inspect the training matrix without executing it

```powershell
.\scripts\run_training_matrix.ps1 `
  -Seeds @(1729) `
  -Workers 4 `
  -BatchCwt 16 `
  -BatchEnergy 64 `
  -BatchTemporal 32 `
  -BatchFft 64
```

Without `-Execute`, this only prints the six commands. Replace the engineering values with the winners
from the benchmark.

### 4. One-seed scientific pilot

```powershell
.\scripts\run_training_matrix.ps1 `
  -Seeds @(1729) `
  -Workers 4 `
  -BatchCwt 16 `
  -BatchEnergy 64 `
  -BatchTemporal 32 `
  -BatchFft 64 `
  -Execute
```

Review convergence, generalization gap, runtime and checkpoints for all six configurations before
starting repetitions. A run directory is immutable once `TRAINING_COMPLETE.json` exists; the command
will refuse to overwrite it.

### 5. Final repeated training

After the one-seed pilot is accepted, use the predeclared seeds:

```powershell
.\scripts\run_training_matrix.ps1 `
  -Seeds @(1729,2027,4099,7919,104729) `
  -Workers 4 `
  -BatchCwt 16 `
  -BatchEnergy 64 `
  -BatchTemporal 32 `
  -BatchFft 64 `
  -Execute
```

Seed `1729` will be skipped only if its completed artifact is intentionally retained; the current
launcher refuses overwrite, so remove it from the list when continuing after an accepted pilot. With
six configurations and five seeds the scientific matrix contains 30 training runs, not 300.

### 6. Frozen evaluation

```powershell
.\scripts\run_evaluation.ps1 `
  -Seeds @(1729,2027,4099,7919,104729) `
  -IncludeE2B
```

Omit an optional switch when that cohort is absent. The command writes per-run probabilities and
predictions, E0 metrics and confusion matrices, E1 severity tables, E2-A/E2-B tables, E3 mode and
Train-fitted excitation-quartile tables, and parent-cluster bootstrap intervals.

### Production E4: offline calibration and zero-shot evaluation

Use the already completed `C:\KinovaProduction\AI\index\full_index.parquet`. The calibration step
selects exactly 14,000 `PRIMARY/train` rows, reads only their existing `/telemetry/dq_meas`, and calls
`shape.e4_calibration_stats` and `shape.aggregate_e4_calibration`. It verifies membership, HDF5 files,
six finite RMS values, index SHA-256 and the frozen artifact before reuse. It does not promote a pilot
candidate. Run once from `Fault_Diagnosis\shape_ai`:

```powershell
.\scripts\run_e4_production.ps1 -Step Calibrate
.\scripts\run_e4_production.ps1 -Step Verify
```

For a one-run, ten-condition smoke test, use a separate output and stage root:

```powershell
.\scripts\run_e4_production.ps1 -Step Evaluate -SmokeRuns 1 -ChunkRuns 1 `
  -OutputRoot 'C:\KinovaProduction\AI\evaluation\E4_smoke' `
  -StageRoot 'C:\KinovaProduction\AI\e4\stage_smoke'
```

The host-measured full production E4 command (print here; launch only after operator review) is:

```powershell
.\scripts\run_e4_production.ps1 -Step Evaluate -ChunkRuns 20 -BatchSize 32 -Workers 4 -MatlabWorkers 10
```

The launcher checks exactly 3,000 `PRIMARY/test` clean inputs for the full run, generates the four
velocity-only, three position-only and three combined conditions with `shape.offline_e4`, then calls
`shape.represent_e4_view`. It never calls Simulink or a training command. The same staged tensors are
evaluated by the four CWT methods with all five frozen `best.pt` checkpoints. The clean input files
and checkpoints are read-only.

Each chunk keeps its index, evaluator job receipt, predictions and metrics in
`AI/evaluation/E4/_chunks/chunk_NNNN/`. MATLAB stages each E4 condition once per clean run.
`-MatlabWorkers` controls a MATLAB **process** pool across independent clean Test runs; `-Workers`
controls the separate Python DataLoader. With `-MatlabWorkers 10`, one MATLAB Engine process and
its pool remain alive across chunks. MATLAB finishes staging a chunk before Python inference
begins; the next chunk starts only after that inference finishes. Omitting the MATLAB parameter
retains the sequential MATLAB staging path. R2026a's bundled MATLAB Engine for Python is loaded
from the local MATLAB installation, without installing another Python package.
One Python/PyTorch/CUDA process per chunk evaluates the 20 checkpoints sequentially, reusing one
DataLoader across the five seeds of each representation. One model is loaded at a time. The loader
retains the accepted four-clean-run inference batch boundaries. Completed checkpoint outputs are
verified against the checkpoint, chunk index, calibration and E4 run_uid membership before reuse;
conflicts stop the run. Rerun with the same index, output root, stage root, chunk size, batch size
and both worker counts. An interrupted temporary stage is regenerated; completed checkpoint predictions are
retained. Staged HDF5 files live only under `AI/e4/stage/chunk_NNNN/` and are removed after all 20
checkpoint evaluations for that chunk succeed. At ChunkRuns 20, at most 200 copied HDF5 files
(3.62 GB measured) are staged at once. A retained `e4_index.parquet` contains
the identities and condition metadata, without tensors. Final files are
`AI/evaluation/E4/<representation>/seed_<seed>/predictions.parquet`, `metrics.json`, and
`analysis/e4_noise_robustness.csv`. The calibration receipt is
`AI/e4/production_e4_calibration.json`.

On the i9-13900K / 32 GB DDR5 / RTX 4090 / MATLAB R2026a Update 4 host, a fixed 50 clean-run
Test subset took 5,771 s with the accepted 4/32/4 bridge (260 Python launches, 13 MATLAB launches)
and 2,003 s with 20/32/4 (3 Python launches, 3 MATLAB launches), a 2.88× end-to-end speedup.
The 20/32/4 run used at most 18.03 GiB system RAM and 4.76 GiB VRAM in 3-second samples. All
10,000 final prediction rows across 20 checkpoints, probabilities, metrics and E4 robustness CSVs
matched the accepted bridge exactly. A 50/32/4 run took 2,166 s with a 9.05 GB stage. MATLAB
generation remained the largest cost and varied between runs; extrapolated full-run time is only
an estimate. The conservative fallback is ChunkRuns 4, BatchSize 32, Workers 4 with the same
persistent evaluator. Resume with the exact same command shown above. BatchSize 64 was measured
on the same subset and rejected: it changed one predicted class, probabilities by up to 0.002546,
and one robustness CSV because its fp16 inference batch shape differs from the accepted 32+8
batches. Keep BatchSize 32 for the production campaign.

For the same fixed 50 clean runs with ChunkRuns 20, BatchSize 32 and Python Workers 4,
sequential MATLAB staging took 2,024 s end to end (1,858 s MATLAB). A persistent process pool
with 8 MATLAB workers took 714 s (544 s MATLAB); 10 workers took 649 s (480 s MATLAB), a
3.12× end-to-end speedup. Pool creation took 9.18 s and 8.77 s, respectively, once for all
three chunks. Process workers default to one numerical thread on this host, whereas the
sequential MATLAB client uses 24. The launcher sets each worker to the client's numerical
thread count to preserve exact results. Without that setting, nine CWT magnitude values
differed by one float32 ULP in three of the 500 staged files, so the default-thread runs were
rejected. With the setting, all 500 staged HDF5 files for both worker counts matched the
sequential files byte for byte. Both produced identical 10,000 prediction rows, probabilities,
metrics and robustness CSVs across all 20 checkpoints.

The 10-worker run peaked at 26.82 GiB of 31.77 GiB physical RAM, leaving at least 4.94 GiB
free in the sampled trace. Pagefile allocation rose from 249 to 404 MB; there were no worker
failures or observed sustained paging stalls in this three-chunk benchmark. The equivalence
benchmark retained all three chunks, reaching 9.05 GB of staged files; normal production
removes each chunk after evaluation and peaks near 3.62 GB. The recommended MATLAB worker
count for this host is 10; use 8 if memory headroom is needed. Resume with the exact command
above. The 50-run timing is a bounded estimate for the full campaign, not a long-run guarantee.

## Pairwise scientific comparison

For one matched seed, compare methods on identical `run_uid` values:

```powershell
.\.venv\Scripts\python.exe -m shape_ai.compare `
  --prediction shape=C:\KinovaProduction\AI\evaluation\PRIMARY\shape_cwt\seed_1729\predictions.parquet `
  --prediction torque=C:\KinovaProduction\AI\evaluation\PRIMARY\torque_cwt\seed_1729\predictions.parquet `
  --prediction gmo=C:\KinovaProduction\AI\evaluation\PRIMARY\gmo_cwt\seed_1729\predictions.parquet `
  --prediction energy=C:\KinovaProduction\AI\evaluation\PRIMARY\energy_cwt\seed_1729\predictions.parquet `
  --reference shape `
  --output C:\KinovaProduction\AI\evaluation\comparisons\seed_1729.json
```

The bootstrap resamples `parent_trajectory_id`, preserving the four sibling conditions as one physical
cluster. It reports paired deltas and 95% intervals for Balanced Accuracy and Macro-F1.

Aggregate the final metrics across the frozen seed set:

```powershell
.\.venv\Scripts\python.exe -m shape_ai.aggregate `
  --root C:\KinovaProduction\AI\evaluation `
  --expected-seeds 1729,2027,4099,7919,104729 `
  --output C:\KinovaProduction\AI\evaluation\aggregate
```

This refuses duplicate records or incomplete seed sets and writes both the individual metrics and
mean, standard deviation, minimum and maximum summaries.

## Outputs per training run

```text
representation/seed_<seed>/
├── config.resolved.json
├── provenance.json
├── history.csv
├── best.pt
├── last.pt
└── TRAINING_COMPLETE.json
```

Evaluation adds `predictions.parquet`, `metrics.json`, raw and normalized confusion matrices, and the
stratified analysis tables. The predictions retain `run_uid`, parent, class, split, probabilities,
representation, seed and checkpoint path for auditability.

## Scope boundaries

- The pipeline reports full-window four-class FAR and fault missed-detection rate. Sequential detection
  delay relative to `t_fault` requires a separately frozen windowed detector and is not claimed here.
- `run_evaluation.ps1 -IncludeE4` is disabled because it expects permanently indexed E4 files.
  Use `run_e4_production.ps1` for E4.
- External published architectures can be added as explicitly named baselines later. They must not
  replace or silently tune the matched six-configuration matrix.

## Developer validation

```powershell
.\.venv\Scripts\python.exe -m pytest
```

The tests cover MATLAB-to-Python axis conversion, lazy HDF5 loading, class/parent validation, the
six-joint 2D forward pass, the scalar EO path and the 1D forward pass.
