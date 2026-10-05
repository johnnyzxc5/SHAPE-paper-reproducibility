function [path,sha,timing] = serialize_run(output_dir,record,ref,telemetry,~,normed,rep,fft_amp,fft_freq,profile,cfg)
%SERIALIZE_RUN Atomic, resumable float32 HDF5 run artifact with qualified P6 fastpath.
% Preserves 100% of scientific datasets, values, datatypes, shapes, chunking,
% all 40 root attribute signatures and values, atomic finalization, and canonical
% validation invariants.
% Integrated from qualified GATE08 P6 serializer with single H5F.create lifecycle,
% unified dataset and attribute writing, preallocated datatypes and dataspaces,
% atomic rename, and streaming Java NIO SHA-256 computation.

total_clock=tic;
uid=char(string(record.run_uid)); path=shape.output_path(output_dir,record); dirpath=fileparts(path);
if ~isfolder(dirpath), mkdir(dirpath); end
tmp=[path '.tmp'];
if isfile(path) && ~cfg.overwrite
    shape.validate_output_gate08_fast_p4(path,uid,cfg,record);
    sha=shape.sha256_file_java_nio(path);
    if nargout > 2
        timing = struct('resumed', true, 'total_s', toc(total_clock));
    end
    return
end
if isfile(tmp), delete(tmp); end

datasets={ ...
 '/temporal/shape',normed.shape; '/temporal/torque',normed.torque; ...
 '/temporal/gmo',normed.gmo; '/temporal/energy',normed.energy; ...
 '/cwt/shape_log',rep.shape_log; '/cwt/torque_log',rep.torque_log; ...
 '/cwt/gmo_log',rep.gmo_log; '/cwt/energy_log',rep.energy_log; ...
 '/cwt/shape_magnitude',rep.shape_magnitude; '/cwt/torque_magnitude',rep.torque_magnitude; ...
 '/cwt/gmo_magnitude',rep.gmo_magnitude; '/cwt/energy_magnitude',rep.energy_magnitude; ...
 '/views/shape_fft_amplitude',fft_amp; '/coordinates/fft_frequency_hz',fft_freq; ...
 '/coordinates/cwt_frequency_hz',rep.freq_hz; '/coordinates/cwt_time_s',rep.time_s; ...
 '/coordinates/telemetry_time_s',single(ref.t); '/quality/coi_valid_mask',uint8(rep.coi_valid_mask); ...
 '/telemetry/q_meas',single(telemetry.q); '/telemetry/dq_meas',single(telemetry.dq); ...
 '/telemetry/tau_cmd',single(telemetry.tau_cmd); '/reference/q_ref',single(ref.q); ...
 '/reference/dq_ref',single(ref.dq); '/reference/ddq_ref',single(ref.ddq); ...
 '/reference/tau_nom',single(ref.tau_nom)};

attributes=local_attributes(uid,record,ref,profile,cfg);

% Open file once for both datasets and attributes
fid=H5F.create(tmp,'H5F_ACC_TRUNC','H5P_DEFAULT','H5P_DEFAULT');

clock=tic;
groups={'/temporal','/cwt','/views','/coordinates','/quality','/telemetry','/reference'};
for k=1:numel(groups)
    gid=H5G.create(fid,groups{k},'H5P_DEFAULT','H5P_DEFAULT','H5P_DEFAULT'); H5G.close(gid);
end

tid_single=H5T.copy('H5T_IEEE_F32LE');
tid_uint8=H5T.copy('H5T_STD_U8LE');
for k=1:size(datasets,1)
    name=datasets{k,1}; value=datasets{k,2};
    dims=fliplr(size(value)); chunk=fliplr(local_chunk(size(value)));
    sid=H5S.create_simple(numel(dims),dims,[]);
    if isa(value,'single')
        tid=tid_single; is_cached=true;
    elseif isa(value,'uint8')
        tid=tid_uint8; is_cached=true;
    else
        tid=local_file_type(class(value)); is_cached=false;
    end
    dcpl=H5P.create('H5P_DATASET_CREATE'); H5P.set_chunk(dcpl,chunk);
    did=H5D.create(fid,name,tid,sid,'H5P_DEFAULT',dcpl,'H5P_DEFAULT');
    try
        H5D.write(did,'H5ML_DEFAULT','H5S_ALL','H5S_ALL','H5P_DEFAULT',value);
    catch ME
        H5D.close(did); H5P.close(dcpl); H5S.close(sid);
        if ~is_cached, H5T.close(tid); end
        H5T.close(tid_uint8); H5T.close(tid_single); H5F.close(fid);
        rethrow(ME)
    end
    H5D.close(did); H5P.close(dcpl); H5S.close(sid);
    if ~is_cached, H5T.close(tid); end
end
H5T.close(tid_uint8); H5T.close(tid_single);
timing.dataset_phase_s=toc(clock);

% Attributes phase (directly to open fid, pre-allocating variable-length string and scalar types)
clock=tic;
tid_vlen=H5T.copy('H5T_C_S1'); H5T.set_size(tid_vlen,'H5T_VARIABLE');
H5T.set_cset(tid_vlen,'H5T_CSET_UTF8'); H5T.set_strpad(tid_vlen,'H5T_STR_NULLTERM');
sid_scalar=H5S.create('H5S_SCALAR');
sid_null=H5S.create('H5S_NULL');

tid_i64=H5T.copy('H5T_STD_I64LE');
tid_f64=H5T.copy('H5T_IEEE_F64LE');
tid_u8=H5T.copy('H5T_STD_U8LE');

for k=1:size(attributes,1)
    name=attributes{k,1}; value=attributes{k,2};
    if (ischar(value) && isempty(value)) || (isstring(value) && (isempty(value) || (isscalar(value) && strlength(value) == 0)))
        sid=sid_null; tid=tid_vlen; write_tid=tid_vlen; payload='';
    elseif ischar(value)
        sid=sid_scalar; tid=tid_vlen; write_tid='H5ML_DEFAULT'; payload={value};
    elseif isstring(value) && isscalar(value)
        sid=sid_scalar; tid=tid_vlen; write_tid='H5ML_DEFAULT'; payload={char(value)};
    elseif isa(value,'int64')
        sid=sid_scalar; tid=tid_i64; write_tid='H5ML_DEFAULT'; payload=value;
    elseif isa(value,'double')
        sid=sid_scalar; tid=tid_f64; write_tid='H5ML_DEFAULT'; payload=value;
    elseif isa(value,'uint8')
        sid=sid_scalar; tid=tid_u8; write_tid='H5ML_DEFAULT'; payload=value;
    else
        sid=sid_scalar; tid=local_file_type(class(value)); write_tid='H5ML_DEFAULT'; payload=value;
    end
    aid=H5A.create(fid,name,tid,sid,'H5P_DEFAULT');
    try
        H5A.write(aid,write_tid,payload);
    catch ME
        H5A.close(aid); H5T.close(tid_vlen); H5T.close(tid_i64); H5T.close(tid_f64); H5T.close(tid_u8);
        H5S.close(sid_scalar); H5S.close(sid_null); H5F.close(fid);
        rethrow(ME)
    end
    H5A.close(aid);
end
H5T.close(tid_vlen); H5T.close(tid_i64); H5T.close(tid_f64); H5T.close(tid_u8);
H5S.close(sid_scalar); H5S.close(sid_null);

% Single final file close
H5F.close(fid);
timing.attribute_fast_path_s=toc(clock);
timing.attribute_count=size(attributes,1);

clock=tic; movefile(tmp,path,'f'); timing.atomic_rename_s=toc(clock);
clock=tic; validation=shape.validate_output_gate08_fast_p4(path,uid,cfg,record); timing.validation_fast_path_s=toc(clock);
timing.validation=validation;
clock=tic; sha=shape.sha256_file_java_nio(path); timing.sha256_s=toc(clock);
timing.total_s=toc(total_clock);
timing.instrumented_sum_s=timing.dataset_phase_s+timing.attribute_fast_path_s+ ...
    timing.atomic_rename_s+timing.validation_fast_path_s+timing.sha256_s;
timing.unexplained_remainder_s=timing.total_s-timing.instrumented_sum_s;
end

function attributes=local_attributes(uid,record,ref,profile,cfg)
persistent matlab_ver
if isempty(matlab_ver), matlab_ver=['MATLAB ' version]; end
attributes={ ...
 'run_uid',uid; 'parent_trajectory_id',int64(record.parent_trajectory_id); ...
 'fault_class',char(string(record.fault_class)); 'schema_version',char(cfg.schema_version); ...
 'normalization','fixed_hardware_limits_doc09'; 'rng_provenance',jsonencode(local_record_seeds(record)); ...
 'manifest_record_json',jsonencode(table2struct(record)); 'software_provenance',matlab_ver; ...
 'code_state_id',char(string(cfg.code_state_id)); ...
 'input_manifest_sha256',char(string(cfg.active_manifest_sha256)); ...
 'input_manifest_path',char(string(cfg.active_manifest_path))};
if isfield(ref,'trajectory_sha256')
    attributes=[attributes; { ...
     'trajectory_sha256',char(string(ref.trajectory_sha256)); ...
     'trajectory_binding_sha256',char(string(ref.trajectory_binding_sha256)); ...
     'generator_sha256',char(string(ref.generator_sha256)); ...
     'constraint_contract_sha256',char(string(ref.constraint_contract_sha256)); ...
     'trajectory_model_sha256',char(string(ref.model_sha256)); ...
     'trajectory_K_segments',int64(ref.K_segments); ...
     'trajectory_mode',char(string(ref.trajectory_mode))}];
end
attributes=[attributes; { ...
 'solver','ode45'; 'solver_rel_tol',double(cfg.solver_rel_tol); ...
 'solver_abs_tol',double(cfg.solver_abs_tol); 'solver_max_step',local_max_step(cfg); ...
 'telemetry_dt_s',double(cfg.telemetry_dt_s)}];
if isfield(profile,'observer_ctdq')
    p=profile.observer_ctdq;
    if p.fallback_used, fallback_status=local_optional(p,'status'); else, fallback_status='NO_FALLBACK'; end
    if isfield(p,'selftest'), selftest_status=local_optional(p.selftest,'status'); else, selftest_status='NOT_APPLICABLE_GOLD'; end
    attributes=[attributes; { ...
     'observer_ctdq_backend',char(string(p.actual_backend)); ...
     'observer_ctdq_backend_version',char(string(p.backend_version)); ...
     'observer_ctdq_requested_backend_version',local_optional(p,'requested_backend_version'); ...
     'observer_ctdq_actual_backend_version',local_optional(p,'actual_backend_version'); ...
     'observer_ctdq_source_version',char(string(p.backend_version)); ...
     'observer_ctdq_status',char(string(p.status)); ...
     'observer_ctdq_fallback_used',uint8(logical(p.fallback_used)); ...
     'observer_ctdq_fallback_status',fallback_status; ...
     'observer_ctdq_fallback_reason',local_optional(p,'fallback_reason'); ...
     'observer_ctdq_selftest_status',selftest_status; ...
     'observer_ctdq_mex_sha256',char(string(p.mex_sha256)); ...
     'observer_ctdq_source_sha256',char(string(p.source_sha256))}];
end
attributes=[attributes; { ...
 'profile_json',jsonencode(profile); 'qc_state','PRE_PILOT_GENERATED'; ...
 'e4_calibration_state',char(string(cfg.e4_calibration.state)); ...
 'e4_calibration_source',char(string(cfg.e4_calibration.source)); ...
 'e4_pooled_velocity_rms_json',jsonencode(cfg.e4_calibration.pooled_velocity_rms)}];
end

function chunk=local_chunk(sz)
chunk=sz; chunk(end)=min(chunk(end),64);
end

function tid=local_file_type(class_name)
switch class_name
    case 'single', tid=H5T.copy('H5T_IEEE_F32LE');
    case 'double', tid=H5T.copy('H5T_IEEE_F64LE');
    case 'uint8', tid=H5T.copy('H5T_STD_U8LE');
    case 'int8', tid=H5T.copy('H5T_STD_I8LE');
    case 'uint16', tid=H5T.copy('H5T_STD_U16LE');
    case 'int16', tid=H5T.copy('H5T_STD_I16LE');
    case 'uint32', tid=H5T.copy('H5T_STD_U32LE');
    case 'int32', tid=H5T.copy('H5T_STD_I32LE');
    case 'uint64', tid=H5T.copy('H5T_STD_U64LE');
    case 'int64', tid=H5T.copy('H5T_STD_I64LE');
    otherwise, error('shape:serialize_run:UnsupportedDatatype','Unsupported class %s.',class_name);
end
end

function value=local_optional(s,name)
if isfield(s,name), value=char(string(s.(name))); else, value=''; end
end

function value=local_max_step(cfg)
if isempty(cfg.solver_max_step_s), value='auto'; else, value=num2str(cfg.solver_max_step_s,17); end
end

function s=local_record_seeds(r)
s=struct('trajectory_seed',double(r.trajectory_seed),'parameter_seed',double(r.parameter_seed), ...
 'fault_seed',double(r.fault_seed),'noise_seed',double(r.noise_seed));
end
