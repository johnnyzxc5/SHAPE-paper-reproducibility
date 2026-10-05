# 12_TRAJECTORY_PARENT_GENERATION_QUALIFICATION_AND_FREEZE_CONTRACT

**Status:** BINDING SCIENTIFIC / IMPLEMENTATION AUTHORITY  
**Ratification:** Human-authorized trajectory repair, 2026-09-14  
**Scope:** Parent trajectory generation, physical qualification, freezing, provenance, and replay.

## 1. Canonical lifecycle

Every physical parent follows this mandatory lifecycle:

`parent metadata -> deterministic candidate generation -> physical qualification -> accepted geometry -> frozen artifact -> hash-verified replay`.

Physical simulation must load a verified frozen artifact. It must not regenerate geometry from a seed. The seed remains provenance; seed alone is not trajectory identity. Qualification and freezing are required before Pilot or production physical execution. Primary siblings and paired E2-B frequency siblings consume exactly the same parent artifact.

## 2. Ratified generator distribution

The active distribution is **sequential feasibility-aware waypoint generation**. For `K` segments, generate `q0`, then each `q(i+1)` conditioned on `q(i)`, segment duration, position limits, velocity reachability, and current-model static feasibility. Simultaneous independent full-workspace sampling of all `K+1` waypoints is prohibited on the active path.

`q0` and each next waypoint are screened with current nominal Kinova gravity torques before spline construction. This screening is an efficiency mechanism only and never substitutes for final dynamic qualification.

## 3. Frozen trajectory constants

- Duration: exactly `T=10.0 s`.
- Final qualification grid: `Fs=1000 Hz`, `dt=0.001 s`, `Nt=10001`, including both endpoints.
- Segments: `K_segments in {2,3}` with uniform deterministic knots `linspace(0,10,K+1)`.
- Modes: `fly` and `stop` retain existing authority semantics.
- Safety factor: 85% of active velocity, acceleration, and nominal inverse-dynamics torque limits.
- Maximum candidate attempts: exactly 500. Exhaustion is `TRAJECTORY_QUALIFICATION_FAIL`; seeds are never silently changed.

## 4. RNG contract

Each parent initializes one local MATLAB `RandStream('mt19937ar','Seed',trajectory_seed)` inside the generator. The stream is neither global nor shared, so serial/parallel scheduling cannot affect a parent.

Each outer attempt draws one array `U=rand(stream,6,50,K+1)`. Slice 1 supplies 50 ordered `q0` candidates; slices 2 through `K+1` supply 50 ordered conditional candidates for each next waypoint. The first statically feasible candidate in each slice is selected. The complete array is drawn before screening, so early rejection and fly/stop branches do not change attempt consumption. K=2 consumes 900 uniforms per attempt; K=3 consumes 1200. Fly/stop consumes no random values. The parent stream continues between attempts and is never reset per attempt.

## 5. Waypoints and mode semantics

Workspace bounds are `0.90*[-pi,-2.25,-2.58,-pi,-2.10,-pi]` to `0.90*[pi,2.25,2.58,pi,2.10,pi]`. `q0` must satisfy nominal static gravity torque within 95% of the already margin-adjusted torque limits.

For segment duration `dt_i`, the conditional reach vector is `reach_i = dt_i*(dq_limit/1.875)*0.92`. For each joint, define `l_i=max(q_min,q_i-reach_i)` and `u_i=min(q_max,q_i+reach_i)`. Given the already assigned uniform vector `U`, the next candidate is exactly `q_(i+1)=l_i+U.*(u_i-l_i)`. This samples uniformly over the intersection of the reachable box and valid joint-position box. Post-sampling clipping of a larger unconstrained reachable-box draw is prohibited on the active path. Each accepted waypoint passes the same static screen.

Stop mode uses zero velocity and acceleration at all knots. Fly mode uses zero endpoint velocity, zero acceleration at all knots, and centered internal tangents clamped componentwise to 65% of the margin-adjusted velocity limits. No RNG draw depends on mode.

## 6. Exact final acceptance

Spline construction is evaluated directly on the final 1-kHz grid. Acceptance requires all of the following:

1. exact array shapes `[6,10001]` and valid 0–10 s grid;
2. all `q_ref`, `dq_ref`, `ddq_ref`, and nominal torques finite;
3. `q_min <= q_ref <= q_max` at every sample;
4. `abs(dq_ref) <= 0.85*dq_hardware` at every sample;
5. `abs(ddq_ref) <= 0.85*[5.2,5.2,5.2,10,10,10] rad/s^2` at every sample;
6. `abs(tau_nom) <= 0.85*[39,39,39,9,9,9] Nm` at every sample, using the current nominal Kinova model, rotor inertia, gravity, and nominal friction implementation;
7. Joint-2 accumulated absolute travel `L_q2 = trapz(t,abs(dq_ref(2,:))) >= 0.8 rad` on the same grid.

A coarse torque screen may reject early, but final acceptance always evaluates every 1-kHz sample. Observability is trajectory-only and must not depend on fault class, severity, or classifier behavior. Rejections are instrumented under `Q_LIMIT`, `DQ_LIMIT`, `DDQ_LIMIT`, `TORQUE_LIMIT`, `OBSERVABILITY`, `STATIC_FEASIBILITY`, `SPLINE_INVALID`, `NONFINITE`, or `OTHER`; multiple observed final predicates may be counted for one attempt.

## 7. Frozen artifact and receipt

Every accepted parent artifact persists: parent ID, trajectory seed, RNG algorithm/version and draw contract, accepted attempt, attempt count, K, mode, `q_waypoints`, `t_knots`, boundary-condition metadata, `q_ref`, `dq_ref`, `ddq_ref`, `tau_nom`, qualification metrics/margins, rejection histogram, generator hash, constraint-contract hash, nominal model hash, trajectory content hash, and software provenance. A machine-readable receipt additionally records status, elapsed qualification time, UTC timestamp, and exact rejection counts.

The trajectory content identifier is SHA-256 over a typed canonical stream containing the schema label, parent ID, seed, accepted attempt, K, mode, RNG algorithm, knots, waypoints, boundary conditions, and `q_ref/dq_ref/ddq_ref`. Numeric content is column-major, explicitly typed, and encoded little-endian; strings are length-prefixed UTF-8. Replay must recompute and verify it.

The generator identifier is SHA-256 over ordered hashes of the relevant generator/reference/dynamics source. The constraint identifier is SHA-256 over canonical configuration and acceptance semantics. The nominal-model identifier is the SHA-256 of `Kinova_MR_Nominal.mat`. A mismatch in any identifier blocks replay.

## 8. Campaign gates

Missing artifacts produce `TRAJECTORY_NOT_QUALIFIED`; there is no implicit regeneration fallback. `GATE-TRAJ-PROD` is created and remains **NOT RUN / NOT PASS** until 5000/5000 Primary and 30/30 paired E2-B parents are qualified and frozen, all hashes validate, no parent is unqualified, and sibling mappings are verified. Pilot qualification does not satisfy this production gate.

The original Pilot, Primary, and paired E2-B manifests remain immutable. Bindings from parent IDs to qualified artifacts are separate, versioned artifacts.
