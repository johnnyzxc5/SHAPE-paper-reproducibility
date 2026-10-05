function cfg = config(varargin)
%CONFIG Frozen SHAPE generator constants and configurable engineering knobs.
cfg = struct();
cfg.schema_version = "shape-generator-v1";
cfg.master_seed = uint32(20260913);
cfg.duration_s = 10.0;
cfg.fs_hz = 1000;
cfg.telemetry_dt_s = 1/cfg.fs_hz;
cfg.n_time = 10001;
cfg.solver_rel_tol = 1e-6;
cfg.solver_abs_tol = 1e-8;
cfg.solver_max_step_s = 1e-3; % non-final candidate; [] selects model/default auto
cfg.solver_candidate_status = 'PRODUCTION_RATIFIED_FROZEN';
cfg.target_joint = 2;
cfg.tau_max = [39;39;39;9;9;9];
cfg.dq_max = [1.3962634016;1.3962634016;1.3962634016;1.2217304764;1.2217304764;1.2217304764];
cfg.power_ref = cfg.tau_max .* cfg.dq_max;
cfg.robot_power_ref = 196.3495;
cfg.rotor_inertia = diag([0.172 0.172 0.172 0.089 0.089 0.089]);
cfg.gravity = [0;0;-9.80665];
cfg.observer_gain = 100.0;
cfg.observer_ctdq_backend = 'finite_difference_batch_mex';
cfg.observer_ctdq_mex_dir = fullfile(fileparts(fileparts(mfilename('fullpath'))), ...
    'generated','p1_ctdq_mex');
cfg.observer_ctdq_mex_enabled = true;
cfg.observer_ctdq_backend_version = 'p1b-fd-central-h1e-6-v1';
cfg.observer_ctdq_gold_version = 'fd-central-h1e-6-gold-v1';
cfg.observer_ctdq_mex_expected_sha256 = '9dda22245d4f649854c9f3b7f9ad04527e288a2342ef5468c5a70020ddf12f5c';
cfg.observer_ctdq_source_expected_sha256 = 'b99e2a6b3185a6af0f4f8db7b720fe5dfa4f90b4bb45c4c6b28b978c6d7e13c0';
cfg.observer_ctdq_qualified_arch = 'win64';
cfg.observer_ctdq_qualified_matlab = '26.1.0.3312084 (R2026a) Update 4';
cfg.observer_ctdq_qualified_coder_major_minor = '26.1';
cfg.observer_ctdq_qualified_compiler = 'MinGW64 Compiler (C++)';
cfg.observer_ctdq_qualified_compiler_version = '14.2.0';
cfg.observer_ctdq_selftest_enabled = true;
cfg.observer_ctdq_selftest_tolerance_Nm = 5e-9;
cfg.cwt_wavelet = 'amor';
cfg.voices_per_octave = 32;
cfg.frequency_limits_hz = [1 100];
cfg.output_size = [224 448];
cfg.coi_gamma = 0.80;
cfg.power_epsilon = 1e-10;
cfg.log_floor_db = -100.0;
cfg.e2b_frequencies_hz = [2 5 8 11 14 17 20 23 26 30];
cfg.e4_velocity_snr_db = [40 30 20 10];
cfg.e4_position_sigma_deg = [0.01 0.05 0.20];
cfg.num_workers = [];
cfg.use_gpu = false;
cfg.fast_restart = true;
cfg.compression = 'none';
cfg.e4_retention = 'on_the_fly';
cfg.e4_calibration = struct('state','CALIBRATION_NOT_YET_FROZEN', ...
    'pooled_velocity_rms',[],'source','');
cfg.e4_pilot_validate_candidate = true;
cfg.e4_candidate_validation_runs = 1;
cfg.e4_output_dir = '';
cfg.overwrite = false;
cfg.run_pilot = false;
cfg.max_retries = 1;
cfg.observer_gold_provider = [];
cfg.observer_gold_nominal_only = true;
cfg.active_manifest_sha256 = '';
cfg.active_manifest_path = '';
cfg.code_state_id = '';
cfg.performance_instrumentation = false;
cfg.performance_resource_sample_s = 1.0;
cfg.mpc_shared_rnea_enabled = false;
cfg.mpc_shared_rnea_version = 'p3-shared-rnea-v1';
cfg.mpc_mass_backend = 0; % 0=P3 baseline, 1=Qualified zero-state mass (SHA: 8a72d91b...)
cfg.trajectory_registry_dir = fullfile(fileparts(fileparts(fileparts(mfilename('fullpath')))), ...
    'data','trajectory_registry','pilot24','v2');
cfg.trajectory_binding_path = fullfile(fileparts(fileparts(fileparts(mfilename('fullpath')))), ...
    'docs','codex_active','manifests','PILOT24_TRAJECTORY_BINDING_CANDIDATE_V2.parquet');
cfg.trajectory_max_attempts = 500;
for k = 1:2:numel(varargin)
    name = char(varargin{k});
    if ~isfield(cfg, name), error('shape:config:UnknownOption','Unknown option %s.',name); end
    cfg.(name) = varargin{k+1};
end
assert(cfg.n_time == round(cfg.duration_s*cfg.fs_hz)+1);
assert(isempty(cfg.solver_max_step_s) || ...
    (isscalar(cfg.solver_max_step_s) && cfg.solver_max_step_s>0));
assert(cfg.max_retries>=0 && cfg.max_retries==floor(cfg.max_retries));
assert(cfg.trajectory_max_attempts==500);
assert(islogical(cfg.performance_instrumentation) && isscalar(cfg.performance_instrumentation));
assert(isscalar(cfg.performance_resource_sample_s) && cfg.performance_resource_sample_s>0);
assert(islogical(cfg.mpc_shared_rnea_enabled) && isscalar(cfg.mpc_shared_rnea_enabled));
assert(strcmp(cfg.mpc_shared_rnea_version,'p3-shared-rnea-v1'));
assert(isnumeric(cfg.mpc_mass_backend) && isscalar(cfg.mpc_mass_backend) && ...
    any(double(cfg.mpc_mass_backend)==[0 1]));
assert(any(strcmp(cfg.observer_ctdq_backend, ...
    {'finite_difference_gold','finite_difference_batch_mex'})));
assert(islogical(cfg.observer_ctdq_mex_enabled) && isscalar(cfg.observer_ctdq_mex_enabled));
assert(islogical(cfg.observer_ctdq_selftest_enabled) && isscalar(cfg.observer_ctdq_selftest_enabled));
assert(isscalar(cfg.observer_ctdq_selftest_tolerance_Nm) && cfg.observer_ctdq_selftest_tolerance_Nm>=0);
end
