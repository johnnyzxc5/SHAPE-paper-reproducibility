# Environment evidence

| Evidence scope | Verified record | Interpretation |
|---|---|---|
| All 30 training runs | `metadata/AI/runs/*/seed_*/provenance.json` | One consistent environment: Windows 11 build 26200, Python 3.12.3 AMD64, PyTorch 2.14.0+cu130, CUDA runtime 13.0, cuDNN 92400, one NVIDIA RTX 4090 |
| E4 calibration | `metadata/AI/e4/production_e4_calibration.json` | MATLAB 26.1.0.3312084 (R2026a) Update 4; code SHA recorded but not readable |
| Frozen simulation backend | `+shape/config.m`, `observer_ctdq_environment_policy.m`; sample HDF5 header in `provenance/metadata_audit.json` | win64; MATLAB R2026a Update 4, Coder 26.1, MinGW64 C++ 14.2.0; fixed MEX/source identities |
| Candidate portable host | `observer_ctdq_environment_policy.m` | Update 5 / MSVC 2022 17.0 is a candidate requiring fresh physical qualification; not equivalent to the production environment |
| Joint/regional analysis | `evidence/joint/00_source_and_output_provenance.json`, `27_regional_provenance.json` | Python 3.12.3, pandas 3.0.6, NumPy 2.5.3, matplotlib 3.11.2 recorded at analysis time |
| Current safe test environment | `provenance/metadata_audit.json` | Read-only use of the existing Python environment; versions observed now, not retroactively assigned to training |

Required simulation products detected by source are MATLAB, Simulink, Stateflow, Optimization Toolbox, Wavelet Toolbox, Parallel Computing Toolbox and MATLAB Coder, with Windows PowerShell/CIM and selected compiler/licensing support. Availability on the delivery host was not qualified.

`Fault_Diagnosis/shape_ai/pyproject.toml` declares h5py, matplotlib, numpy, pandas, pyarrow, scikit-learn, torch and tqdm, and pytest for tests. These are lower bounds; no complete historic pip lock was found in the selected training records. `requirements.txt` installs the local editable package and does not pin transitive dependencies. Do not describe the current `pip` environment as the complete historical training environment. Preserve/resolve analysis-only plotting and statistical dependencies separately before future execution.

No environment, wheel cache, proprietary MATLAB installation or CUDA toolkit is included. No installation or upgrade was performed. Hardware/timing claims from upstream README files remain historical claims; no fresh benchmark or universal resource estimate was established.
