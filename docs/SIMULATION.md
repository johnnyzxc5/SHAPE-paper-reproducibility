# Simulation and representations

`Code_Image/Kinova_Fault_Simulator.slx` and the nominal/dirty MAT models are copied from the verified operational portable. `+shape` contains reference loading, residual construction, normalization, CWT, FFT, serialization and validation. Original function and directory names are retained because executable code resolves `docs/`, `data/` and Pilot paths relative to them.

The frozen scientific specification is declared by commit `5b4d09994fae40e2992d0e118cc9b31cd6cf90a1`, but that commit is not a complete self-contained source distribution: the generator in its readable tree differs from the generator bound to production. The copied generator matches every source hash in the qualified trajectory receipt; see `provenance/generator_identity.json`. Do not replace it with the old Git blob.

## Restore before running

Restore every path in `provenance/external_portable_inventory.json` from the indicated local portable into the same relative path under a disposable execution copy of this repository. Verify each size and SHA-256. This includes 5,030 production MAT trajectories, their 5,030 qualification JSONs, two Pilot MAT/JSON pairs and two Pilot HDF5 files. The two Pilot reference records are parent 9002 (`8167b058-...`) and parent 9015 (`216a0075-...`). The corresponding Pilot manifests are already packaged.

`production_spec` accepts `TrajectoryRegistry` for the production registry. Pilot paths are separately fixed by the qualification harness; a production-registry override does not restore Pilot fixtures. Nothing has been symlinked to the originals and no source directories were altered.

## Execution stages — all NOT_RUN here

Follow the retained `COLLABORATOR_HOST_SETUP.md` with explicit new writable output/qualification roots. Its full portable claim applies only after external fixtures are restored.

1. `run_production_host_qualification('Mode','STATIC',...)`: environment and protected hashes. This also executes the MEX numerical self-test; it was not run in this static assembly.
2. Q1 in `docs/codex_p6_worker_topology/run_eof_worker_cache_isolation_qualification.m`: nonphysical worker file-generation isolation.
3. Conditional base PHYSICAL qualification: four C1/C2 runs when required by the candidate environment policy.
4. Q2: 96 physical runs for the exact host and worker count. Issue/review the host-bound concurrency receipt.
5. `run_production('Mode','PREFLIGHT',...)`, then separately explicitly armed PRODUCTION with the same assignment and host receipt.

Do not reuse another computer's receipt or treat a static pass as authorization. Do not disable source, MEX, trajectory or numerical checks.

## Scientific details

The clean closed-loop campaign does not include E4 measurement noise. `offline_e4.m` perturbs position and velocity independently at diagnosis time, with commands and references fixed. E3 uses `dq2_rms_post`, measured Joint-2 velocity RMS after fault onset; train-derived quartile thresholds are retained in evaluation metadata.

Dirty friction is joint dependent: viscous multipliers `[1.12,1.05,1.15,1.08,1.10,1.04]`, Coulomb multipliers `[1.08,1.06,1.10,1.05,1.09,1.03]`. The plant calls `get_Friction_Sucia(dq,zeros(6,1))`. It is not a uniform +15% mismatch. Use the actual matrices and functions for model parameters.

## Trajectory regeneration

`run_production_trajectory_qualification.m`, `qualify_parent.m` and `save_frozen_trajectory.m` are included as supplements. They generate, reject, qualify and freeze geometry; the orchestration writes binding/receipt files. Run only in a separate prospective campaign copy. Never run it over the frozen artifacts. The freeze receipt records 39,785 rejected attempts and 5,030 accepted parents, with MATLAB MT19937 and the historical release. These establish qualified inputs, not portable byte-identical regeneration. MAT/HDF5 file bytes also contain serialization/provenance details. No 15-minute regeneration promise is supported by this assembly.

## Observer MEX

Source: `Code_Image/ctdq_finite_difference_batch_mex_source.m`. Build driver: `Code_Image/build_p1_ctdq_mex.m`. The frozen binary is `Code_Image/generated/p1_ctdq_mex/ctdq_finite_difference_batch_mex.mexw64` (SHA-256 `9dda22245d4f649854c9f3b7f9ad04527e288a2342ef5468c5a70020ddf12f5c`). It is a Windows x64 artifact from the verified portable, for the historical MATLAB/Coder/MinGW environment.

For source compilation in an isolated experimental copy, configure MATLAB Coder and a C++ compiler, add `Code_Image` and `Code_Image/MATLAB/mr` to the MATLAB path, change to `Code_Image`, then call `build_p1_ctdq_mex(true)`. This invokes `codegen` with 6×N variable double inputs and fixed 4×4×7, 6×6×6 and 6×6 model inputs, and emits a build receipt. Compilation is NOT_RUN. A rebuilt binary is not the frozen qualified binary and will fail its expected hash unless independently qualified under a new authority. Do not overwrite the supplied binary or change expected hashes to make preflight pass. No Linux/macOS compatibility is claimed.
