function result = run_record(record,ref,models,output_dir,cfg)
%RUN_RECORD One physical simulation through all generator products.
existing=shape.output_path(output_dir,record);
if isfile(existing) && ~cfg.overwrite
    [resume,recovery]=shape.resume_or_quarantine(existing,string(record.run_uid),cfg,record);
    if resume
        saved_profile=jsondecode(h5readatt(existing,'/','profile_json'));
        if isfield(saved_profile,'observer_gold'), observer_gold=saved_profile.observer_gold;
        else, observer_gold=shape.observer_gold_metrics([],[]); end
        saved_profile.resumed=true;
        result=struct('path',string(existing),'sha256',string(shape.sha256_file(existing)), ...
            'profile',saved_profile,'run_uid',string(record.run_uid), ...
            'recovery',recovery,'retry_count',0,'e4_calibration_stats',[], ...
            'observer_gold',observer_gold);
        return
    end
else
    recovery=struct('state','NO_EXISTING_OUTPUT','quarantine_path','', ...
        'validation_error','');
end
identity=local_identity(record);
log_path=[existing '.recovery.jsonl'];
result=shape.execute_with_retry(@(attempt)local_execute(attempt,record,ref,models, ...
    output_dir,cfg,recovery),identity,cfg,log_path);
end
function result=local_execute(attempt,record,ref,models,output_dir,cfg,recovery)
profile=struct(); total=tic;
if nargin<2 || isempty(ref)
    if contains(upper(string(cfg.active_manifest_path)),'PILOT24')
        error('shape:pilot:FrozenReferenceRequired', ...
            'Canonical Pilot execution prohibits trajectory generation.');
    end
    x=tic; ref=shape.generate_reference(record,models,cfg); profile.reference_s=toc(x);
else
    profile.reference_s=0;
end
x=tic; [telemetry,sp]=shape.simulate_run(record,ref,models,cfg); profile.simulink_s=sp.simulink_s; profile.telemetry_s=toc(x)-sp.simulink_s;
profile.logged_output_points=sp.logged_output_points;
if isfield(cfg,'performance_instrumentation') && cfg.performance_instrumentation
    transfer={'p0','mpc_prepare_s','simulation_input_setup_s','telemetry_extraction_s','final_output_points'};
    for transfer_index=1:numel(transfer)
        if isfield(sp,transfer{transfer_index}), profile.(transfer{transfer_index})=sp.(transfer{transfer_index}); end
    end
end
x=tic; [res,diagnostics]=shape.compute_residuals(telemetry,ref,models,cfg); profile.residuals_s=toc(x);
profile.residual_breakdown=diagnostics.timing;
profile.observer_ctdq=diagnostics.ctdq_backend_details;
if isfield(cfg,'performance_instrumentation') && cfg.performance_instrumentation
    named=diagnostics.timing.algebra_s+diagnostics.timing.mass_matrix_s+ ...
        diagnostics.timing.gravity_s+diagnostics.timing.coriolis_transpose_s+ ...
        diagnostics.timing.friction_s+diagnostics.timing.observer_update_s;
    profile.residual_breakdown.wrapper_remainder_s=max(0,profile.residuals_s-named);
end
if isempty(cfg.observer_gold_provider)
    observer_gold=shape.observer_gold_metrics(res,[]);
else
    gold=cfg.observer_gold_provider(record,telemetry,ref,models,cfg,diagnostics);
    observer_gold=shape.observer_gold_metrics(res,gold);
end
x=tic; normed=shape.normalize_residuals(res,cfg); profile.normalization_s=toc(x);
x=tic; [fft_amp,fft_freq]=shape.compute_fft(normed.shape,cfg); profile.fft_s=toc(x);
x=tic; rep=shape.cwt_representations(normed,cfg); profile.cwt_rebin_s=toc(x);
profile.retry_count=attempt-1; profile.recovery_state=recovery.state;
profile.observer_gold_state=observer_gold.state;
profile.observer_gold=observer_gold;
e4_stats=shape.e4_calibration_stats(telemetry,record);
x=tic; [path,~]=shape.serialize_run(output_dir,record,ref,telemetry,res,normed,rep,fft_amp,fft_freq,profile,cfg); profile.serialization_s=toc(x);
profile.total_s=toc(total);
h5writeatt(path,'/','profile_json',jsonencode(profile));
sha=shape.sha256_file(path);
result=struct('path',string(path),'sha256',string(sha),'profile',profile, ...
    'run_uid',string(record.run_uid),'recovery',recovery,'observer_gold',observer_gold, ...
    'e4_calibration_stats',e4_stats);
end
function identity=local_identity(record)
identity=struct('run_uid',char(string(record.run_uid)), ...
    'parent_trajectory_id',double(record.parent_trajectory_id), ...
    'trajectory_seed',double(record.trajectory_seed), ...
    'parameter_seed',double(record.parameter_seed),'fault_seed',double(record.fault_seed), ...
    'noise_seed',double(record.noise_seed));
end
