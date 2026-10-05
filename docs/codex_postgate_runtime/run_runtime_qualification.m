function receipt = run_runtime_qualification(varargin)
%RUN_RUNTIME_QUALIFICATION Master one-command entry point for runtime/Accelerator qualification.
% Preserves frozen continuous ode45 scheduling, tolerances, and Flatness-MPC mathematics.
%
% Methodological Requirements:
%   1. Fresh (Normal, Accelerator) physical pairs per case (never historical HDF5 as baseline).
%   2. Enforces Level 1A raw in-memory canonical-precision pre-serialization equivalence.
%   3. Enforces Level 1B fresh delivery HDF5 equivalence (Normal vs Accelerator).
%   4. Checks Level 2 delivery HDF5 against canonical Pilot V2 GOLD as third provenance verification.
%   5. Authoritative Observer Provenance Gate (finite_difference_batch_mex, MEX_ACTIVE, zero fallback).
%   6. Authoritative Effective Configuration Gate (ode45, RelTol=1e-6, AbsTol=1e-8, MaxStep=1e-3, Stateflow ChartUpdate='INHERITED').
%   7. Correct Physical Run Accounting: tracks attempted, started, completed, postprocessed (max 4).
%   8. Hard stop at Stage 1 if any gate fails or Accelerator falls back (stops at 2 physical runs).
%   9. Explicit governance non-authorization: production_authorized = false.
%
% Usage:
%   addpath('docs/codex_postgate_runtime');
%   receipt = run_runtime_qualification();

root = fileparts(fileparts(fileparts(mfilename('fullpath'))));
code_dir = fullfile(root, 'Code_Image');
addpath(code_dir);
addpath(genpath(fullfile(code_dir, 'MATLAB', 'mr')));
addpath(fullfile(root, 'docs', 'codex_postgate_runtime'));

% Fail-safe cleanup guard to discard in-memory model modifications without saving
model_name = 'Kinova_Fault_Simulator';
model_cleanup = onCleanup(@() local_cleanup_model(model_name));

report_dir = fullfile(root, 'docs', 'codex_postgate_runtime');
if ~isfolder(report_dir), mkdir(report_dir); end
result_path = fullfile(report_dir, 'POSTGATE_RUNTIME_RESULTS.json');

% Invalidate/delete stale prior qualification receipt before ledger init (Repair 3)
if isfile(result_path)
    delete(result_path);
    if isfile(result_path)
        error('postgate:stale_result_invalidation_failed', ...
            'Failed to delete stale prior qualification result: %s', result_path);
    end
end

% Initialize truthful lifecycle ledger at earliest entry point (Repair 1A)
% Establishes fresh zeroed ledger BEFORE any fallible setup or outer catch invocation
init_ledger = postgate_lifecycle_ledger('init');

stamp = char(datetime('now', 'TimeZone', 'UTC', 'Format', 'yyyyMMdd_HHmmss_SSS'));
output_dir = fullfile(root, 'postpilot_outputs', ['RUNTIME_QUAL_' stamp]);

% Define minimal test matrix: exactly C1 and C2 from qualified records
specs = local_specs(root);

% Comprehensive lifecycle accounting (Blocker 7 & Governance)
receipt = struct('status', 'RUNNER_FAIL', ...
    'production_authorized', false, ...
    'execution_timestamp_utc', char(datetime('now', 'TimeZone', 'UTC', 'Format', 'yyyy-MM-dd HH:mm:ss')), ...
    'environment', struct('MATLAB', version, 'arch', computer('arch'), 'OS', char(system_dependent('getos'))), ...
    'policy', struct( ...
        'max_authorized_physical_simulations', 4, ...
        'fresh_pair_execution_required', true, ...
        'historical_hdf5_role', 'THIRD_PROVENANCE_DELIVERY_CHECK_ONLY', ...
        'in_memory_canonical_check_required', true, ...
        'fresh_hdf5_delivery_check_required', true, ...
        'authoritative_observer_gate_required', true, ...
        'effective_config_inspection_required', true, ...
        'live_co_replay_executed', false, ...
        'speedup_threshold_enforced_for_equivalence', false), ...
    'stage0_preflight', struct(), ...
    'stage1_representative', struct(), ...
    'stage2_contrasting', struct(), ...
    'run_accounting', init_ledger, ...
    'physical_simulations_executed', 0, ...
    'stage1_passed', false, ...
    'stage2_executed', false, ...
    'stage2_passed', false, ...
    'summary', struct(), ...
    'warnings', {{}}, 'errors', {{}});

local_write_json(result_path, receipt);

try
    models = shape.load_models(code_dir);
    manifest_path = fullfile(root, 'docs', 'codex_active', 'manifests', ...
        'PILOT24_MANIFEST_CANDIDATE.parquet');
    [manifest, manifest_report] = shape.validate_manifest(manifest_path);

    % Configure frozen generator parameters
    cfg = shape.config('performance_instrumentation', true, 'num_workers', 1, ...
        'overwrite', false, 'max_retries', 0, 'run_pilot', true, ...
        'solver_rel_tol', 1e-6, 'solver_abs_tol', 1e-8, 'solver_max_step_s', 1e-3, ...
        'mpc_shared_rnea_enabled', true, 'mpc_mass_backend', 1, ...
        'observer_ctdq_backend', 'finite_difference_batch_mex', ...
        'code_state_id', 'POSTGATE_RUNTIME_QUALIFICATION');
    cfg.active_manifest_sha256 = char(manifest_report.sha256);
    cfg.active_manifest_path = manifest_path;

    % =========================================================================
    % STAGE 0 — NONPHYSICAL PREFLIGHT (0 physical runs)
    % =========================================================================
    fprintf('\n>>> Executing Stage 0: Nonphysical Preflight...\n');
    preflight = postgate_preflight(root, specs);
    receipt.stage0_preflight = preflight;
    local_write_json(result_path, receipt);

    if ~strcmp(preflight.status, 'PASS')
        receipt.status = 'STAGE0_PREFLIGHT_FAIL';
        receipt.errors{end+1} = 'Stage 0 preflight failed. Zero physical simulations executed.';
        local_write_json(result_path, receipt);
        fprintf('Stage 0 failed: %s. Halting.\n', preflight.status);
        return;
    end
    fprintf('>>> Stage 0 Preflight PASSED.\n');

    % Extract manifest rows for selected records
    idx_c1 = find(string(manifest.run_uid) == string(specs(1).uid), 1);
    idx_c2 = find(string(manifest.run_uid) == string(specs(2).uid), 1);
    row_c1 = manifest(idx_c1, :);
    row_c2 = manifest(idx_c2, :);

    % =========================================================================
    % STAGE 1 — FRESH PAIR: C1 NORMAL VS C1 ACCELERATOR (Fly, LoE, K=3)
    % Physical runs: exactly 2
    % =========================================================================
    fprintf('\n>>> Executing Stage 1: Fresh Pair on C1 (%s)...\n', specs(1).uid);
    if ~isfolder(output_dir), mkdir(output_dir); end

    % 1.1 Fresh Normal Mode Baseline Run (Run #1)
    fprintf('  [1/4] Running Fresh Normal Mode Baseline (C1)...\n');
    res_c1_normal = postgate_simulate_record(row_c1, models, output_dir, cfg, 'normal', 'C1_normal');
    receipt.run_accounting = postgate_lifecycle_ledger('get');
    receipt.physical_simulations_executed = receipt.run_accounting.physical_sims_started;
    local_write_json(result_path, receipt);

    % 1.2 Fresh Accelerator Mode Candidate Run (Run #2)
    fprintf('  [2/4] Running Fresh Accelerator Mode Candidate (C1)...\n');
    res_c1_accel = postgate_simulate_record(row_c1, models, output_dir, cfg, 'accelerator', 'C1_accelerator');
    receipt.run_accounting = postgate_lifecycle_ledger('get');
    receipt.physical_simulations_executed = receipt.run_accounting.physical_sims_started;
    local_write_json(result_path, receipt);

    % 1.3 Mode Verification & Fallback Detection (Blocker 4)
    normal_mode_ok = strcmp(res_c1_normal.actual_mode, 'normal');
    accel_mode_ok = strcmp(res_c1_accel.actual_mode, 'accelerator');
    fallback_c1 = res_c1_accel.fallback_detected || ~accel_mode_ok || ~normal_mode_ok;
    if fallback_c1
        receipt.warnings{end+1} = sprintf('Stage 1 mode mismatch: Normal actual=%s, Accel actual=%s (fallback=%d)', ...
            res_c1_normal.actual_mode, res_c1_accel.actual_mode, res_c1_accel.fallback_detected);
    end

    % 1.4 Dual-Layer Equivalence Verification (Level 1A + Level 1B + Level 2)
    fprintf('  Verifying Scientific Equivalence for C1 (In-Memory + Fresh HDF5 + Provenance)...\n');
    equiv_c1 = postgate_compare_equivalence(res_c1_normal, res_c1_accel, specs(1), models, cfg);

    % 1.5 Unattributed Walltime Diagnostic (Signed Remainder & In-Simulation Context Benchmark)
    diag_c1 = postgate_unattributed_diagnostic(res_c1_accel.profile, res_c1_accel.telemetry, models, res_c1_accel.prep);

    speedup_c1 = res_c1_normal.sim_wall_s / max(1e-6, res_c1_accel.sim_wall_s);

    stage1 = struct();
    stage1.label = specs(1).label;
    stage1.uid = specs(1).uid;
    stage1.mode = specs(1).mode;
    stage1.fault = specs(1).fault;
    stage1.K = specs(1).K;
    stage1.normal_baseline = struct('sim_wall_s', res_c1_normal.sim_wall_s, ...
        'actual_mode', res_c1_normal.actual_mode, 'path', res_c1_normal.path);
    stage1.accelerator_candidate = struct('sim_wall_s', res_c1_accel.sim_wall_s, ...
        'actual_mode', res_c1_accel.actual_mode, 'fallback_detected', fallback_c1, 'path', res_c1_accel.path);
    stage1.speedup_factor = speedup_c1;
    stage1.speedup_evaluation = struct('faster', speedup_c1 > 1.0, ...
        'speedup_factor', speedup_c1, ...
        'timing_semantics', 'FIRST_INVOCATION_COMPILE_INCLUSIVE', ...
        'note', 'Speedup reported for characterization; not an equivalence gate criterion.');
    stage1.equivalence = equiv_c1;
    stage1.unattributed_diagnostic = diag_c1;
    receipt.stage1_representative = stage1;
    local_write_json(result_path, receipt);

    % 1.6 Stage 1 Hard Stop Gate
    stage1_pass = equiv_c1.pass && ~fallback_c1;
    receipt.stage1_passed = stage1_pass;

    if ~equiv_c1.pass
        receipt.status = 'STAGE1_EQUIVALENCE_FAIL';
        receipt.errors{end+1} = sprintf('Stage 1 failed equivalence: %s', equiv_c1.qualification_label);
        local_write_json(result_path, receipt);
        fprintf('Stage 1 Equivalence Gate FAILED (%s). Stopping at 2 physical simulations.\n', equiv_c1.qualification_label);
        return;
    end

    if fallback_c1
        receipt.status = 'STAGE1_FALLBACK_DETECTED';
        receipt.errors{end+1} = 'Stage 1 requested Accelerator mode, but Simulink fell back or mode mismatched. Stopping.';
        local_write_json(result_path, receipt);
        fprintf('Stage 1 Fallback Detected. Stopping at 2 physical simulations.\n');
        return;
    end

    fprintf('>>> Stage 1 PASSED: 100%% scientific equivalence confirmed. (Speedup: %.3fx - FIRST_INVOCATION_COMPILE_INCLUSIVE)\n', speedup_c1);

    % =========================================================================
    % STAGE 2 — FRESH PAIR: C2 NORMAL VS C2 ACCELERATOR (Stop, LoE, K=2)
    % Only executed if Stage 1 passes all criteria.
    % Physical runs: 2 (total 4)
    % =========================================================================
    fprintf('\n>>> Executing Stage 2: Fresh Pair on Contrasting Record C2 (%s)...\n', specs(2).uid);
    receipt.stage2_executed = true;

    % 2.1 Fresh Normal Mode Baseline Run (Run #3)
    fprintf('  [3/4] Running Fresh Normal Mode Baseline (C2)...\n');
    res_c2_normal = postgate_simulate_record(row_c2, models, output_dir, cfg, 'normal', 'C2_normal');
    receipt.run_accounting = postgate_lifecycle_ledger('get');
    receipt.physical_simulations_executed = receipt.run_accounting.physical_sims_started;
    local_write_json(result_path, receipt);

    % 2.2 Fresh Accelerator Mode Candidate Run (Run #4)
    fprintf('  [4/4] Running Fresh Accelerator Mode Candidate (C2)...\n');
    res_c2_accel = postgate_simulate_record(row_c2, models, output_dir, cfg, 'accelerator', 'C2_accelerator');
    receipt.run_accounting = postgate_lifecycle_ledger('get');
    receipt.physical_simulations_executed = receipt.run_accounting.physical_sims_started;
    local_write_json(result_path, receipt);

    normal_c2_ok = strcmp(res_c2_normal.actual_mode, 'normal');
    accel_c2_ok = strcmp(res_c2_accel.actual_mode, 'accelerator');
    fallback_c2 = res_c2_accel.fallback_detected || ~accel_c2_ok || ~normal_c2_ok;
    equiv_c2 = postgate_compare_equivalence(res_c2_normal, res_c2_accel, specs(2), models, cfg);
    diag_c2 = postgate_unattributed_diagnostic(res_c2_accel.profile, res_c2_accel.telemetry, models, res_c2_accel.prep);
    speedup_c2 = res_c2_normal.sim_wall_s / max(1e-6, res_c2_accel.sim_wall_s);

    stage2 = struct();
    stage2.label = specs(2).label;
    stage2.uid = specs(2).uid;
    stage2.mode = specs(2).mode;
    stage2.fault = specs(2).fault;
    stage2.K = specs(2).K;
    stage2.normal_baseline = struct('sim_wall_s', res_c2_normal.sim_wall_s, ...
        'actual_mode', res_c2_normal.actual_mode, 'path', res_c2_normal.path);
    stage2.accelerator_candidate = struct('sim_wall_s', res_c2_accel.sim_wall_s, ...
        'actual_mode', res_c2_accel.actual_mode, 'fallback_detected', fallback_c2, 'path', res_c2_accel.path);
    stage2.speedup_factor = speedup_c2;
    stage2.speedup_evaluation = struct('faster', speedup_c2 > 1.0, ...
        'speedup_factor', speedup_c2, ...
        'timing_semantics', 'FIRST_INVOCATION_COMPILE_INCLUSIVE', ...
        'note', 'Speedup reported for characterization; not an equivalence gate criterion.');
    stage2.equivalence = equiv_c2;
    stage2.unattributed_diagnostic = diag_c2;
    receipt.stage2_contrasting = stage2;

    stage2_pass = equiv_c2.pass && ~fallback_c2;
    receipt.stage2_passed = stage2_pass;

    if ~equiv_c2.pass
        receipt.status = 'STAGE2_EQUIVALENCE_FAIL';
        receipt.errors{end+1} = sprintf('Stage 2 failed equivalence: %s', equiv_c2.qualification_label);
        local_write_json(result_path, receipt);
        fprintf('Stage 2 Equivalence Gate FAILED (%s).\n', equiv_c2.qualification_label);
        return;
    end

    if fallback_c2
        receipt.status = 'STAGE2_FALLBACK_DETECTED';
        receipt.errors{end+1} = 'Stage 2 requested Accelerator mode, but Simulink fell back or mode mismatched.';
        local_write_json(result_path, receipt);
        fprintf('Stage 2 Fallback Detected.\n');
        return;
    end

    receipt.status = 'QUALIFICATION_PASS';
    receipt.summary = struct( ...
        'total_physical_simulations', receipt.physical_simulations_executed, ...
        'c1_normal_sim_s', res_c1_normal.sim_wall_s, ...
        'c1_accelerator_sim_s', res_c1_accel.sim_wall_s, ...
        'c1_speedup', speedup_c1, ...
        'c1_speedup_semantics', 'FIRST_INVOCATION_COMPILE_INCLUSIVE', ...
        'c2_normal_sim_s', res_c2_normal.sim_wall_s, ...
        'c2_accelerator_sim_s', res_c2_accel.sim_wall_s, ...
        'c2_speedup', speedup_c2, ...
        'c2_speedup_semantics', 'FIRST_INVOCATION_COMPILE_INCLUSIVE', ...
        'c1_raw_unattributed_remainder_s', diag_c1.measured_in_simulation.raw_unattributed_remainder_s, ...
        'c1_newly_recomputed_unattributed_remainder_s', diag_c1.measured_in_simulation.newly_recomputed_unattributed_remainder_s, ...
        'c1_measured_computed_torque_total_s', diag_c1.measured_in_simulation.measured_computed_torque_total_s, ...
        'c1_measured_mpc_dynamics_constraint_s', diag_c1.measured_in_simulation.measured_mpc_dynamics_constraint_s, ...
        'c1_measured_mpc_b1_robot_dynamics_s', diag_c1.measured_in_simulation.measured_mpc_b1_robot_dynamics_s, ...
        'c1_measured_mpc_b1a_shared_kinematics_s', diag_c1.measured_in_simulation.measured_mpc_b1a_shared_kinematics_s, ...
        'c1_measured_mpc_b1b_mass_matrix_s', diag_c1.measured_in_simulation.measured_mpc_b1b_mass_matrix_s, ...
        'c1_measured_mpc_b1c_bias_friction_s', diag_c1.measured_in_simulation.measured_mpc_b1c_bias_friction_s, ...
        'c1_measured_mpc_b1abc_sum_s', diag_c1.measured_in_simulation.measured_mpc_b1abc_sum_s, ...
        'c1_measured_mpc_b1abc_reconciliation_error_s', diag_c1.measured_in_simulation.measured_mpc_b1abc_reconciliation_error_s, ...
        'c1_measured_mpc_b2_block_torque_s', diag_c1.measured_in_simulation.measured_mpc_b2_block_torque_s, ...
        'c1_measured_mpc_b3_constraint_assembly_s', diag_c1.measured_in_simulation.measured_mpc_b3_constraint_assembly_s, ...
        'c1_measured_mpc_b123_sum_s', diag_c1.measured_in_simulation.measured_mpc_b123_sum_s, ...
        'c1_measured_mpc_b123_reconciliation_error_s', diag_c1.measured_in_simulation.measured_mpc_b123_reconciliation_error_s, ...
        'c1_clipped_unattributed_remainder_s', diag_c1.measured_in_simulation.clipped_unattributed_remainder_s, ...
        'c1_raw_estimated_unattributed_remainder_s', diag_c1.estimated_decomposition.raw_estimated_unattributed_remainder_s, ...
        'c2_raw_unattributed_remainder_s', diag_c2.measured_in_simulation.raw_unattributed_remainder_s, ...
        'c2_newly_recomputed_unattributed_remainder_s', diag_c2.measured_in_simulation.newly_recomputed_unattributed_remainder_s, ...
        'c2_measured_computed_torque_total_s', diag_c2.measured_in_simulation.measured_computed_torque_total_s, ...
        'c2_measured_mpc_dynamics_constraint_s', diag_c2.measured_in_simulation.measured_mpc_dynamics_constraint_s, ...
        'c2_measured_mpc_b1_robot_dynamics_s', diag_c2.measured_in_simulation.measured_mpc_b1_robot_dynamics_s, ...
        'c2_measured_mpc_b1a_shared_kinematics_s', diag_c2.measured_in_simulation.measured_mpc_b1a_shared_kinematics_s, ...
        'c2_measured_mpc_b1b_mass_matrix_s', diag_c2.measured_in_simulation.measured_mpc_b1b_mass_matrix_s, ...
        'c2_measured_mpc_b1c_bias_friction_s', diag_c2.measured_in_simulation.measured_mpc_b1c_bias_friction_s, ...
        'c2_measured_mpc_b1abc_sum_s', diag_c2.measured_in_simulation.measured_mpc_b1abc_sum_s, ...
        'c2_measured_mpc_b1abc_reconciliation_error_s', diag_c2.measured_in_simulation.measured_mpc_b1abc_reconciliation_error_s, ...
        'c2_measured_mpc_b2_block_torque_s', diag_c2.measured_in_simulation.measured_mpc_b2_block_torque_s, ...
        'c2_measured_mpc_b3_constraint_assembly_s', diag_c2.measured_in_simulation.measured_mpc_b3_constraint_assembly_s, ...
        'c2_measured_mpc_b123_sum_s', diag_c2.measured_in_simulation.measured_mpc_b123_sum_s, ...
        'c2_measured_mpc_b123_reconciliation_error_s', diag_c2.measured_in_simulation.measured_mpc_b123_reconciliation_error_s, ...
        'c2_clipped_unattributed_remainder_s', diag_c2.measured_in_simulation.clipped_unattributed_remainder_s, ...
        'c2_raw_estimated_unattributed_remainder_s', diag_c2.estimated_decomposition.raw_estimated_unattributed_remainder_s, ...
        'level1a_in_memory_equivalence_confirmed', true, ...
        'level1b_fresh_delivery_equivalence_confirmed', true, ...
        'level2_historical_provenance_confirmed', true, ...
        'observer_provenance_confirmed', true, ...
        'effective_config_confirmed', true, ...
        'zero_fallback_confirmed', true, ...
        'production_authorized', false);

    local_write_json(result_path, receipt);
    fprintf('\n>>> QUALIFICATION STAGE COMPLETE: ALL CRITERIA PASSED.\n');
    fprintf('Total physical simulations: %d (Max: 4)\n', receipt.physical_simulations_executed);
    fprintf('Receipt written to: %s\n', result_path);

catch ME
    if bdIsLoaded(model_name)
        try close_system(model_name, 0); catch; end
    end
    receipt.run_accounting = postgate_lifecycle_ledger('get');
    receipt.physical_simulations_executed = receipt.run_accounting.physical_sims_started;
    receipt.status = 'QUALIFICATION_ERROR';
    receipt.errors{end+1} = struct('identifier', ME.identifier, 'message', ME.message);
    local_write_json(result_path, receipt);
    fprintf('Runner caught fatal exception: %s\n', ME.message);
end

if bdIsLoaded(model_name)
    try close_system(model_name, 0); catch; end
end

receipt.production_authorized = false;
local_write_json(result_path, receipt);

end

function specs = local_specs(root)
specs = [ ...
    struct('label', 'C1', 'uid', '8167b058-dc6e-3b0a-b6b0-0478265cd56a', ...
        'parent', 9002, 'mode', 'fly', 'fault', 'LoE', 'K', 3, ...
        'reference_path', fullfile(root, 'pilot24_outputs', 'PILOT24_CANONICAL_V2', 'parent_9001_9100', 'run_8167b058-dc6e-3b0a-b6b0-0478265cd56a.h5'), ...
        'reference_sha256', '394999422a46b1a83e4e2c128a0f0f94e5d46243a27c5019c85abe44c4769022', ...
        'trajectory_sha256', 'd9faca027ff832f67a42281665e3e3d866a6f253f84623c76c191db10b047469'), ...
    struct('label', 'C2', 'uid', '216a0075-20d7-34a6-aded-c2198b018f7d', ...
        'parent', 9015, 'mode', 'stop', 'fault', 'LoE', 'K', 2, ...
        'reference_path', fullfile(root, 'pilot24_outputs', 'PILOT24_CANONICAL_V2', 'parent_9001_9100', 'run_216a0075-20d7-34a6-aded-c2198b018f7d.h5'), ...
        'reference_sha256', 'a5ab4db31c8b86066b86e765e772e850dc98623f423cd3d0b7e5620e9be9bc4f', ...
        'trajectory_sha256', '3e30070554287033a074f38e592736e374755b89611113a647ee38c66d9d3bc8') ...
];
end

function local_write_json(path, data)
fid = fopen(path, 'w');
if fid < 0, return; end
c = onCleanup(@() fclose(fid));
fprintf(fid, '%s', jsonencode(data, 'PrettyPrint', true));
clear c;
end

function local_cleanup_model(model_name)
if bdIsLoaded(model_name)
    try close_system(model_name, 0); catch; end
end
end

