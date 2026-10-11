# Reproduction from source and seeds

The new entry point is `tools/reproduce.py`. It plans a new campaign without restoring production trajectories, simulation HDF5, Pilot HDF5 or trained checkpoints. The original scientific functions, manifests, trajectory bindings and resolved training configurations remain unchanged. New work belongs in a dedicated directory outside the repository. Existing results are not touched.

**Validation boundary (2026-10-11):** source/dependency checks and planning tests passed. MATLAB Code Analyzer reported no issues in the new launcher. All 50 fingerprints were checked against the existing qualified files using MATLAB's canonical hash routine. No trajectories were generated, no physical simulation, training, inference, E4 restaging or statistical aggregation was executed. The new end-to-end route is therefore **NOT_RUN**. These checks establish an executable source plan, not demonstrated numerical replication of the paper.

## Metadata available in a clean clone

| Stage | Included authority | Generated locally in the future |
|---|---|---|
| Robot/solver/controller | SLX, nominal/dirty model matrices, Modern Robotics, frozen MATLAB functions/MEX | Simulink worker caches |
| Trajectories | Generator and constraints; PRIMARY/E2B/Pilot manifests with trajectory seeds, modes and segments; original content bindings | 5,030 production and 24 Pilot trajectory MAT/qualification JSON pairs |
| Physical faults | Per-run parameter/fault/noise seeds, onset, magnitude, frequency and phase | 20,000 PRIMARY + 300 E2B HDF5 runs |
| Splits | Manifest train/val/test assignments | A new full index of generated outputs, including measured `dq2_rms_post` |
| Training | Six representations x seeds 1729, 2027, 4099, 7919, 104729; all 30 resolved configurations | 30 newly trained checkpoints and training records |
| E4 | Offline noise code, noise seeds and ten conditions; calibration procedure | Calibration from new PRIMARY/train inputs, staged test representations and predictions |
| Analysis | Preserved E0–E4 calculations, bin definitions and bootstrap seeds; portable path adapter | T02–T13, associated figures and joint severity/excitation numerical summaries |

The MAT files containing robot model parameters are source inputs, not precomputed trajectories. Frozen numerical predictions/tables are reference evidence and are not used as training inputs. `metadata/simulation/qualified_pilot_signatures.json` contains only fingerprints of the 25 datasets of each of two existing ratified Pilot cases, with source receipt/file hashes. It contains no trajectory/telemetry tensors.

## Dependencies

Simulation uses Windows x64, licensed MATLAB/Simulink R2026a, Stateflow, Optimization Toolbox, Wavelet Toolbox, Parallel Computing Toolbox and MATLAB Coder. The preserved runtime policy supports exactly Update 4/MinGW C++ 14.2 or the Update 5/MSVC 2022 candidate. PowerShell/CIM and the selected C++ compiler are checked by the source. Other MATLAB versions/operating systems are not qualified by this release. Consult [MathWorks compiler requirements](https://www.mathworks.com/support/requirements/supported-compilers.html) for installation support.

`requirements/reproduction-win64-py312.lock` pins the packages observed in the working Windows/Python 3.12 environment on 2026-10-11. This is a **prospective version profile**, not a recovered complete historical training lock. It includes scientific/plotting libraries, transitive packages and build tools. Training additionally requires a compatible NVIDIA GPU/driver and CUDA-enabled PyTorch; the recorded training hardware is an RTX 4090. PyTorch 2.14.0+cu130 has a Python 3.12 Windows x64 wheel in the [official distribution index](https://download.pytorch.org/whl/cu130/torch/). No wheel, proprietary product or environment is bundled.

The setup script defaults to a plan. It never installs packages without `-Install` and refuses an existing environment directory:

```powershell
# Planning only; substitute your Python 3.12 executable and intended new paths.
powershell -NoProfile -File tools/setup_reproduction.ps1 -Python 'C:/Python312/python.exe' -Venv 'D:/SHAPE-reproduction/venv'

# Only if/when installation is wanted, repeat with -Install.
# Installation does not generate data, simulate, train or test a network.
```

## Safe inspection and preparation

From the cloned repository root:

```powershell
python tools/verify_repository.py
python tools/check_reproduction.py
python -m unittest discover -s tools/tests -v
python tools/reproduce.py plan --work-root 'D:/SHAPE-reproduction/campaign'
```

These commands do not invoke MATLAB or import PyTorch. The last command prints argument arrays for all stages without creating the work directory. `plan --prepare` writes only a ownership marker, a command plan and 30 configurations with new index/output paths. All scientific configuration values are preserved. In the selected Python environment, `check_reproduction.py --environment` inspects installed package metadata only; it does not initialize CUDA.

## Future execution, one explicit stage at a time

Every stage below is a **future scientific computation**, not an instruction to run it during this audit. There is no execute-all option. Use the prepared directory, its Python environment and the intended MATLAB executable consistently:

```powershell
$CampaignRoot = 'D:/SHAPE-reproduction/campaign'
$CampaignPython = 'D:/SHAPE-reproduction/venv/Scripts/python.exe'
$CampaignMatlab = 'C:/Program Files/MATLAB/R2026a/bin/matlab.exe'

# Preparation only.
python tools/reproduce.py plan --work-root $CampaignRoot --python $CampaignPython --matlab $CampaignMatlab --prepare

# For a future, explicitly requested reproduction, run each stage in this order:
# inputs, qualify, simulate, index, train, evaluate, calibrate, e4, tables.
# Example invocation syntax (expensive execution is enabled by --execute):
# python tools/reproduce.py inputs --work-root $CampaignRoot --python $CampaignPython --matlab $CampaignMatlab --execute
```

Without `--execute`, even `simulate` or `train` only prints commands. A selected execution stops on the first error. The wrapper selects this checkout's Python source even if the supplied interpreter has another editable checkout installed.

`inputs` calls the frozen generator directly from manifest seeds. Each produced or resumed trajectory must pass the original content binding, generator/constraint/model hashes and verification. It never rewrites an original manifest, binding or freeze receipt. Rejection exhaustion or a cross-environment content difference stops the stage; there is no force/rebind option.

`qualify` checks the frozen environment/source/MEX policy, then generates two fresh contrasting Pilot cases in one isolated Process worker. It compares all 25 dataset fingerprints per case with the included ratified numerical signatures and prohibits GOLD fallback. Its receipt is bound to that host, MATLAB/compiler, source seal and signature table. This is a new, deliberately narrow **serial reproduction check**, not the historical 96-run Q2 concurrency qualification. It does not authorize multiple workers or certify Accelerator mode.

`simulate` requires that serial receipt and keeps one Process worker. It uses `shape.production_assignment` and `shape.run_parent` with the frozen physical settings, sibling grouping, manifests and trajectories. Existing valid campaign outputs can resume; conflicting outputs are handled by the preserved validator/recovery code. No output is directed to the author's historical production. The serial route may take a long time; no timing guarantee is made. Historical multiworker launchers remain a separate, host-specific workflow.

`index` checks the complete 20,300-run population and schema and derives E3 velocity RMS. `train` uses the 30 recorded resolved configurations, including the correct batch sizes. `evaluate` uses six methods for PRIMARY and four CWT methods for E2B. `calibrate` fits a new E4 calibration from exactly the new index's 14,000 PRIMARY/train runs; it does not reuse/edit the frozen calibration's index hash. `e4` keeps the recorded four-clean-run chunks and inference batches of 32 with the eight-item tails. It stages representations locally from clean simulations and removes successful temporary chunks as in the preserved bridge.

`tables` copies predictions into a new analysis workspace, fits E3 quartiles on the new training population, and changes only the historical scripts' ROOT assignment in copied source. The original calculations, bootstrap seeds and bin definitions are preserved. It also calculates joint numerical summaries with unique physical-run denominators, five seed-specific metrics, means and sample SDs. It refuses to overwrite an existing analysis workspace. Historical narrative reports, manuscript synchronization, publication layout variants and hardware cost measurements are not silently reused as new results; their original source/evidence remain available separately.

## What is and is not guaranteed

All required campaign seeds and source-generating inputs are packaged; preloaded simulation results are not a prerequisite of this new route. Installing tools does not establish numerical agreement. A successful future run must compare its generated predictions/tables with frozen evidence and report differences. The frozen generator binding and two-case fingerprints provide early, explicit checks of trajectory/backend drift.

The original Python code sets deterministic seeds but uses PyTorch deterministic algorithms with `warn_only=True`. Historical records do not supply a complete package lock or all process environment variables. Neither identical checkpoints nor exact cross-host training metrics can be promised from seeds alone. Preserve warnings/provenance; see the [PyTorch reproducibility guidance](https://docs.pytorch.org/docs/stable/notes/randomness.html). The prospective lock improves repeatability of future executions but cannot retroactively prove a historical environment or replace a numerical rerun.
