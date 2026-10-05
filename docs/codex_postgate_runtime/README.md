# POST-GATE RUNTIME & SIMULINK ACCELERATOR QUALIFICATION (HARDENED REVISION)

**Stage Status:** HARDENED & STAGED (ZERO EXECUTION — FINAL REVIEW REQUIRED)  
**Governance:** Frozen Continuous ODE45 Scheduling (`ode45`, `RelTol = 1e-6`, `AbsTol = 1e-8`, `MaxStep = 1e-3`, Stateflow `ChartUpdate = 'INHERITED'`, Continuous Flatness-MPC, Active-Set `quadprog`).  
**Production Authorization:** `production_authorized = false` (Strictly non-authorizing qualification harness).  
**Purpose:** Qualify Simulink Accelerator execution semantics against fresh Normal-mode baselines, enforce raw double-precision in-memory equivalence, categorize walltime attribution, and maintain zero disruption to parallel GATE-08 work.

---

## 1. Executive Summary & Hardened Methodological Rules

Following critical review, the qualification harness has been fully repaired across all 7 Blockers, 5 Important issues, and Governance mandates:

1. **Fresh (Normal, Accelerator) Execution Pairs:** Historical canonical HDF5 files are **NOT** permitted to substitute for the live Normal-mode execution baseline. For every case qualified, a fresh Normal-mode simulation and a fresh Accelerator-mode simulation are executed back-to-back in the same session.
2. **Dual-Layer Equivalence Contract & True IEEE Bit-Pattern Verification:**
   * **Level 1A:** In-memory canonical-precision pre-serialization arrays (fresh Normal vs fresh Accelerator) evaluated via true IEEE bit-pattern comparison (`typecast` to `uint64`/`uint32`, signed-zero discrimination `+0.0` vs `-0.0`, ULP distance) across 11 key channels (`q`, `dq`, `tau_cmd`, `shape`, `torque`, `eo`, `q_ref`, `dq_ref`, `ddq_ref`, `tau_nom`, `timebase`). Fresh Normal vs fresh Accelerator GMO is evaluated under established P4C numerical authority ($\max \le 2^{-28}$, $\mathrm{RMSE} \le 5.2507 \times 10^{-11}$).
   * **Level 1B:** Fresh delivery HDF5 comparison (fresh Normal HDF5 vs fresh Accelerator HDF5) bitwise exact across **ALL 25 scientific datasets** written by `serialize_run.m` (24 non-GMO datasets bitwise equal + `/temporal/gmo` under P4C authority) plus strict root attribute contract: exact 40-root-attribute inventory (39 immutable required attributes + `profile_json`). Every immutable attribute must exist in both files (missing in either or both is immediate failure) and match exactly in value. `profile_json` is required to exist in both files but is excluded from exact value equality.
   * **Level 2:** Third provenance check against historical Pilot V2 GOLD HDF5 across all 25 scientific datasets. Stored historical Pilot GOLD GMO vs fresh MEX GMO is strictly **`INFORMATIONAL_ONLY_NOT_GATE`**; live same-input GOLD/MEX co-replay is **NOT** executed by this harness.
3. **Runtime Context Exception Cleanup (Blocker 1 & Repair 2):** Immediately following `shape.mpc_runtime_context('set', prep)`, an `onCleanup(@() shape.mpc_runtime_context('clear'))` guard is created. This guarantees deterministic context cleanup on success, on `sim()` exception, or on postprocessing exception, leaving zero stale context in the MATLAB session and avoiding double-cleanup side effects. The context access microbenchmark is executed directly inside `postgate_simulate_record` while the context is loaded and valid.
4. **Exact Solver & Scheduling Semantics Verification Without Epsilon (Finding 1):** Following repository precedent from `Code_Image/+shape/run_parent.m` and `Code_Image/+shape/p2_compile_update_selftest.m`, the loaded model is explicitly configured before every physical run via `set_param(model, 'Solver', 'ode45', 'RelTol', num2str(cfg.solver_rel_tol, 17), 'AbsTol', num2str(cfg.solver_abs_tol, 17), 'MaxStep', num2str(cfg.solver_max_step_s, 17))`. Effective loaded-model values are verified via exact IEEE equality without epsilon: `str2double(get_param(model, 'RelTol')) == 1e-6`, `str2double(get_param(model, 'AbsTol')) == 1e-8`, `str2double(get_param(model, 'MaxStep')) == 1e-3`, `strcmp(get_param(model, 'Solver'), 'ode45')`, and Stateflow `ChartUpdate == 'INHERITED'` on the underlying `Stateflow.EMChart` objects for `MATLAB Function1` (Flatness-MPC) and `MATLAB Function` (Computed-Torque) **BEFORE** `sim(in)` is called. The `.slx` file is NOT modified permanently, and the model is NOT saved (in-memory changes discarded via `close_system(model, 0)`).
5. **Fresh-Run Session Isolation (Blocker 3):** Before EVERY physical run, `postgate_isolate_session.m` enforces `FastRestart = 'off'`, confirms model status `'stopped'`, resets `shape.mpc_runtime_context`, resets P0 profiler, and clears persistent variables across the 9 established functions from P4C-R3 (`run_postpilot_p4c_r3.m` lines 70–74):
   * `solve_flatness_mpc_step_MR`
   * `solve_flatness_mpc_runtime_MR`
   * `mpc_exact_invariants_MR`
   * `rnea_shared_kinematics_MR`
   * `InverseDynamicsSharedKinematics_MR`
   * `MassMatrixSharedKinematics_MR`
   * `MassMatrixZeroStateSharedKinematics_MR`
   * `kinova_state_space_sucia_MR`
   * `p0_profile_bridge`
6. **Strict Mode Enforcement on Both Modes (Blocker 4):**
   * Normal run: `requested_mode == normal` AND `actual_mode == normal`.
   * Accelerator run: `requested_mode == accelerator` AND `actual_mode == accelerator`.
   * Authoritative post-run actual mode extracted strictly from completed-run `out.SimulationMetadata.ModelInfo.SimulationMode` (fails closed with `postgate:actual_simulation_mode_unavailable` if missing/unreadable).
   * Any fallback or drift in either direction triggers immediate qualification failure (`postgate:simulation_mode_mismatch`) strictly before postprocessing and serialization.
7. **Authoritative Observer Provenance Gating (Blockers 5 & 6 & Repair 3):** Authoritative fail-closed gate requires:
   * `requested_backend == finite_difference_batch_mex`
   * `actual_backend == finite_difference_batch_mex`
   * `status == MEX_ACTIVE`
   * `fallback_used == false`
   * MEX artifact SHA256 matches qualified authority (`9dda22245d4f649854c9f3b7f9ad04527e288a2342ef5468c5a70020ddf12f5c`)
   * Source SHA256 matches qualified authority (`b99e2a6b3185a6af0f4f8db7b720fe5dfa4f90b4bb45c4c6b28b978c6d7e13c0`)
   * Live same-input GOLD/MEX co-replay is NOT executed by this harness.
8. **Truthful Physical Simulation Lifecycle Accounting (Fail-Closed & Transactional Staged Commit):** Managed through dedicated `postgate_lifecycle_ledger.m`: any stale prior `POSTGATE_RUNTIME_RESULTS.json` is explicitly invalidated/deleted before ledger initialization at the earliest entry point. The ledger distinguishes `physical_runs_attempted`, `physical_sims_started`, `physical_sims_completed`, and `physical_runs_postprocessed`. Crucially, `physical_sims_started` is incremented strictly immediately before `sim(in)` via a transactional staged commit pattern (`next_state` staged, persisted to `POSTGATE_LIFECYCLE_LEDGER.json` via atomic rename, and committed to persistent memory ONLY upon disk write success). If disk persistence fails, persistent memory remains unmutated (reporting 0 physical simulations started) and `sim(in)` is never executed. Enforces hard cap of maximum **4** physical simulations.
9. **Instrumentation Validity Gating (Important 2):** Snapshots must exist, match `run_uid`, contain required counter fields, and all counters must be strictly positive (`> 0`) before count parity is evaluated.
10. **Preflight Fail-Closed Gating (Important 3 & MassMatrix Authority):** Nonphysical Stage 0 halts immediately if compiler, model, observer hashes, MassMatrix authority hashes, selftest, context, instrumentation, or references fail.
11. **Compile-Inclusive Timing Semantics (Important 4):** First-invocation Accelerator timing includes compilation/build overhead and is labeled `FIRST_INVOCATION_COMPILE_INCLUSIVE`. Speedup is reported for characterization, not as an equivalence gate.
12. **Preservation of Raw Signed Remainder (Important 5):** The authoritative walltime difference `raw_unattributed_remainder_s = simulink_wall_s - measured_mpc_total_s - measured_plant_total_s` is preserved without clipping. Any negative value triggers an instrumentation consistency warning.
13. **Qualified MassMatrix Runtime Authority & Rollback Baseline:**
    * **Active Qualified MassMatrix Authority:** `Code_Image/MassMatrixZeroStateSharedKinematics_MR.m` (SHA-256: `8a72d91b1c7e7ef17e5830a09cad756f4d6b45c03d793deae2506f888683e68f`). Incorporates aggressive zero-GEMV column pruning ($j \le i$), qualified under 1,006 P4A4 fixtures (bitwise exact, max ULP = 0, signed-zero match), 4-physical simulation qualification (Level 1A & 1B PASS, zero fallback), and controlled same-session A/B benchmark (B1b speedups: -17.02% on C1, -25.31% on C2).
    * **Historical Baseline / Rollback Authority:** SHA-256 `9d2d89912ae949b288da17131b3e46c0314e79875c71621731dcb09edb8e029a`. Retained across benchmark baselines (`MassMatrixZeroStateSharedKinematics_baseline_bench.m`, `run_zero_gemv_same_session_ab.m`) and immutable qualification receipts as the authoritative fallback.
    * **Governance & Production Authorization:** Formally ratified for runtime qualification. Production remains strictly unauthorized (`production_authorized = false`).
14. **Qualified Continuous-Time (CT) Runtime Wrapper Authority:**
    * **Active Qualified CT Runtime Wrapper:** `Code_Image/inverse_dynamics_kinova_runtime_MR.m` (SHA-256: `787c6c8223d3fa21990763c7d1c8eab7d0d77211f53172a2e7977446013792b9`). Reuses qualified P3 shared kinematics cache for geometric inverse dynamics, qualified under 3,036 fixtures / 18,216 scalar outputs (bitwise exact, max ULP = 0, signed-0 mismatches = 0, -28.79% latency reduction), 4-physical simulation qualification (Level 1A & 1B PASS, zero fallback, CT walltime reduced by ~25.7% to 26.5%).
    * **Historical Baseline / Rollback Authority:** SHA-256 `4baaeaccb8c88489497ebd68576e9a4c27845206be46281c220a7c4e6be05bc6` (generic delegation wrapper).
    * **Frozen Scientific Authority:** `Code_Image/inverse_dynamics_kinova_MR.m` (SHA-256: `fddf05158221b047c793086460578277459fb423687ff31dd7bf4c98503616ce`, strictly untouched).
15. **Qualified Flatness-MPC Step Runtime Authority (Exact W4 Signed-Zero + Exact M_blk Construction + GEMV-Pruned):**
    * **Active Qualified MPC Step Authority:** `Code_Image/solve_flatness_mpc_step_MR.m` (SHA-256: `1d12979ed026047086b586e50b089965369d2a462f5b0d42724efba376814f32`). Guarded scalar W4 path (`20*s`) with exact dense fallback for zero/underflow results, preserving finite IEEE-754 signed-zero parity, exact $M_{\mathrm{blk}}$ construction, and redundant GEMV elimination. Qualified under 346,815 offline vectors (20,511,630 comparisons, 0 mismatches, 0 signed-zero mismatches, max ULP = 0), 880 focused controller fixtures, and 4-physical simulation qualification (Stage 0 PASS, Level 1A PASS, Level 1B PASS, Level 2 PASS, actual mode `accelerator`, zero fallback).
    * **Immediate Qualified Rollback Authority (Pre-W4 Baseline):** `Code_Image/+shape/private/solve_flatness_mpc_step_pre_w4_baseline.m` (mirror SHA: `262773f44a3ff7c5bb9c6b82d7c9198d55f9df0c73a7941d33c11ef36aa04e7e`; canonical historical SHA: `b5371e3c970036c8af94efb4aca9544c2695f100be8a7ed633884e76bd5ed7b5` preserved in `solve_flatness_mpc_step_b5371e3c_canonical.m`). Exact $M_{\mathrm{blk}}$ + GEMV-pruned baseline. Qualified rollback authority.
    * **Historical Rollback Authority (Pre-M-blk Baseline):** `Code_Image/+shape/private/solve_flatness_mpc_step_pre_mblk_baseline.m` (SHA-256: `a3199a05d7c85974698d63f6964c673d088866b7475d2844023bf5a76165d62a`). Pre-M-blk GEMV-pruned baseline. Qualified rollback authority.
    * **Historical Rollback Authority (Pre-GEMV Baseline):** `Code_Image/+shape/private/solve_flatness_mpc_step_baseline.m` (SHA-256: `da593d0f85580037ed07989b16bab327782ec84a9610b1ff2b8ea27e580a16b4` / `6fe93f4764889230f461ab6520041f46776a63ee66c674338fcb76185cd23af3`). Original unhoisted baseline.
16. **Qualified Shared Kinematics Cache Authority (Exact Inter-Block State-Result Cache):**
    * **Active Qualified Shared Kinematics Authority:** `Code_Image/rnea_shared_kinematics_MR.m` (SHA-256: `618138f82ff473da95a4b5047ed51ddc1e329a37ce03c031c8e75dd657248ccf`). Reuses forward kinematics between back-to-back callers (Flatness-MPC and Computed-Torque) via raw IEEE-754 `uint64` state-key comparison. Preserves 100% bitwise exactness across signed-zero, 1-ULP, and subnormal states. Qualified under 296,928 adversarial oracle comparisons (0 mismatches, max ULP = 0), 2,000 real trajectory steps (1,008,000 comparisons, 50% overall hit rate, 100% CT hit rate), and 4-physical simulation qualification (Stage 0 PASS, Level 1A PASS, Level 1B PASS, Level 2 PASS, CT walltime reduced by ~50%, direct kinematics saving ~7.1 to 8.0 s/run).
    * **Immediate Qualified Rollback Authority:** `Code_Image/+shape/private/rnea_shared_kinematics_54756e2f_rollback.m` (historical invariant-hoisted baseline) (SHA-256: `54756e2fde33a885cc0699464cbbcffbb5a227627600ce029c88aba5662edd18`).

---

## 2. Minimal Test Matrix: Exact Qualified Records

The test matrix consists exclusively of two authoritative records whose execution parameters are loaded from the active input manifest (`docs/codex_active/manifests/PILOT24_MANIFEST_CANDIDATE.parquet`), while historical canonical HDF5 delivery references remain bound to `pilot24_outputs/PILOT24_CANONICAL_V2/`:

| Case | Run UID | Parent Trajectory | Trajectory Mode | Segments ($K$) | Fault Class | Severity / Parameters | Canonical Reference HDF5 |
|---|---|---|---|---|---|---|---|
| **C1** | `8167b058-dc6e-3b0a-b6b0-0478265cd56a` | `9002` | **`fly`** | **$3$** | `LoE` | $s_{\mathrm{LoE}} = 0.24$, $t_f = 2.5\,\mathrm{s}$ | `pilot24_outputs/PILOT24_CANONICAL_V2/parent_9001_9100/run_8167b058-dc6e-3b0a-b6b0-0478265cd56a.h5` |
| **C2** | `216a0075-20d7-34a6-aded-c2198b018f7d` | `9015` | **`stop`** | **$2$** | `LoE` | $s_{\mathrm{LoE}} = 0.24$, $t_f = 2.5\,\mathrm{s}$ | `pilot24_outputs/PILOT24_CANONICAL_V2/parent_9001_9100/run_216a0075-20d7-34a6-aded-c2198b018f7d.h5` |

---

## 3. Staged Execution & Stop Rules

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ STAGE 0: NONPHYSICAL PREFLIGHT (0 physical runs)                             │
│ - Model & C++ compiler availability, solver parameter settings, Stateflow    │
│ - MEX hashes, selftest, runtime context set/get/clear, reference HDF5        │
│ STOP RULE: If PASS -> proceed to Stage 1. If FAIL -> HALT (0 physical runs). │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ STAGE 1: FRESH PAIR ON REPRESENTATIVE RECORD C1 (Fly, LoE, K=3)              │
│ - Run #1: Fresh Normal Mode Baseline (C1)                                    │
│ - Run #2: Fresh Accelerator Mode Candidate (C1)                              │
│ - Mode check: Verifies actual_mode == 'accelerator' (zero fallback)          │
│ - Level 1A In-Memory Equivalence: 11 canonical-precision arrays compared     │
│ - Level 1B Fresh Delivery Equivalence: Normal HDF5 vs. Accel HDF5 (25 dsets) │
│ - Level 2 Canonical Equivalence: 22 strict bitwise + 1 GMO info + 2 CWT P1B  │
│ - Authoritative Observer Provenance & Effective Configuration Gates          │
│ - Independent Count Parity: plant, controller, mpc, qp, tout (> 0)           │
│ - Forensic Attribution: Signed raw unattributed remainder + offline benches  │
│ STOP RULE: If PASS -> proceed to Stage 2.                                    │
│            If FAIL / FALLBACK / DRIFT -> HALT AT 2 PHYSICAL RUNS.            │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       ▼ (Only if Stage 1 passes all criteria)
┌──────────────────────────────────────────────────────────────────────────────┐
│ STAGE 2: FRESH PAIR ON CONTRASTING RECORD C2 (Stop, LoE, K=2)                │
│ - Run #3: Fresh Normal Mode Baseline (C2)                                    │
│ - Run #4: Fresh Accelerator Mode Candidate (C2)                              │
│ - Mode check on C2                                                           │
│ - Level 1A in-memory + Level 1B fresh delivery (25 dsets) + Level 2 canonical │
│   (Level 2: 22 strict bitwise + 1 GMO informational + 2 CWT P1B M03 guard)   │
│ - Observer provenance & effective configuration gating                       │
│ - Independent count analysis & attribution breakdown on contrasting mode     │
│ - Emit final POSTGATE_RUNTIME_RESULTS.json receipt                           │
│ TOTAL RUNS: Exactly 4 physical simulations maximum.                          │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Walltime Attribution Taxonomy & Labeling

The diagnostic tool (`postgate_unattributed_diagnostic.m`) strictly separates direct in-simulation measurements from offline benchmarks:

| Field | Timing Category | Authority Level | Description |
|---|---|---|---|
| `simulink_wall_s` | `MEASURED_IN_SIMULATION` | Authoritative | Direct walltime of `sim(in)` measured via `tic`/`toc`. |
| `measured_mpc_total_s` | `MEASURED_IN_SIMULATION` | Authoritative | Cumulative P0 profiler time in `solve_flatness_mpc_step_MR`. |
| `measured_qp_total_s` | `MEASURED_IN_SIMULATION` | Authoritative | Cumulative P0 profiler time in `quadprog`. |
| `measured_plant_total_s` | `MEASURED_IN_SIMULATION` | Authoritative | Cumulative P0 profiler time in `kinova_state_space_sucia_MR`. |
| `raw_unattributed_remainder_s` | `MEASURED_IN_SIMULATION` | Authoritative Signed | Exact difference: `simulink_wall_s - measured_mpc_total_s - measured_plant_total_s` (unclipped). |
| `clipped_unattributed_remainder_s` | `MEASURED_IN_SIMULATION` | Display Only | `max(0, raw_unattributed_remainder_s)`. |
| `estimated_computed_torque_s` | `OFFLINE_ESTIMATE` | Modeled Estimate | Microbenchmark of `inverse_dynamics_kinova_MR` on telemetry states scaled by controller entries. |
| `estimated_context_access_s` | `OFFLINE_ESTIMATE` | Modeled Estimate | Microbenchmark of `shape.mpc_runtime_context('get')` captured during valid context scaled by controller entries. |
| `raw_estimated_unattributed_remainder_s` | `CALCULATED_ESTIMATE` | Modeled Residual | Model calculation: `raw_unattributed_remainder_s - estimated_computed_torque_s - estimated_context_access_s`. |

---

## 5. File Inventory & Isolation

All files are strictly isolated in `docs/codex_postgate_runtime/`:

| File | Role |
|---|---|
| [`postgate_isolate_session.m`](postgate_isolate_session.m) | Pre-run session isolation (FastRestart off, stopped check, clears 9 persistent functions & context). |
| [`postgate_lifecycle_ledger.m`](postgate_lifecycle_ledger.m) | Truthful physical simulation lifecycle ledger (tracks attempted, sim_started before sim(), completed, postprocessed; cap <= 4). |
| [`postgate_preflight.m`](postgate_preflight.m) | Stage 0 nonphysical preflight verification (fail-closed gates, MassMatrix authority SHA-256 verification, exact solver checks without epsilon). |
| [`postgate_simulate_record.m`](postgate_simulate_record.m) | Isolated physical runner returning in-memory arrays, exact config inspection without epsilon, and lifecycle hooks. |
| [`postgate_compare_equivalence.m`](postgate_compare_equivalence.m) | Dual-layer equivalence validator (P4C bitwise comparison, all 25 fresh HDF5 datasets, Level 2 historical 3-way partition with P1B M03 representation guard). |
| [`postgate_unattributed_diagnostic.m`](postgate_unattributed_diagnostic.m) | Forensic walltime attribution with strict taxonomy and signed remainder preservation. |
| [`run_runtime_qualification.m`](run_runtime_qualification.m) | Master user runner automating fresh-pair execution, Stage 1 hard stop, and truthful physical run cap (max 4). |
| [`README.md`](README.md) | Architectural specification and governance documentation. |

---

## 6. User Execution Instructions

When ready to execute the hardened qualification stage in MATLAB:

```powershell
Set-Location 'C:\Users\Johnny\Desktop\Git\Image Processing Project'; & matlab -batch "addpath('docs/codex_postgate_runtime'); receipt = run_runtime_qualification();" 2>&1 | Tee-Object -FilePath 'docs\codex_postgate_runtime\console.log'
```

Output receipt:  
`docs/codex_postgate_runtime/POSTGATE_RUNTIME_RESULTS.json`

---

## 7. Runtime Dynamics Provenance & Master Authority Register

| Authority Class | Canonical Path | Qualified SHA-256 | Description / Status |
|---|---|---|---|
| **Active Qualified Dirty-Plant RHS** | `Code_Image/kinova_state_space_sucia_MR.m` | `4e26440935b5a7a825c038789835cbae380861fe71c371c6e0aba0d21c819f7d` | P4 modernized dirty plant with local inlined shared kinematics and zero-state mass matrix. Active runtime authority (`RATIFIED / CLOSED`). |
| **Historical Dirty-Plant Rollback** | `Code_Image/+shape/private/kinova_state_space_sucia_a03b1093_rollback.m` | `a03b10937cd207c3099a4dfd5f4d26ba4c80cef7673ea59be4643f248530919f` | Legacy 2017 Modern Robotics unshared plant RHS. Qualified rollback authority. |
| **Active Observer O3 Engine** | `Code_Image/+shape/compute_residuals.m` | `7d984fc7f02a830de76e401816d87a12c8e575df12d0cc5933c24dbde2d664b5` | Direct-dynamics observer evaluation (O3). Active runtime authority (`RATIFIED / CLOSED`). |
| **Active CWT-1 / REBIN-1 Engine** | `Code_Image/+shape/cwt_representations.m` | `4601002e839fbe2f33ba2b5aef4baf671fd2df7b3f2e6a9fb241d7910db970fb` | Vectorized frequency representation with area aggregation rebinning. Active runtime authority (`RATIFIED / CLOSED`). |
| **Active Qualified MassMatrix Authority** | `Code_Image/MassMatrixZeroStateSharedKinematics_MR.m` | `8a72d91b1c7e7ef17e5830a09cad756f4d6b45c03d793deae2506f888683e68f` | Aggressive zero-GEMV pruning ($j \le i$). Active runtime authority. |
| **Historical MassMatrix Rollback** | `Code_Image/+shape/private/MassMatrixZeroStateSharedKinematics_baseline_bench.m` | `9d2d89912ae949b288da17131b3e46c0314e79875c71621731dcb09edb8e029a` | Unpruned zero-state baseline. Qualified rollback authority. |
| **Active Shared Kinematics Authority** | `Code_Image/rnea_shared_kinematics_MR.m` | `618138f82ff473da95a4b5047ed51ddc1e329a37ce03c031c8e75dd657248ccf` | Exact inter-block state-result cache. Active runtime authority. |
| **Historical Shared Kinematics Rollback** | `Code_Image/+shape/private/rnea_shared_kinematics_54756e2f_rollback.m` | `54756e2fde33a885cc0699464cbbcffbb5a227627600ce029c88aba5662edd18` | Invariant-hoisted shared kinematics cache. Qualified rollback authority. |
| **Active Qualified Shared RNEA Authority** | `Code_Image/InverseDynamicsSharedKinematics_MR.m` | `199e12af463fac25625da752836b05e9d3051fd97bb64b901b2d61af873ba2a3` | Direct exact $6 \times 6$ $\text{ad}(V)$ construction. Active runtime authority. |
| **Historical Shared RNEA Rollback** | `Code_Image/+shape/private/InverseDynamicsSharedKinematics_ae2c047b_rollback.m` | `ae2c047bb5105bf63495e2fba313f9db0e903a910addbc7b014d2998c56c74ec` | Generic `ad.m` dispatch / concatenation baseline. Qualified rollback authority. |
| **Active CT Runtime Wrapper Authority** | `Code_Image/inverse_dynamics_kinova_runtime_MR.m` | `787c6c8223d3fa21990763c7d1c8eab7d0d77211f53172a2e7977446013792b9` | Specialized CT wrapper reusing P3 shared kinematics. Active runtime authority. |
| **Historical CT Wrapper Rollback** | `Code_Image/inverse_dynamics_kinova_runtime_MR.m` (historical baseline) | `4baaeaccb8c88489497ebd68576e9a4c27845206be46281c220a7c4e6be05bc6` | Generic delegation wrapper. Qualified rollback authority. |
| **Active Qualified MPC Step Authority** | `Code_Image/solve_flatness_mpc_step_MR.m` | `1d12979ed026047086b586e50b089965369d2a462f5b0d42724efba376814f32` | Guarded scalar W4 path with exact dense fallback for zero/underflow results, exact $M_{\mathrm{blk}}$ construction, and redundant GEMV elimination. Active runtime authority. |
| **Historical MPC Step Rollback (Pre-W4)** | `Code_Image/+shape/private/solve_flatness_mpc_step_pre_w4_baseline.m` (mirror SHA: `262773f44a3ff7c5bb9c6b82d7c9198d55f9df0c73a7941d33c11ef36aa04e7e`; canonical historical SHA: `b5371e3c970036c8af94efb4aca9544c2695f100be8a7ed633884e76bd5ed7b5` preserved in `solve_flatness_mpc_step_b5371e3c_canonical.m`) | `b5371e3c970036c8af94efb4aca9544c2695f100be8a7ed633884e76bd5ed7b5` | Exact $M_{\mathrm{blk}}$ + GEMV-pruned baseline. Qualified rollback authority. |
| **Historical MPC Step Rollback (Pre-M-blk)** | `Code_Image/+shape/private/solve_flatness_mpc_step_pre_mblk_baseline.m` | `a3199a05d7c85974698d63f6964c673d088866b7475d2844023bf5a76165d62a` | Pre-$M_{\mathrm{blk}}$ GEMV-pruned baseline. Qualified rollback authority. |
| **Historical MPC Step Rollback (Pre-GEMV)** | `Code_Image/solve_flatness_mpc_step_MR.m` (historical pre-GEMV baseline) | `6fe93f4764889230f461ab6520041f46776a63ee66c674338fcb76185cd23af3` | Unhoisted pre-GEMV baseline. Qualified rollback authority. |
| **MPC GEMV Parity Oracle Baseline** | `Code_Image/+shape/private/solve_flatness_mpc_step_baseline.m` | `da593d0f85580037ed07989b16bab327782ec84a9610b1ff2b8ea27e580a16b4` | Independent oracle baseline function for nonphysical bitwise selftest. |

---

## 8. Runtime Front Status Matrix & Next Execution Front

| Optimization Front | Technical Scope | Status | Next Action |
|---|---|:---:|---|
| **Observer O3 Engine** | Direct-dynamics observer evaluation | `RATIFIED / CLOSED` | Realized $\sim 8.42\,\mathrm{s/run}$ saving; closed. |
| **CWT-1 + REBIN-1** | Exactness-preserving CWT & rebinning | `RATIFIED / CLOSED` | Realized $\sim 4.0\text{--}7.0\,\mathrm{s/run}$ saving; closed. |
| **Dirty Plant P4** | Inlined kinematics + zero-state mass matrix | `RATIFIED / CLOSED` | Realized $3.62\text{--}3.98\,\mathrm{s/run}$ saving; closed. |
| **Pure MATLAB MPC Micro-opt** | Invariants, GEMV hoisting, W4 guard | `CLOSED` | Completed under pre-W4 / W4 exact programs. |
| **QP Optimization Front** | Codegen active-set solver inspection | `CLOSED` | Completed forensic audit; closed. |
| **RNEA MEX Compilation Front** | Native C-MEX recursion evaluation | `CLOSED` | Superseded by inlined/O3 gains; closed. |
| **GATE08 HDF5 Storage Performance** | Fast-path serialization & attribute streaming | `RATIFIED / CLOSED` | Realized $161.8\,\mathrm{MB/s}$ throughput ($>150\,\mathrm{MB/s}$ gate PASS). Active canonical serializer: `shape.serialize_run`. |
| **P6 Worker Topology Qualification** | Multi-worker parallel scaling & final-storage compatibility | `RATIFIED / CLOSED` | Final storage compatibility ratified. Valid measured W8 authority = $355.4\,\mathrm{runs/hr}$ ($88.9\,\mathrm{parents/hr}$). W6 operationally rejected due to reproducible worker-level performance heterogeneity under normal host scheduling. Final production worker count frozen = 8 (8 process workers, 1 parent per worker, 4 siblings sequential). |
| **MassMatrix Symmetry** | Lower/upper triangle evaluation reuse | `REOPEN LATER` | Deferred post-campaign. Do NOT open now. |
| **Compiled Kinematics Backend**| Multi-stage compiled backend | `REOPEN LATER` | Deferred post-campaign. Do NOT open now. |

**Runtime & Storage Optimization Status:** **`GATE08 RATIFIED/CLOSED — P6 RATIFIED/CLOSED`**  
**Production Worker Count Status:** **`FROZEN = 8 (Authority: W8 @ 355.4 runs/hr, 88.9 parents/hr)`**  
*Production Authorization Status:* `production_authorized = false` across all active and staged artifacts. Campaign production unblocking remains governed by separate pipeline gates.
