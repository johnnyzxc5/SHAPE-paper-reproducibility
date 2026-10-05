function receipt = postgate_preflight(root, specs)
%POSTGATE_PREFLIGHT Stage 0 nonphysical verification for runtime qualification.
% Zero physical simulations executed. Validates prerequisites, hashes, and environment.
% Enforces fail-closed policy: if any prerequisite is missing or invalid, halts immediately.

if nargin < 1 || isempty(root)
    root = fileparts(fileparts(fileparts(mfilename('fullpath'))));
end
if nargin < 2 || isempty(specs)
    specs = local_default_specs(root);
end
code_dir = fullfile(root, 'Code_Image');
addpath(code_dir);
addpath(genpath(fullfile(code_dir, 'MATLAB', 'mr')));

receipt = struct('status', 'PREFLIGHT_FAIL', ...
    'production_authorized', false, ...
    'timestamp_utc', char(datetime('now', 'TimeZone', 'UTC', 'Format', 'yyyy-MM-dd HH:mm:ss')), ...
    'environment', struct('MATLAB', version, 'arch', computer('arch'), 'OS', char(system_dependent('getos'))), ...
    'model_check', struct('available', false, 'name', 'Kinova_Fault_Simulator', 'slx_path', '', 'slxc_path', ''), ...
    'solver_check', struct('solver', 'ode45', 'rel_tol', 1e-6, 'abs_tol', 1e-8, 'max_step', 1e-3, ...
        'mpc_chart_found', false, 'mpc_chart_update', 'UNKNOWN', 'mpc_inherited_valid', false, ...
        'computed_torque_chart_found', false, 'computed_torque_chart_update', 'UNKNOWN', 'computed_torque_inherited_valid', false, ...
        'controller_scheduling_semantics', 'inherited/continuous (-1)', ...
        'sample_time_mpc', 'UNKNOWN', 'sample_time_ct', 'UNKNOWN', 'valid', false), ...
    'accelerator_check', struct('compiler_available', false, 'compiler_name', '', 'compiler_version', ''), ...
    'extrinsic_boundary_check', struct('flatness_mpc_extrinsic', false, 'computed_torque_extrinsic', false, 'plant_dirty_inlined', false), ...
    'observer_mex_check', struct('available', false, 'mex_sha256', '', 'expected_mex_sha256', '', 'mex_hash_match', false, ...
        'source_available', false, 'source_sha256', '', 'expected_source_sha256', '', 'source_hash_match', false, ...
        'selftest_pass', false, 'selftest_status', ''), ...
    'runtime_context_check', struct('set_get_pass', false, 'clear_pass', false), ...
    'instrumentation_check', struct('available', false, 'p0_reset_pass', false), ...
    'w4_candidate_check', struct('available', false, 'path', '', 'actual_sha256', '', ...
        'expected_candidate_sha256', '1d12979ed026047086b586e50b089965369d2a462f5b0d42724efba376814f32', ...
        'rollback_authority_sha256', 'b5371e3c970036c8af94efb4aca9544c2695f100be8a7ed633884e76bd5ed7b5', ...
        'valid', false), ...
    'mass_matrix_check', struct('available', false, 'path', '', 'actual_sha256', '', ...
        'expected_active_sha256', '8a72d91b1c7e7ef17e5830a09cad756f4d6b45c03d793deae2506f888683e68f', ...
        'expected_rollback_sha256', '9d2d89912ae949b288da17131b3e46c0314e79875c71621731dcb09edb8e029a', ...
        'is_active_authority', false, 'is_rollback_authority', false, 'valid', false), ...
    'reference_cases_check', struct([]), ...
    'warnings', {{}}, 'errors', {{}});

try
    models = shape.load_models(code_dir);
    cfg = shape.config();

    % 1. Model Check
    model_name = 'Kinova_Fault_Simulator';
    slx_file = fullfile(code_dir, [model_name '.slx']);
    slxc_file = fullfile(code_dir, [model_name '.slxc']);
    receipt.model_check.slx_path = slx_file;
    receipt.model_check.slxc_path = slxc_file;
    receipt.model_check.available = isfile(slx_file);
    if ~receipt.model_check.available
        receipt.errors{end+1} = sprintf('Model file missing: %s', slx_file);
    end

    % 2. Solver & Scheduling Parameters Check (Trustworthy Simulink Model Inspection)
    if receipt.model_check.available
        load_system(model_name);
        solver = get_param(model_name, 'Solver');
        rel_tol = str2double(get_param(model_name, 'RelTol'));
        abs_tol = str2double(get_param(model_name, 'AbsTol'));
        max_step = str2double(get_param(model_name, 'MaxStep'));
        receipt.solver_check.solver = solver;
        receipt.solver_check.rel_tol = rel_tol;
        receipt.solver_check.abs_tol = abs_tol;
        receipt.solver_check.max_step = max_step;

        % Resolve Stateflow charts for Flatness-MPC and Computed-Torque (Authoritative Scheduling Gate)
        rt = sfroot();
        charts_mpc = rt.find('-isa', 'Stateflow.EMChart', 'Path', [model_name '/MATLAB Function1']);
        charts_ct = rt.find('-isa', 'Stateflow.EMChart', 'Path', [model_name '/MATLAB Function']);

        mpc_found = isscalar(charts_mpc) && isa(charts_mpc, 'Stateflow.EMChart');
        ct_found = isscalar(charts_ct) && isa(charts_ct, 'Stateflow.EMChart');

        mpc_update = 'UNKNOWN';
        if mpc_found
            try mpc_update = char(string(charts_mpc.ChartUpdate)); catch; end
        end

        ct_update = 'UNKNOWN';
        if ct_found
            try ct_update = char(string(charts_ct.ChartUpdate)); catch; end
        end

        mpc_inherited_valid = mpc_found && strcmp(mpc_update, 'INHERITED');
        ct_inherited_valid = ct_found && strcmp(ct_update, 'INHERITED');

        receipt.solver_check.mpc_chart_found = mpc_found;
        receipt.solver_check.mpc_chart_update = mpc_update;
        receipt.solver_check.mpc_inherited_valid = mpc_inherited_valid;
        receipt.solver_check.computed_torque_chart_found = ct_found;
        receipt.solver_check.computed_torque_chart_update = ct_update;
        receipt.solver_check.computed_torque_inherited_valid = ct_inherited_valid;
        receipt.solver_check.controller_scheduling_semantics = 'inherited/continuous (historical SampleTime=-1)';
        receipt.solver_check.sample_time_mpc = mpc_update;
        receipt.solver_check.sample_time_ct = ct_update;

        if ~mpc_inherited_valid
            receipt.errors{end+1} = sprintf('Flatness-MPC Stateflow chart (%s/MATLAB Function1) invalid or ChartUpdate is %s (expected INHERITED)', ...
                model_name, mpc_update);
        end
        if ~ct_inherited_valid
            receipt.errors{end+1} = sprintf('Computed-Torque Stateflow chart (%s/MATLAB Function) invalid or ChartUpdate is %s (expected INHERITED)', ...
                model_name, ct_update);
        end

        receipt.solver_check.valid = strcmp(solver, 'ode45') && ...
            rel_tol == 1e-6 && ...
            abs_tol == 1e-8 && ...
            max_step == 1e-3 && ...
            mpc_inherited_valid && ct_inherited_valid;

        if ~receipt.solver_check.valid && mpc_inherited_valid && ct_inherited_valid
            receipt.warnings{end+1} = 'Model default solver settings differ from canonical runtime parameters (will be enforced via set_param on loaded model and SimulationInput before simulation).';
        end
    end

    % 3. Accelerator Compiler Check (Fail-Closed: Compiler is required for Accelerator mode)
    compilers = mex.getCompilerConfigurations('C++', 'Selected');
    if ~isempty(compilers)
        receipt.accelerator_check.compiler_available = true;
        receipt.accelerator_check.compiler_name = compilers(1).Name;
        receipt.accelerator_check.compiler_version = compilers(1).Version;
    else
        receipt.accelerator_check.compiler_available = false;
        receipt.errors{end+1} = 'No C++ compiler selected via mex -setup. Accelerator mode qualification requires an active C++ compiler.';
    end

    % 4. Extrinsic Boundary Verification (Inspect Stateflow code without modifying)
    rt = sfroot();
    m = rt.find('-isa', 'Stateflow.Machine', 'Name', model_name);
    if ~isempty(m)
        charts = m.find('-isa', 'Stateflow.EMChart');
        for c_idx = 1:numel(charts)
            c = charts(c_idx);
            s_name = c.Name;
            s_code = c.Script;
            if contains(s_name, 'Flatness_MPC') || contains(s_code, 'solve_flatness_mpc_runtime_MR')
                receipt.extrinsic_boundary_check.flatness_mpc_extrinsic = contains(s_code, "coder.extrinsic('solve_flatness_mpc_runtime_MR')");
            end
            if contains(s_name, 'Computed_Torque') || contains(s_code, 'inverse_dynamics_kinova_')
                receipt.extrinsic_boundary_check.computed_torque_extrinsic = ...
                    contains(s_code, "coder.extrinsic('inverse_dynamics_kinova_runtime_MR')") || ...
                    contains(s_code, "coder.extrinsic('inverse_dynamics_kinova_MR')");
            end
            if contains(s_name, 'Plant_Dirty') || contains(s_code, 'kinova_state_space_sucia_MR')
                receipt.extrinsic_boundary_check.plant_dirty_inlined = ~contains(s_code, "coder.extrinsic");
            end
        end
    end

    % 5. Observer MEX & Source Integrity Verification (Authoritative Fail-Closed Gate)
    mex_path = fullfile(cfg.observer_ctdq_mex_dir, ['ctdq_finite_difference_batch_mex.' mexext]);
    source_path = fullfile(code_dir, 'ctdq_finite_difference_batch_mex_source.m');

    receipt.observer_mex_check.available = isfile(mex_path);
    receipt.observer_mex_check.source_available = isfile(source_path);
    receipt.observer_mex_check.expected_mex_sha256 = cfg.observer_ctdq_mex_expected_sha256;
    receipt.observer_mex_check.expected_source_sha256 = cfg.observer_ctdq_source_expected_sha256;

    if receipt.observer_mex_check.available
        receipt.observer_mex_check.mex_sha256 = char(shape.sha256_file(mex_path));
        receipt.observer_mex_check.mex_hash_match = strcmpi(receipt.observer_mex_check.mex_sha256, ...
            receipt.observer_mex_check.expected_mex_sha256);
        if ~receipt.observer_mex_check.mex_hash_match
            receipt.errors{end+1} = sprintf('Observer MEX hash mismatch. Expected: %s, Actual: %s', ...
                receipt.observer_mex_check.expected_mex_sha256, receipt.observer_mex_check.mex_sha256);
        end
    else
        receipt.errors{end+1} = sprintf('Observer MEX file missing: %s', mex_path);
    end

    if receipt.observer_mex_check.source_available
        receipt.observer_mex_check.source_sha256 = char(shape.sha256_file(source_path));
        receipt.observer_mex_check.source_hash_match = strcmpi(receipt.observer_mex_check.source_sha256, ...
            receipt.observer_mex_check.expected_source_sha256);
        if ~receipt.observer_mex_check.source_hash_match
            receipt.errors{end+1} = sprintf('Observer source hash mismatch. Expected: %s, Actual: %s', ...
                receipt.observer_mex_check.expected_source_sha256, receipt.observer_mex_check.source_sha256);
        end
    else
        receipt.errors{end+1} = sprintf('Observer source file missing: %s', source_path);
    end

    % Execute lightweight nonphysical selftest
    selftest = shape.ctdq_mex_selftest(models, cfg);
    receipt.observer_mex_check.selftest_pass = selftest.pass;
    receipt.observer_mex_check.selftest_status = selftest.status;
    if ~selftest.pass
        receipt.errors{end+1} = sprintf('Observer MEX selftest failed: %s (%s)', selftest.status, selftest.reason);
    end

    % 6. Runtime Context Verification
    shape.mpc_runtime_context('clear');
    dummy_prep = struct('Ts', 0.05, 'N', 201, 'nu', 6, 'ny', 6, 'nq', 6, ...
        'Adseq', zeros(12, 12, 1), 'Bdseq', zeros(12, 6, 1), 'Cdseq', zeros(6, 12, 1), ...
        'xop', zeros(12, 201), 'yop', zeros(6, 201), 'uop', zeros(6, 201), ...
        'y_ref', zeros(6, 201), 't', zeros(1, 201), ...
        'P0InstrumentationEnabled', false, 'P2ExactCacheEnabled', true, ...
        'P2ExactCacheVersion', 'p2-exact-invariants-v1', ...
        'P3SharedRNEAEnabled', true, 'P3SharedRNEAVersion', 'p3-shared-rnea-v1', ...
        'P4BMassBackend', 1);
    shape.mpc_runtime_context('set', dummy_prep);
    got_prep = shape.mpc_runtime_context('get');
    receipt.runtime_context_check.set_get_pass = isequaln(got_prep.Ts, dummy_prep.Ts);
    shape.mpc_runtime_context('clear');
    ctx_cleared = shape.mpc_runtime_context('snapshot');
    receipt.runtime_context_check.clear_pass = ~ctx_cleared.initialized;
    if ~receipt.runtime_context_check.set_get_pass || ~receipt.runtime_context_check.clear_pass
        receipt.errors{end+1} = 'Runtime context set/get/clear verification failed.';
    end

    % 7. Profiler Instrumentation Check
    shape.p0_profiler('reset', 'preflight-test');
    p0_test = shape.p0_profiler('snapshot');
    receipt.instrumentation_check.available = isstruct(p0_test) && isfield(p0_test, 'controller_entries');
    receipt.instrumentation_check.p0_reset_pass = receipt.instrumentation_check.available && ...
        p0_test.controller_entries == 0;
    if ~receipt.instrumentation_check.available
        receipt.errors{end+1} = 'P0 profiler instrumentation unavailable or malformed.';
    end

    % 8. Reference Cases Check
    ref_cases = struct([]);
    for k = 1:numel(specs)
        s = specs(k);
        case_info = struct('label', s.label, 'uid', s.uid, 'parent', s.parent, ...
            'mode', s.mode, 'fault', s.fault, 'K', s.K, ...
            'ref_path', s.reference_path, 'exists', isfile(s.reference_path), ...
            'actual_sha256', '', 'expected_sha256', s.reference_sha256, 'hash_match', false);
        if case_info.exists
            case_info.actual_sha256 = char(shape.sha256_file(s.reference_path));
            case_info.hash_match = strcmpi(case_info.actual_sha256, s.reference_sha256);
            if ~case_info.hash_match
                receipt.errors{end+1} = sprintf('Reference canonical HDF5 hash mismatch for %s: %s', s.label, s.reference_path);
            end
        else
            receipt.errors{end+1} = sprintf('Reference canonical HDF5 missing for %s: %s', s.label, s.reference_path);
        end
        ref_cases = [ref_cases, case_info]; %#ok<AGROW>
    end
    receipt.reference_cases_check = ref_cases;

    % 9. Exact W4 signed-zero candidate identity (qualification-only gate)
    mpc_file = fullfile(code_dir, 'solve_flatness_mpc_step_MR.m');
    expected_w4_candidate_sha = '1d12979ed026047086b586e50b089965369d2a462f5b0d42724efba376814f32';
    receipt.w4_candidate_check.path = mpc_file;
    receipt.w4_candidate_check.available = isfile(mpc_file);
    if receipt.w4_candidate_check.available
        receipt.w4_candidate_check.actual_sha256 = char(shape.sha256_file(mpc_file));
        receipt.w4_candidate_check.valid = strcmpi(receipt.w4_candidate_check.actual_sha256, expected_w4_candidate_sha);
        if ~receipt.w4_candidate_check.valid
            receipt.errors{end+1} = sprintf('W4 candidate hash mismatch. Expected: %s, Actual: %s', ...
                expected_w4_candidate_sha, receipt.w4_candidate_check.actual_sha256);
        end
    else
        receipt.errors{end+1} = sprintf('MPC controller file missing: %s', mpc_file);
    end

    % 10. MassMatrix Authority Verification (Stage 0.10 Fail-Closed Gate)
    mm_file = fullfile(code_dir, 'MassMatrixZeroStateSharedKinematics_MR.m');
    expected_active_sha = '8a72d91b1c7e7ef17e5830a09cad756f4d6b45c03d793deae2506f888683e68f';
    expected_rollback_sha = '9d2d89912ae949b288da17131b3e46c0314e79875c71621731dcb09edb8e029a';
    receipt.mass_matrix_check.path = mm_file;
    receipt.mass_matrix_check.available = isfile(mm_file);
    receipt.mass_matrix_check.expected_active_sha256 = expected_active_sha;
    receipt.mass_matrix_check.expected_rollback_sha256 = expected_rollback_sha;

    if receipt.mass_matrix_check.available
        receipt.mass_matrix_check.actual_sha256 = char(shape.sha256_file(mm_file));
        receipt.mass_matrix_check.is_active_authority = strcmpi(receipt.mass_matrix_check.actual_sha256, expected_active_sha);
        receipt.mass_matrix_check.is_rollback_authority = strcmpi(receipt.mass_matrix_check.actual_sha256, expected_rollback_sha);
        receipt.mass_matrix_check.valid = receipt.mass_matrix_check.is_active_authority;
        if ~receipt.mass_matrix_check.is_active_authority
            receipt.errors{end+1} = sprintf('MassMatrix authority mismatch. Expected active SHA-256: %s, Actual: %s', ...
                expected_active_sha, receipt.mass_matrix_check.actual_sha256);
        end
    else
        receipt.mass_matrix_check.valid = false;
        receipt.errors{end+1} = sprintf('MassMatrix file missing: %s', mm_file);
    end

    % Status resolution (Fail-Closed)
    has_errors = ~isempty(receipt.errors) || ~receipt.model_check.available || ...
        ~receipt.solver_check.mpc_inherited_valid || ~receipt.solver_check.computed_torque_inherited_valid || ...
        ~receipt.accelerator_check.compiler_available || ...
        ~receipt.observer_mex_check.available || ~receipt.observer_mex_check.mex_hash_match || ...
        ~receipt.observer_mex_check.source_available || ~receipt.observer_mex_check.source_hash_match || ...
        ~receipt.observer_mex_check.selftest_pass || ...
        ~receipt.runtime_context_check.set_get_pass || ~receipt.runtime_context_check.clear_pass || ...
        ~receipt.instrumentation_check.available || ...
        ~receipt.w4_candidate_check.available || ~receipt.w4_candidate_check.valid || ...
        ~receipt.mass_matrix_check.available || ~receipt.mass_matrix_check.valid || ...
        (isempty(receipt.reference_cases_check) || ~all([receipt.reference_cases_check.hash_match]));

    if has_errors
        receipt.status = 'PREFLIGHT_FAIL';
    else
        receipt.status = 'PASS';
    end

catch ME
    receipt.status = 'PREFLIGHT_ERROR';
    receipt.errors{end+1} = struct('identifier', ME.identifier, 'message', ME.message);
end

receipt.production_authorized = false;

end

function specs = local_default_specs(root)
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
