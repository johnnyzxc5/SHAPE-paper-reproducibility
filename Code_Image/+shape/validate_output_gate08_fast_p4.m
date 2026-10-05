function timing=validate_output_gate08_fast_p4(path,uid,cfg,record)
%VALIDATE_OUTPUT_GATE08_FAST_P4 Experimental fast validator for P4.
% It reads every required dataset, performs all finite/shape and
% identity/provenance checks without semantic weakening, avoiding
% redundant double allocations and repeated string conversions.

total_clock=tic; assert(isfile(path),'Output does not exist.');
clock=tic; fid=H5F.open(path,'H5F_ACC_RDONLY','H5P_DEFAULT'); cleanup=onCleanup(@()H5F.close(fid));
timing.file_open_s=toc(clock);

persistent cached_checks cached_key
key=[cfg.n_time, cfg.output_size];
if isempty(cached_checks) || ~isequal(cached_key,key)
    cached_checks={ ...
     '/temporal/shape',[6 cfg.n_time],'single'; '/temporal/torque',[6 cfg.n_time],'single'; ...
     '/temporal/gmo',[6 cfg.n_time],'single'; '/temporal/energy',[1 cfg.n_time],'single'; ...
     '/cwt/shape_log',[6 cfg.output_size],'single'; '/cwt/torque_log',[6 cfg.output_size],'single'; ...
     '/cwt/gmo_log',[6 cfg.output_size],'single'; '/cwt/energy_log',cfg.output_size,'single'; ...
     '/cwt/shape_magnitude',[6 cfg.output_size],'single'; '/cwt/torque_magnitude',[6 cfg.output_size],'single'; ...
     '/cwt/gmo_magnitude',[6 cfg.output_size],'single'; '/cwt/energy_magnitude',cfg.output_size,'single'; ...
     '/views/shape_fft_amplitude',[6 1001],'single'; '/coordinates/fft_frequency_hz',[1 1001],'single'; ...
     '/coordinates/cwt_frequency_hz',[1 cfg.output_size(1)],'single'; ...
     '/coordinates/cwt_time_s',[1 cfg.output_size(2)],'single'; ...
     '/coordinates/telemetry_time_s',[1 cfg.n_time],'single'; '/quality/coi_valid_mask',cfg.output_size,'uint8'; ...
     '/telemetry/q_meas',[6 cfg.n_time],'single'; '/telemetry/dq_meas',[6 cfg.n_time],'single'; ...
     '/telemetry/tau_cmd',[6 cfg.n_time],'single'; '/reference/q_ref',[6 cfg.n_time],'single'; ...
     '/reference/dq_ref',[6 cfg.n_time],'single'; '/reference/ddq_ref',[6 cfg.n_time],'single'; ...
     '/reference/tau_nom',[6 cfg.n_time],'single'};
    cached_key=key;
end
checks=cached_checks;

timing.dataset_open_s=0; timing.dataset_read_s=0; timing.dataset_shape_type_s=0; timing.dataset_finite_s=0;
telemetry_time=[];
for k=1:size(checks,1)
    clock=tic; did=H5D.open(fid,checks{k,1}); timing.dataset_open_s=timing.dataset_open_s+toc(clock);
    clock=tic; value=H5D.read(did); timing.dataset_read_s=timing.dataset_read_s+toc(clock); H5D.close(did);
    clock=tic;
    actual=size(value); expected=checks{k,2};
    if ~isequal(actual,expected)
        actual=actual(actual~=1); expected=expected(expected~=1);
        assert(isequal(actual,expected),'Dataset shape mismatch at %s.',checks{k,1});
    end
    assert(strcmp(class(value),checks{k,3}),'Dataset datatype mismatch at %s.',checks{k,1});
    timing.dataset_shape_type_s=timing.dataset_shape_type_s+toc(clock);
    clock=tic; assert(all(isfinite(value(:))),'Nonfinite value at %s.',checks{k,1});
    timing.dataset_finite_s=timing.dataset_finite_s+toc(clock);
    if strcmp(checks{k,1},'/coordinates/telemetry_time_s'), telemetry_time=value; end
end

clock=tic;
assert(strcmp(local_read_attr(fid,'run_uid'),uid),'UID mismatch.');
timing.root_attribute_presence_and_uid_s=toc(clock);

clock=tic; t=double(telemetry_time);
assert(numel(t)==cfg.n_time && abs(t(1))<=eps && abs(t(end)-cfg.duration_s)<=1e-6, ...
    'Telemetry endpoints are invalid.');
timing.reused_timebase_check_s=toc(clock);

clock=tic;
assert(strcmp(local_read_attr(fid,'normalization'),'fixed_hardware_limits_doc09'),'Normalization mismatch.');
assert(strcmp(local_read_attr(fid,'solver'),'ode45'),'Solver mismatch.');
timing.normalization_and_solver_s=toc(clock);

clock=tic;
if nargin>=4 && ~isempty(record)
    assert(double(local_read_attr(fid,'parent_trajectory_id'))==double(record.parent_trajectory_id),'Parent trajectory mismatch.');
    assert(strcmp(char(string(local_read_attr(fid,'fault_class'))),char(string(record.fault_class))),'Fault class mismatch.');
    if ~isempty(strfind(upper(char(string(cfg.active_manifest_path))),'PILOT24'))
        assert(strcmp(local_read_attr(fid,'trajectory_binding_sha256'),'e51122549278d5ae2597605bbeaa75f4f4fff1e244657dad399a2428d85e15ef'),'Binding SHA mismatch.');
        assert(strcmp(local_read_attr(fid,'generator_sha256'),'809483cef2eb13d099938ced21c254dcc33fe01e473415e261057e5a614c46fd'),'Generator SHA mismatch.');
        assert(strcmp(local_read_attr(fid,'constraint_contract_sha256'),'b353095eaaca28d6c2cb241b5f2d4b724e7bbc9d2c8998fde67c57d28c05b65a'),'Contract SHA mismatch.');
        assert(strcmp(local_read_attr(fid,'trajectory_model_sha256'),'534d87131c1d90f8c3b13611e4d3e9087c8e983f22bf51bf41023bcb672fc569'),'Model SHA mismatch.');
        assert(double(local_read_attr(fid,'trajectory_K_segments'))==double(record.K_segments),'K_segments mismatch.');
        assert(strcmp(char(string(local_read_attr(fid,'trajectory_mode'))),char(string(record.trajectory_mode))),'Trajectory mode mismatch.');
    end
end
timing.identity_and_provenance_s=toc(clock);
clock=tic; clear cleanup; timing.file_close_s=toc(clock);
timing.dataset_count=size(checks,1); timing.dataset_read_count=size(checks,1);
timing.telemetry_time_reused=true; timing.validation_invariants_weakened=false;
timing.total_s=toc(total_clock);
timing.instrumented_sum_s=timing.file_open_s+timing.dataset_open_s+timing.dataset_read_s+ ...
    timing.dataset_shape_type_s+timing.dataset_finite_s+timing.root_attribute_presence_and_uid_s+ ...
    timing.reused_timebase_check_s+timing.normalization_and_solver_s+ ...
    timing.identity_and_provenance_s+timing.file_close_s;
timing.unexplained_remainder_s=timing.total_s-timing.instrumented_sum_s;
end

function raw=local_read_attr(fid,name)
aid=H5A.open(fid,name);
try
    raw=H5A.read(aid,'H5ML_DEFAULT');
catch ME
    H5A.close(aid); rethrow(ME)
end
H5A.close(aid);
if iscell(raw), raw=raw{1}; end
if ischar(raw), raw=char(raw); end
end
