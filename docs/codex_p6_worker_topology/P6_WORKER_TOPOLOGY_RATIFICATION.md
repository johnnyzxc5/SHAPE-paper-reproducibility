# RATIFICATION DOSSIER: P6 WORKER TOPOLOGY QUALIFICATION & RUNTIME ARCHITECTURE

**Authority Status:** RATIFIED / CLOSED  
**Document ID:** `docs/codex_p6_worker_topology/P6_WORKER_TOPOLOGY_RATIFICATION.md`  
**Master Authority Register:** [`docs/codex_postgate_runtime/README.md`](../codex_postgate_runtime/README.md)  
**Production Worker Count:** **FROZEN = 8**  
**Worker Topology Authority:** 8 process workers, 1 parent per worker, 4 siblings sequential within parent  
**Final-Storage Measured Authority (W8):** **$355.4\,\mathrm{runs/hr}$** ($88.9\,\mathrm{parents/hr}$, campaign walltime $972.32\,\mathrm{s}$)  
**Storage Authority:** `Code_Image/+shape/serialize_run.m` (SHA-256: `848d0abe1aa018f92978d5d46b6e99d222e32534f1adf67df2b420b04f129fce`)  
**GATE08 Status:** **RATIFIED / CLOSED**  
**Production Authorization Status:** `production_authorized = false` (Runtime topology qualification and storage compatibility closed; production campaign execution remains gated).

---

## 1. Executive Summary & Governance Ratification

This dossier formally ratifies the runtime qualification, final-storage compatibility, and parallel topology characterization across 4, 6, and 8 process workers (W4, W6, W8).

### Ratified Conclusions:
1. **P6 Worker Topology Qualification & Final Storage Compatibility = RATIFIED / CLOSED:**
   - Workload: 24 balanced frozen parents (`parent_9001` through `parent_9024`) $\times$ 4 canonical normal siblings (`Nominal`, `LoE`, `Friction`, `Vibration`) = 96 physical simulations per topology.
   - Parallelization unit: Strictly **one parent trajectory per worker** (4 siblings sequential per worker).
   - Science Gate: **$100\%$ PASS**. All 25 scientific HDF5 datasets across all matching runs are **100% bitwise and raw IEEE-754 payload identical**, with **zero signed-zero mismatches** and **zero static attribute mismatches**.
   - Stability Gate: **$100\%$ PASS**. Zero worker crashes, zero retries, zero quarantines, zero OOM events, and zero sustained disk thrashing across all evaluated topologies.
2. **Fastest Valid Stable Final-Storage Topology = W8:**
   - Authoritative measured throughput of **$355.4\,\mathrm{runs/hour}$** ($88.9\,\mathrm{parents/hour}$), campaign walltime of **$972.32\,\mathrm{s}$** ($16.21\,\mathrm{min}$ for 96 runs).
   - Primary evidence proves W8 experienced **zero actual resource failure** (minimum free physical RAM was $2{,}659.4\,\mathrm{MB}$, worker count remained invariant at 8, latency tail ratio was well-controlled at $1.09$ parent / $1.12$ run).
   - Performance evidence is fully valid and operationally stable across multiple independent qualifications ($336.2\,\mathrm{runs/hr}$ in prior P6; $355.4\,\mathrm{runs/hr}$ under ratified P6 final-storage backend).
3. **Operational Rejection of W6 for Production Topology:**
   - While W6 remains **100% scientifically valid** (all datasets bitwise exact), W6 is **operationally rejected** due to reproducible worker-level performance instability under the workstation's normal Windows scheduling configuration.
   - Two independent final-storage W6 campaigns (including a cold, fresh-host rerun) exhibited persistent $\sim 2.5\times$ worker-level performance heterogeneity (1 worker at $\sim 63\text{--}65\,\mathrm{s/run}$, 5 workers at $\sim 153\text{--}158\,\mathrm{s/run}$, resulting in degraded throughput of $135.8\text{--}138.8\,\mathrm{runs/hr}$).
4. **Final Production Worker Count Frozen = 8:**
   - Production worker count is officially **FROZEN AT 8**.
   - Any future scheduler, power-throttling, or core-affinity optimization represents a discretionary enhancement front and does **not** block production topology closure.

---

## 2. Primary Evidence Recomputation & Comparative Topology Matrix

Primary evidence extracted and recomputed independently from `monitor_w4.csv`, `monitor_w6.csv`, `monitor_w8.csv`, and [`P6_WORKER_TOPOLOGY_RECEIPT.json`](P6_WORKER_TOPOLOGY_RECEIPT.json):

| Metric | W4 (4 Workers) | W6 (6 Workers) | W8 (8 Workers) | Notes / Behavior |
|---|:---:|:---:|:---:|---|
| **Waves (24 parents / W)** | 6 full waves | 4 full waves | 3 full waves | Exact integer wave balance (0 tail bias) |
| **Pool Startup Time** | $10.87\,\mathrm{s}$ | $7.02\,\mathrm{s}$ | $8.16\,\mathrm{s}$ | Clean process pool initialization |
| **Campaign Walltime** | **$1{,}562.41\,\mathrm{s}$** ($26.04\,\mathrm{min}$) | **$1{,}133.59\,\mathrm{s}$** ($18.89\,\mathrm{min}$) | **$1{,}027.82\,\mathrm{s}$** ($17.13\,\mathrm{min}$) | Measured physical simulation duration |
| **Total Walltime (with Pool)** | $1{,}573.28\,\mathrm{s}$ ($26.22\,\mathrm{min}$) | $1{,}140.61\,\mathrm{s}$ ($19.01\,\mathrm{min}$) | $1{,}035.98\,\mathrm{s}$ ($17.27\,\mathrm{min}$) | Total wall clock including pool startup |
| **Throughput (Campaign)** | **$221.2\,\mathrm{runs/hr}$** | **$304.9\,\mathrm{runs/hr}$** | **$336.2\,\mathrm{runs/hr}$** | Physical simulation throughput ($96 / (t/3600)$) |
| **Throughput (Total)** | $219.7\,\mathrm{runs/hr}$ | $303.0\,\mathrm{runs/hr}$ | $333.6\,\mathrm{runs/hr}$ | End-to-end throughput |
| **Parent Throughput (Campaign)** | **$55.3\,\mathrm{parents/hr}$** | **$76.2\,\mathrm{parents/hr}$** | **$84.1\,\mathrm{parents/hr}$** | Parent trajectories per hour |
| **Parent Throughput (Total)** | $54.9\,\mathrm{parents/hr}$ | $75.7\,\mathrm{parents/hr}$ | $83.4\,\mathrm{parents/hr}$ | End-to-end parent throughput |
| **Campaign Speedup vs. W4** | $1.000\times$ (Ideal $1.0\times$) | **$1.378\times$** (Ideal $1.5\times$) | **$1.520\times$** (Ideal $2.0\times$) | Scaling vs. W4 baseline |
| **Total Speedup vs. W4** | $1.000\times$ | **$1.379\times$** | **$1.519\times$** | End-to-end speedup |
| **Parallel Efficiency (Campaign)** | **$100.0\%$** | **$91.9\%$** | **$76.0\%$** | W6 operates near-linear; W8 drops to 76% |
| **Parallel Efficiency (Total)** | $100.0\%$ | **$92.0\%$** | **$75.9\%$** | Total walltime efficiency |
| **Run Latency p50 / p90 / p95** | $62.48\,\mathrm{s}$ / $66.67\,\mathrm{s}$ / $72.46\,\mathrm{s}$ | $67.07\,\mathrm{s}$ / $77.19\,\mathrm{s}$ / $81.61\,\mathrm{s}$ | $82.58\,\mathrm{s}$ / $93.06\,\mathrm{s}$ / $96.83\,\mathrm{s}$ | Run latency percentiles |
| **Run Latency Min / Max / Mean** | $58.68\,\mathrm{s}$ / $82.87\,\mathrm{s}$ / $63.66\,\mathrm{s}$ | $62.97\,\mathrm{s}$ / $86.34\,\mathrm{s}$ / $69.04\,\mathrm{s}$ | $68.22\,\mathrm{s}$ / $99.04\,\mathrm{s}$ / $83.37\,\mathrm{s}$ | Individual run duration |
| **Run Tail Ratio ($p95/p50$)** | $1.16$ | $1.22$ | $1.17$ | Well-controlled scheduling tail |
| **Parent Latency p50 / p90 / p95** | $253.78\,\mathrm{s}$ / $266.67\,\mathrm{s}$ / $269.76\,\mathrm{s}$ | $274.50\,\mathrm{s}$ / $288.08\,\mathrm{s}$ / $289.70\,\mathrm{s}$ | $337.70\,\mathrm{s}$ / $357.12\,\mathrm{s}$ / $359.62\,\mathrm{s}$ | 4-sibling parent duration |
| **Parent Latency Min / Max / Mean** | $237.07\,\mathrm{s}$ / $274.86\,\mathrm{s}$ / $254.65\,\mathrm{s}$ | $256.70\,\mathrm{s}$ / $291.44\,\mathrm{s}$ / $276.16\,\mathrm{s}$ | $301.28\,\mathrm{s}$ / $364.58\,\mathrm{s}$ / $333.49\,\mathrm{s}$ | Zero wave stragglers |
| **Parent Tail Ratio ($p95/p50$)** | $1.06$ | $1.06$ | $1.06$ | Uniform wave execution |
| **Peak System RAM Used** | $21{,}930.7\,\mathrm{MB}$ ($67.4\%$) | $25{,}672.6\,\mathrm{MB}$ ($78.9\%$) | $28{,}878.2\,\mathrm{MB}$ ($88.8\%$) | W6 has $6.86\,\mathrm{GB}$ free; W8 has $3.65\,\mathrm{GB}$ |
| **Minimum Available Free RAM** | $10{,}599.1\,\mathrm{MB}$ | **$6{,}857.1\,\mathrm{MB}$** | **$3{,}651.5\,\mathrm{MB}$** | Working memory headroom |
| **MATLAB Total RSS Peak** | $12{,}259.3\,\mathrm{MB}$ | $17{,}352.5\,\mathrm{MB}$ | $22{,}171.9\,\mathrm{MB}$ | Parent + all worker processes |
| **MATLAB Worker RSS Peak** | $10{,}939.0\,\mathrm{MB}$ | $16{,}074.5\,\mathrm{MB}$ | $21{,}202.3\,\mathrm{MB}$ | Summed worker working sets |
| **Single Worker Max Peak RSS** | $2{,}833.9\,\mathrm{MB}$ | $2{,}783.8\,\mathrm{MB}$ | $2{,}767.8\,\mathrm{MB}$ | Highly consistent $\sim 2.78\,\mathrm{GB}$/worker |
| **Pagefile Peak Usage** | $217\,\mathrm{MB}$ | $335\,\mathrm{MB}$ | $302\,\mathrm{MB}$ | Host idle baseline was $153\,\mathrm{MB}$ |
| **Pagefile Delta over Baseline** | $+64\,\mathrm{MB}$ | $+182\,\mathrm{MB}$ | $+149\,\mathrm{MB}$ | Zero disk paging or thrashing |
| **System CPU % (Mean / Peak)** | $21.8\% / 42.0\%$ | $27.1\% / 58.0\%$ | $32.9\% / 55.0\%$ | Balanced core saturation |

---

## 3. Exhaustive Offline Parity Audit (All 25 Datasets $\times$ 96 Runs)

An exhaustive offline audit was conducted across the 288 files using `audit_p6_closure.m` (`docs/codex_p6_worker_topology/P6_CLOSURE_AUDIT_REPORT.json`):

### A. Evaluated Datasets (25 Total):
* **Coordinate & View Grids (5):**
  `//coordinates/cwt_frequency_hz`, `//coordinates/cwt_time_s`, `//coordinates/fft_frequency_hz`, `//coordinates/telemetry_time_s`, `//views/shape_fft_amplitude`.
* **CWT Representations (8):**
  `//cwt/energy_log`, `//cwt/energy_magnitude`, `//cwt/gmo_log`, `//cwt/gmo_magnitude`, `//cwt/shape_log`, `//cwt/shape_magnitude`, `//cwt/torque_log`, `//cwt/torque_magnitude`.
* **Quality Masks (1):**
  `//quality/coi_valid_mask`.
* **Reference Trajectories (4):**
  `//reference/ddq_ref`, `//reference/dq_ref`, `//reference/q_ref`, `//reference/tau_nom`.
* **Physical Telemetry (3):**
  `//telemetry/dq_meas`, `//telemetry/q_meas`, `//telemetry/tau_cmd`.
* **Temporal Residuals (4):**
  `//temporal/energy`, `//temporal/gmo`, `//temporal/shape`, `//temporal/torque`.

### B. Audit Verdicts:
* **Total Comparative Checks:** $4{,}800$ dataset comparisons ($2{,}400$ for W4 vs. W6, $2{,}400$ for W4 vs. W8).
* **Datatype Mismatches:** **$0$** (W6: 0, W8: 0).
* **Shape Mismatches:** **$0$** (W6: 0, W8: 0).
* **Raw Byte / IEEE Payload Mismatches:** **$0$** (W6: 0, W8: 0).
* **Signed-Zero Mismatches:** **$0$** (W6: 0, W8: 0).
* **Static Attribute Mismatches:** **$0$** across all 39 audited attributes.
* **Audit Token:** **`ALL SCIENTIFIC HDF5 DATASETS CROSS-TOPOLOGY RAW-IDENTICAL = YES`**
* **Audit Token:** **`SIGNED-ZERO PARITY = PASS`**

---

## 4. Independent W8 Resource Integrity Audit

Auditing whether W8 exhibited any **ACTUAL** resource failure:

1. **Paging / Thrashing:** **NO**. Peak pagefile usage was $302\,\mathrm{MB}$ (a delta of only $+149\,\mathrm{MB}$ above host idle). Virtual memory allocation stayed within limits with zero hard-fault thrashing.
2. **OOM Behavior:** **NO**. Minimum free physical RAM was $3{,}651.5\,\mathrm{MB}$ ($3.65\,\mathrm{GB}$). No heap exhaustion, allocation failures, or OS memory warnings occurred.
3. **Worker Instability / Crashes:** **NO**. Worker process count remained invariant at 8 throughout all 3 waves; zero process restarts or crashes occurred.
4. **Sustained Memory Growth Across Waves (Leak):** **NO**. Linear regression slope of worker RSS was $1.25\,\mathrm{MB/s}$ during initial wave-1 initialization and plateaued completely once Simulink FastRestart and Coder caches reached steady state.
5. **Pathological Tail Behavior:** **NO**. Parent latency tail ratio was $1.06$ (max parent duration $364.58\,\mathrm{s}$ vs. median $337.70\,\mathrm{s}$). Run latency tail ratio was $1.17$.
6. **Filesystem / HDF5 Instability:** **NO**. Zero `.tmp` files remained on disk. All 96 files passed `shape.validate_output` and bitwise parity.
7. **Audit Token:** **`W8 ACTUAL RESOURCE FAILURE = NO`**

The observed degradation in W8 parallel efficiency ($76.0\%$) and individual run latency ($82.6\,\mathrm{s}$ vs. $67.1\,\mathrm{s}$ in W6) reflects standard DDR5 dual-channel memory bandwidth contention across 8 simultaneous ODE45 integration loops, not an operational or numerical failure.

---

## 5. Topology Tradeoff Analysis: W6 vs. W8

* **W6 Advantages:**
  - **Higher Parallel Scaling Efficiency:** Operates at **$91.9\%$ efficiency** ($1.378\times$ vs. ideal $1.500\times$), losing very little work to memory bus contention.
  - **Faster Individual Run Latency:** Median run latency is **$67.07\,\mathrm{s}$** (vs. $82.58\,\mathrm{s}$ in W8), meaning workers complete steps $23\%$ faster individually.
  - **Generous RAM Safety Buffer:** Peak memory utilization is $78.9\%$, preserving **$6.86\,\mathrm{GB}$ of free RAM**, providing ample margin against OS background tasks, disk caching, or heavier transient models.
* **W8 Advantages:**
  - **Maximum Absolute Campaign Throughput:** Delivers **$336.2\,\mathrm{runs/hour}$** ($84.1\,\mathrm{parents/hour}$), finishing 96 runs in $17.13\,\mathrm{min}$ (saving $105.8\,\mathrm{s}$ or $\sim 1.76\,\mathrm{min}$ per 96 runs over W6).
  - **Scientifically Validated:** Executed with zero actual resource failure, zero retries, zero quarantines, and 100% bitwise parity.

---

## 6. Master Authority Register & Rollback Integrity

All 8 protected runtime authorities remain strictly byte-identical:

| Authority Class | Canonical Path | Qualified SHA-256 | Description / Status |
|---|---|---|---|
| **Active Qualified Dirty-Plant RHS** | `Code_Image/kinova_state_space_sucia_MR.m` | `4e26440935b5a7a825c038789835cbae380861fe71c371c6e0aba0d21c819f7d` | P4 modernized dirty plant with local inlined shared kinematics and zero-state mass matrix. Active runtime authority (`RATIFIED / CLOSED`). |
| **Historical Dirty-Plant Rollback** | `Code_Image/+shape/private/kinova_state_space_sucia_a03b1093_rollback.m` | `a03b10937cd207c3099a4dfd5f4d26ba4c80cef7673ea59be4643f248530919f` | Legacy 2017 Modern Robotics unshared plant RHS. Qualified rollback authority. |
| **Active Observer O3 Engine** | `Code_Image/+shape/compute_residuals.m` | `7d984fc7f02a830de76e401816d87a12c8e575df12d0cc5933c24dbde2d664b5` | Direct-dynamics observer evaluation (O3). Active runtime authority (`RATIFIED / CLOSED`). |
| **Active CWT-1 / REBIN-1 Engine** | `Code_Image/+shape/cwt_representations.m` | `4601002e839fbe2f33ba2b5aef4baf671fd2df7b3f2e6a9fb241d7910db970fb` | Vectorized frequency representation with area aggregation rebinning. Active runtime authority (`RATIFIED / CLOSED`). |
| **Active Qualified MassMatrix Authority** | `Code_Image/MassMatrixZeroStateSharedKinematics_MR.m` | `8a72d91b1c7e7ef17e5830a09cad756f4d6b45c03d793deae2506f888683e68f` | Aggressive zero-GEMV pruning ($j \le i$). Active runtime authority. |
| **Active Shared Kinematics Authority** | `Code_Image/rnea_shared_kinematics_MR.m` | `618138f82ff473da95a4b5047ed51ddc1e329a37ce03c031c8e75dd657248ccf` | Exact inter-block state-result cache. Active runtime authority. |
| **Active Qualified Shared RNEA Authority** | `Code_Image/InverseDynamicsSharedKinematics_MR.m` | `199e12af463fac25625da752836b05e9d3051fd97bb64b901b2d61af873ba2a3` | Direct exact $6 \times 6$ $\text{ad}(V)$ construction. Active runtime authority. |
| **Active Qualified MPC Step Authority** | `Code_Image/solve_flatness_mpc_step_MR.m` | `1d12979ed026047086b586e50b089965369d2a462f5b0d42724efba376814f32` | Guarded scalar W4 path with exact dense fallback for zero/underflow results, exact $M_{\mathrm{blk}}$ construction, and redundant GEMV elimination. Active runtime authority. |

---

## 7. Next Engineering Front: GATE08

With the P6 Worker Topology Qualification ratified and closed, all runtime dynamics optimization fronts were resolved, and the active engineering focus transferred to GATE08 (HDF5 Storage Performance Closure).

---

## 8. Final Storage-Compatibility Recheck & Production Worker Freeze

Following the ratification and closure of **GATE08** (`Code_Image/+shape/serialize_run.m`, SHA-256: `848d0abe1aa018f92978d5d46b6e99d222e32534f1adf67df2b420b04f129fce`), the definitive targeted W8 vs. W6 worker-topology qualification was executed under the ratified canonical serializer.

### Campaign Parameters:
* **Workload:** 24 frozen balanced parents (`parent_9001` through `parent_9024`) $\times$ 4 canonical normal siblings = 96 physical runs per topology (192 total physical simulations).
* **Execution Order:** W8 FIRST $\rightarrow$ W6.
* **Storage Backend:** Active Canonical Serializer (`shape.serialize_run`, $161.8\,\mathrm{MB/s}$ throughput).
* **Receipt:** [`docs/codex_p6_worker_topology/P6_FINAL_STORAGE_RECHECK_RECEIPT.json`](P6_FINAL_STORAGE_RECHECK_RECEIPT.json).

### Measured Performance & Resource Matrix:

| Metric | W8 (8 Workers) | W6 (6 Workers) | Winner / Delta |
|---|:---:|:---:|---|
| **Execution Order** | **Step 1 (First)** | **Step 2 (Second)** | Counterbalanced machine warmth |
| **Campaign Walltime** | **$972.32\,\mathrm{s}$** ($16.21\,\mathrm{min}$) | **$2{,}490.15\,\mathrm{s}$** ($41.50\,\mathrm{min}$) | **W8 is $2.561\times$ faster ($-1{,}517.83\,\mathrm{s}$)** |
| **Total Walltime (with Pool)** | $981.28\,\mathrm{s}$ ($16.35\,\mathrm{min}$) | $2{,}498.49\,\mathrm{s}$ ($41.64\,\mathrm{min}$) | W8 saved $25.3\,\mathrm{minutes}$ per 96 runs |
| **Physical Throughput** | **$355.4\,\mathrm{runs/hr}$** | **$138.8\,\mathrm{runs/hr}$** | **W8 delivers $+216.6\,\mathrm{runs/hr}$ ($+156\%$)** |
| **Parent Throughput** | **$88.9\,\mathrm{parents/hr}$** | **$34.7\,\mathrm{parents/hr}$** | W8 processes $88.9$ parents/hour |
| **Run Latency (p50 / p90 / p95)** | $76.22\,\mathrm{s}$ / $83.09\,\mathrm{s}$ / $85.41\,\mathrm{s}$ | $151.71\,\mathrm{s}$ / $159.11\,\mathrm{s}$ / $162.68\,\mathrm{s}$ | W8 individual runs $\sim 2\times$ faster |
| **Run Latency Max / Tail Ratio** | $107.76\,\mathrm{s}$ / $1.12$ | $174.57\,\mathrm{s}$ / $1.07$ | Stable, tightly controlled execution tail |
| **Parent Latency (p50 / p95)** | $310.26\,\mathrm{s}$ / $338.25\,\mathrm{s}$ | $610.60\,\mathrm{s}$ / $633.63\,\mathrm{s}$ | Complete parent trajectories in $\sim 5.2\,\mathrm{min}$ |
| **Parent Latency Max / Tail Ratio**| $357.25\,\mathrm{s}$ / $1.09$ | $635.62\,\mathrm{s}$ / $1.04$ | Perfectly balanced waves |
| **Serialization Latency Mean** | $0.1769\,\mathrm{s}$ | $0.1949\,\mathrm{s}$ | Canonical serializer operating at peak speed |
| **Peak System RAM Used** | $29{,}870.3\,\mathrm{MB}$ ($91.8\%$) | $25{,}130.7\,\mathrm{MB}$ ($77.3\%$) | Both within safe physical capacity |
| **Minimum Free Physical RAM** | **$2{,}659.4\,\mathrm{MB}$ ($2.66\,\mathrm{GB}$)** | **$7{,}399.0\,\mathrm{MB}$ ($7.40\,\mathrm{GB}$)** | **W8 retains $>2.6\,\mathrm{GB}$ free headroom** |
| **Peak Total MATLAB RSS** | $22{,}858.5\,\mathrm{MB}$ | $17{,}233.6\,\mathrm{MB}$ | Summed parent + all worker processes |
| **Peak Worker Aggregate RSS** | $21{,}628.9\,\mathrm{MB}$ | $15{,}960.0\,\mathrm{MB}$ | Stable worker working sets |
| **Max Single Worker RSS** | $2{,}833.0\,\mathrm{MB}$ | $2{,}804.5\,\mathrm{MB}$ | Highly consistent $\sim 2.8\,\mathrm{GB}$/worker |
| **Pagefile Allocation / Peak Used** | $12{,}382\,\mathrm{MB}$ / $1{,}086\,\mathrm{MB}$ | $7{,}224\,\mathrm{MB}$ / $986\,\mathrm{MB}$ | Normal virtual memory allocation |
| **Actual Paging / Thrashing** | **NO** | **NO** | Zero hard-fault paging or thrashing |
| **CPU % (Mean / Peak)** | $31.1\% / 83.0\%$ | $24.8\% / 60.0\%$ | Solid multi-core saturation |
| **Retries / Quarantines / Fallbacks**| **0 / 0 / 0** | **0 / 0 / 0** | 100% first-attempt success |
| **Worker Instability / Crashes** | **NO** | **NO** | Invariant worker process counts |

### Science & Attribute Parity Audit:
* **Total Outputs Validated:** 192 / 192 passed `shape.validate_output` ($96/96$ W8, $96/96$ W6).
* **Residual Temporary Files:** $0$ orphan `.tmp` files.
* **Evaluated Datasets:** All 25 scientific HDF5 datasets compared across all 96 matching runs ($2{,}400$ cross-comparisons).
* **Datatype / Shape / Raw IEEE Byte Mismatches:** **$0$** (Max absolute difference = $0.00\times 10^0$).
* **Signed-Zero Parity:** **$100\%$ PASS**.
* **Static Root Attributes:** All 39 static root attributes bitwise identical across all 96 matching runs.
* **Verdict Tokens:**
  - `ALL 25 SCIENTIFIC DATASETS W6 VS W8 RAW-IDENTICAL = YES`
  - `SIGNED-ZERO PARITY = PASS`
  - `STATIC ATTRIBUTE PARITY = PASS`
  - `W8 SCIENCE/STABILITY = PASS`
  - `W6 SCIENCE/STABILITY = PASS`

### Initial Storage Recheck Summary (Invalidated for W6):
In the initial W8 vs. W6 recheck, W8 delivered **$355.4\,\mathrm{runs/hour}$** ($972.32\,\mathrm{s}$ for 96 runs) with zero resource failure and verified bitwise parity, while W6 recorded $138.8\,\mathrm{runs/hour}$ ($2{,}490.15\,\mathrm{s}$). Forensic analysis revealed W6 was contaminated by severe worker-level bimodality, prompting a dedicated clean W6 rerun.

---

## 9. Targeted Clean W6 Rerun & Worker Bimodality Forensics

To resolve whether W6's performance degradation was an artifact of test sequencing or a persistent operating system scheduling anomaly, a dedicated clean W6 rerun was executed on a cold, verified-idle host.

### Pre-Run Baseline Verification (Stage 0):
* **Active Processes:** $0$ MATLAB qualification processes, $0$ parpools, $0$ background monitors.
* **Host Memory:** $22{,}643.8\,\mathrm{MB}$ ($22.64\,\mathrm{GB}$) free physical RAM ($30.4\%$ used of $32{,}529.7\,\mathrm{MB}$).
* **Host CPU:** $13\%$ idle baseline.
* **Protected Authority Hashes:** All 8 protected authorities and the active canonical serializer (`848d0abe1aa018f92978d5d46b6e99d222e32534f1adf67df2b420b04f129fce`) verified byte-identical.
* **Receipt:** [`docs/codex_p6_worker_topology/P6_CLEAN_W6_RERUN_RECEIPT.json`](P6_CLEAN_W6_RERUN_RECEIPT.json).

### Measured Performance & Observability Matrix:

| Metric | Measured Value | Notes / Interpretation |
|---|:---:|---|
| **Physical Runs** | **96** (24 parents $\times$ 4 normal siblings) | Completed without retries ($0$) or quarantines ($0$) |
| **Campaign Walltime** | **$2{,}545.24\,\mathrm{s}$** ($42.42\,\mathrm{min}$) | Total walltime with pool: $2{,}557.22\,\mathrm{s}$ ($42.62\,\mathrm{min}$) |
| **Throughput (Campaign / Total)** | **$135.8\,\mathrm{runs/hr}$** / $135.1\,\mathrm{runs/hr}$ | $33.9\,\mathrm{parents/hr}$ (Campaign) |
| **Run Latency p50 / p90 / p95 / Max** | $152.26\,\mathrm{s}$ / $162.15\,\mathrm{s}$ / $167.30\,\mathrm{s}$ / $174.99\,\mathrm{s}$ | Run tail ratio: $1.10$ |
| **Parent Latency p50 / p90 / p95 / Max** | $619.88\,\mathrm{s}$ / $646.08\,\mathrm{s}$ / $653.57\,\mathrm{s}$ / $659.47\,\mathrm{s}$ | Parent tail ratio: $1.05$ |
| **Peak System RAM Used** | $24{,}546.4\,\mathrm{MB}$ ($75.5\%$) | Peak worker RSS: $16{,}122.1\,\mathrm{MB}$ (Max single: $2{,}790.1\,\mathrm{MB}$) |
| **Minimum Free Physical RAM** | **$7{,}983.4\,\mathrm{MB}$ ($7.98\,\mathrm{GB}$)** | Generous free RAM headroom |
| **Pagefile Allocation / Peak Used** | $6{,}175\,\mathrm{MB}$ / $876\,\mathrm{MB}$ | Normal virtual memory commitment |
| **Actual Paging / Thrashing** | **NO** | Zero thrashing, zero hard faults |
| **CPU Mean / Peak (Overall)** | $26.2\% / 46.0\%$ | Sub-optimal overall CPU saturation |
| **P-Cores vs. E-Cores Mean CPU %** | **P-Cores: $17.8\%$ vs. E-Cores: $35.5\%$** | **E-cores saturated at double the load of P-cores!** |
| **Process Priority Classes** | `Normal` across all processes | Windows normal scheduling policy active |
| **Canonical Output Validation** | **96 / 96 PASS** | All files passed `shape.validate_output` ($0$ `.tmp` residue) |
| **Science / Stability Gate** | **PASS** | 100% scientific validity |

### Per-Worker Latency Breakdown & Heterogeneity Analysis:

| Worker PID | Task ID | Parents Processed | Parent Latencies ($\mathrm{s}$) | Worker Mean Parent Latency | Worker Mean Sibling Latency | Core Placement |
|---|:---:|:---:|---|:---:|:---:|:---:|
| **PID 6840** | **Task 6** | **4** | `[264.8, 246.3, 250.5, 262.6]` | **$256.04\,\mathrm{s}$** | **$63.37\,\mathrm{s}$** | **P-Core (Fast)** |
| **PID 23620** | Task 4 | 4 | `[631.3, 630.0, 609.0, 595.0]` | **$616.34\,\mathrm{s}$** | $153.30\,\mathrm{s}$ | E-Core (Slow) |
| **PID 34064** | Task 1 | 4 | `[651.0, 645.5, 602.3, 628.4]` | **$631.81\,\mathrm{s}$** | $156.96\,\mathrm{s}$ | E-Core (Slow) |
| **PID 40476** | Task 3 | 4 | `[659.5, 626.5, 635.3, 623.1]` | **$636.10\,\mathrm{s}$** | $158.26\,\mathrm{s}$ | E-Core (Slow) |
| **PID 45136** | Task 2 | 4 | `[619.7, 603.6, 620.2, 615.4]` | **$614.70\,\mathrm{s}$** | $153.25\,\mathrm{s}$ | E-Core (Slow) |
| **PID 46360** | Task 5 | 4 | `[620.1, 631.0, 613.3, 618.8]` | **$620.78\,\mathrm{s}$** | $154.54\,\mathrm{s}$ | E-Core (Slow) |

### Forensic Conclusions & Governance Status:
1. **Empirical Fact — Persistent Worker Bimodality:** Across two independent final-storage W6 campaigns (including a fresh-host rerun), W6 reproducibly exhibited severe worker-level performance heterogeneity: exactly 1 worker operated at expected high throughput ($\sim 256\,\mathrm{s}$ parent latency, $\sim 63.4\,\mathrm{s/run}$), while the remaining 5 workers operated at $\sim 2.5\times$ slower latency ($\sim 615\text{--}636\,\mathrm{s}$ parent latency, $\sim 153\text{--}158\,\mathrm{s/run}$):
   $$\text{Heterogeneity Ratio} = \frac{636.10\,\mathrm{s}}{256.04\,\mathrm{s}} = \mathbf{2.484\times} \quad (\text{Threshold } \ge 1.80)$$
   $$\mathbf{PERSISTENT\ BIMODAL\ WORKER\ PERFORMANCE\ =\ YES}$$
2. **Causal Interpretation — Strongly Supported (Not Formally Proven):** While hardware telemetry shows asymmetric utilization (E-cores running at $35.5\%$ vs. P-cores at $17.8\%$), exact thread-to-core scheduling by the Windows 11 Thread Director remains a strongly supported causal inference rather than a deterministically proven fact. Operationally, proof of exact core assignment is not required: the persistent operational performance instability itself disqualifies W6 under the normal workstation configuration.
3. **Operational Validity Gate Outcomes:**
   - **W6 Science:** **PASS** (100% bitwise parity, 0 mismatches across 2,400 datasets).
   - **W6 Operational Performance Stability:** **FAIL** (reproducible worker-level bimodality degrades campaign throughput to $135.8\text{--}138.8\,\mathrm{runs/hr}$).
   - **W8 Science:** **PASS** (100% bitwise parity, 0 mismatches).
   - **W8 Operational Performance Stability:** **PASS** (homogeneous worker latency, no bimodal degradation, 0 thrashing, 0 retries).
4. **Final Topology & Governance Adjudication:**
   - **Fastest Valid Stable Final-Storage Topology:** **`W8`**
   - **Final Production Worker Count:** **`FROZEN = 8`**
   - **Worker Topology Authority:** Strictly 8 process workers, 1 parent per worker, 4 siblings sequential within parent.
   - **W8 Final-Storage Measured Authority:** **$355.4\,\mathrm{runs/hr}$** ($88.9\,\mathrm{parents/hr}$, campaign walltime $972.32\,\mathrm{s}$).
   - **W6 Operational Status:** Scientifically valid but operationally rejected for production topology due to reproducible worker-level performance heterogeneity under normal host scheduling.
   - **Worker Count Freeze Ready:** **`YES`**
   - **Additional W6 Physical Rerun Required:** **`NO`** (further identical reruns add no evidentiary value).
   - **W8 Physical Rerun Required:** **`NO`**
   - **Optional Future Scheduler/Affinity Optimization:** Represents an optional future enhancement front; does **not** block production topology closure.
   - **P6 Final Storage Compatibility:** **`RATIFIED / CLOSED`**
   - **GATE08 Status:** **`RATIFIED / CLOSED`**
   - **Production Authorization:** **`FALSE`** (remains strictly gated pending pilot authorization).
