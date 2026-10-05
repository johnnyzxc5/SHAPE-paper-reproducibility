function receipt = run_eof_worker_cache_isolation_qualification(varargin)
%RUN_EOF_WORKER_CACHE_ISOLATION_QUALIFICATION Non-production EOF qualification.
% Never calls run_production; refuses repository and production output roots.
p=inputParser;
p.addParameter('Stage','Q1',@(x)ischar(x)||isstring(x));
p.addParameter('Workers',[],@(x)isnumeric(x)&&(isempty(x)||(isscalar(x)&&isfinite(x)&&x>=2&&x==floor(x))));
p.addParameter('QualificationRoot','',@(x)ischar(x)||isstring(x));
p.addParameter('ProtectedProductionRoot','',@(x)ischar(x)||isstring(x));
p.addParameter('QualificationID','eof_cache_isolation_qualification',@(x)ischar(x)||isstring(x));
p.addParameter('CleanupQualificationOwnedFilegen',false,@(x)islogical(x)&&isscalar(x));
p.addParameter('Arm','',@(x)ischar(x)||isstring(x));
p.parse(varargin{:}); o=p.Results;
stage=upper(string(o.Stage));
assert(any(stage==["Q1" "Q2_PREDISPATCH" "Q2" "ALL"]), ...
    'Stage must be Q1, Q2_PREDISPATCH, Q2, or ALL.');
root_dir=fileparts(fileparts(fileparts(mfilename('fullpath'))));
code_dir=fullfile(root_dir,'Code_Image'); script_dir=fileparts(mfilename('fullpath'));
assert(~isempty(o.Workers),'Workers is required and must be chosen for this host.');
assert(strlength(string(o.QualificationRoot))>0,'QualificationRoot is required.');
assert(strlength(string(o.ProtectedProductionRoot))>0, ...
    'ProtectedProductionRoot is required and must identify the production output root.');
qualification_root=local_canonical(char(string(o.QualificationRoot)));
protected_production_root=local_canonical(char(string(o.ProtectedProductionRoot)));
qualification_id=char(string(o.QualificationID));
assert(~isempty(regexp(qualification_id,'^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$','once')), ...
    'QualificationID must be 3-64 safe characters.');
session_root=local_canonical(fullfile(qualification_root,qualification_id));
local_assert_nonproduction_root(session_root,root_dir,protected_production_root);
if ~isfolder(session_root), mkdir(session_root); end
local_write_owner_marker(session_root,root_dir,qualification_id);
addpath(code_dir); addpath(genpath(fullfile(code_dir,'MATLAB','mr'))); addpath(script_dir);
shape.initialize_worker_filegen_session(fullfile(session_root,'filegen'), ...
    qualification_id,'NONPRODUCTION_Q2',root_dir);

pool=gcp('nocreate'); assert(isempty(pool),'Qualification requires no pre-existing pool.');
pool=parpool('Processes',double(o.Workers)); pool_cleanup=onCleanup(@()local_close_pool(pool));
pctRunOnAll(sprintf('addpath(''%s''); addpath(genpath(''%s'')); addpath(''%s'');', ...
    local_quote(code_dir),local_quote(fullfile(code_dir,'MATLAB','mr')),local_quote(script_dir)));

% Q1 is complete before any model load or physical simulation.
worker_info=local_configure_workers(session_root,root_dir,qualification_id,double(o.Workers));
q1=local_verify_q1(worker_info,session_root,root_dir,double(o.Workers));
q1.created_utc=local_now(); q1.physical_simulations_executed=0;
if stage=="Q1" || stage=="ALL"
    local_write_json(fullfile(session_root,'q1_worker_filegen_receipt.json'),q1);
end

receipt=struct('schema_version','eof-worker-cache-isolation-qualification-v1', ...
    'qualification_id',qualification_id,'stage',char(stage),'workers',double(o.Workers), ...
    'qualification_root',qualification_root,'session_root',session_root, ...
    'production_authorized',false,'production_worker_count_authority','UNRESOLVED', ...
    'q1',q1,'q2_predispatch',struct('status','NOT_REQUESTED'), ...
    'q2',struct('status','NOT_REQUESTED'),'created_utc',local_now());
if stage=="Q2_PREDISPATCH" || stage=="Q2" || stage=="ALL"
    predispatch_path=fullfile(session_root,'q2_predispatch_inventory_receipt.json');
    try
        [predispatch,T,parent_rows,models,cfg,output_root]=local_prepare_q2_inventory( ...
            root_dir,code_dir,session_root,worker_info,double(o.Workers),qualification_id, ...
            protected_production_root);
        receipt.q2_predispatch=predispatch;
        local_write_json(predispatch_path,predispatch);
    catch ME
        failed=struct('schema_version','eof-q2-predispatch-inventory-v1', ...
            'qualification_id',qualification_id,'status','Q2_PREDISPATCH_FAIL', ...
            'ready',false,'workers',double(o.Workers),'physical_simulations_executed',0, ...
            'error_identifier',ME.identifier,'error_message',ME.message,'created_utc',local_now());
        receipt.q2_predispatch=failed; local_write_json(predispatch_path,failed); rethrow(ME)
    end
end
if stage=="Q2" || stage=="ALL"
    assert(string(o.Arm)=="I_AUTHORIZE_NONPRODUCTION_Q2_PHYSICAL_QUALIFICATION", ...
        'Q2 physical execution requires the exact non-production arming token.');
    receipt.q2=local_run_q2(T,parent_rows,models,cfg,output_root,session_root, ...
        worker_info,double(o.Workers),predispatch);
end
receipt.completed_utc=local_now();
if stage~="Q2_PREDISPATCH"
    local_write_json(fullfile(session_root,'qualification_receipt.json'),receipt);
end
if o.CleanupQualificationOwnedFilegen, local_cleanup_owned_filegen(session_root,qualification_id); end
clear pool_cleanup
local_close_pool(pool)
end

function worker_info=local_configure_workers(session_root,root_dir,qualification_id,workers)
spmd
    per_lab=local_configure_one_worker(session_root,root_dir,qualification_id,spmdIndex,spmdSize);
end
schema=local_worker_info_schema();
worker_info=repmat(schema,workers,1);
for k=1:workers
    worker_info(k)=local_require_worker_info(per_lab{k},schema,k,workers);
end
end

function info=local_worker_info_schema()
% Ordered, complete schema: aggregation must never hide worker differences.
info=struct('worker_index',0,'worker_count',0,'worker_identity','', ...
    'hostname','','process_id',0,'process_id_available',false, ...
    'assigned_cache_folder','','cache_folder','','cache_readback_match',false, ...
    'assigned_codegen_folder','','codegen_folder','','codegen_readback_match',false, ...
    'configured_utc','');
end

function info=local_require_worker_info(raw,schema,expected_index,expected_count)
assert(isstruct(raw) && isscalar(raw),'Q1 worker record must be a scalar struct.');
assert(isequal(fieldnames(raw),fieldnames(schema)), ...
    'Q1 worker record schema differs from the required canonical schema.');
assert(raw.worker_index==expected_index && raw.worker_count==expected_count, ...
    'Q1 worker index/count is inconsistent with Process-pool assignment.');
assert(strcmp(raw.worker_identity,sprintf('spmd-lab-%03d',expected_index)), ...
    'Q1 worker identity is inconsistent with Process-pool assignment.');
assert(~isempty(raw.hostname),'Q1 worker hostname is required.');
assert(raw.cache_readback_match && raw.codegen_readback_match, ...
    'Q1 worker FileGen read-back does not match its assigned paths.');
assert(strcmpi(raw.assigned_cache_folder,raw.cache_folder), ...
    'Q1 worker CacheFolder assignment/read-back differs.');
assert(strcmpi(raw.assigned_codegen_folder,raw.codegen_folder), ...
    'Q1 worker CodeGenFolder assignment/read-back differs.');
info=raw;
end

function info=local_configure_one_worker(session_root,root_dir,qualification_id,worker_index,worker_count)
shared=shape.configure_worker_filegen(fullfile(session_root,'filegen'), ...
    qualification_id,root_dir,worker_index,worker_count);
[process_id,process_id_available]=local_process_id();
info=local_worker_info_schema();
info.worker_index=double(worker_index); info.worker_count=double(worker_count);
info.worker_identity=sprintf('spmd-lab-%03d',worker_index);
info.hostname=shared.hostname;
info.process_id=process_id; info.process_id_available=process_id_available;
info.assigned_cache_folder=shared.cache_folder; info.cache_folder=shared.cache_folder;
info.cache_readback_match=shared.cache_readback_match;
info.assigned_codegen_folder=shared.codegen_folder; info.codegen_folder=shared.codegen_folder;
info.codegen_readback_match=shared.codegen_readback_match;
info.configured_utc=shared.configured_utc;
assert(info.cache_readback_match,'Worker CacheFolder did not persist.');
assert(info.codegen_readback_match,'Worker CodeGenFolder did not persist.');
setappdata(0,'eof_worker_cache_isolation_info',info);
end

function [process_id,available]=local_process_id()
process_id=0; available=false;
try
    process_id=double(feature('getpid'));
    available=isfinite(process_id) && process_id>0;
catch
    % Stable SPMD lab identity remains mandatory if this MATLAB lacks a PID API.
end
end

function q1=local_verify_q1(info,session_root,root_dir,workers)
assert(numel(info)==workers,'Q1 did not execute once on every worker.');
assert(isequal([info.worker_index],1:workers),'Q1 worker indexes are not one-to-one.');
identity=string({info.worker_identity});
assert(numel(unique(identity))==workers,'Q1 worker identities are not unique.');
assert(all([info.cache_readback_match]),'Q1 CacheFolder read-back mismatch.');
assert(all([info.codegen_readback_match]),'Q1 CodeGenFolder read-back mismatch.');
cache=string({info.cache_folder}); codegen=string({info.codegen_folder});
assigned_cache=string({info.assigned_cache_folder});
assigned_codegen=string({info.assigned_codegen_folder});
assert(numel(unique(cache))==workers,'CacheFolder collision.');
assert(numel(unique(codegen))==workers,'CodeGenFolder collision.');
assert(all(strcmpi(cache,assigned_cache)),'CacheFolder assignment/read-back mismatch.');
assert(all(strcmpi(codegen,assigned_codegen)),'CodeGenFolder assignment/read-back mismatch.');
pid_available=[info.process_id_available]; process_ids=[info.process_id];
if any(pid_available)
    assert(all(pid_available),'Q1 PID availability differs between Process workers.');
    assert(numel(unique(process_ids))==workers,'Q1 Process workers do not have unique PIDs.');
end
for k=1:workers
    local_assert_descendant(char(cache(k)),session_root);
    local_assert_descendant(char(codegen(k)),session_root);
    local_assert_not_descendant(char(cache(k)),root_dir);
    local_assert_not_descendant(char(codegen(k)),root_dir);
end
q1=struct('status','Q1_PASS_NO_PHYSICAL_SIMULATION','worker_count',workers, ...
    'workers',{info},'worker_identities_unique',true, ...
    'process_ids_unique_if_available',~any(pid_available)||numel(unique(process_ids))==workers, ...
    'unique_cache_folders',true,'unique_codegen_folders',true, ...
    'cachefolder_readback_match',true,'codegenfolder_readback_match',true, ...
    'repository_root_slprj_used',false,'physical_simulations_executed',0);
end

function [inventory,T,parent_rows,models,cfg,output_root]=local_prepare_q2_inventory( ...
        root_dir,code_dir,session_root,worker_info,workers,qualification_id,protected_production_root)
% Reproduce the executable historical P6 population exactly, without sim().
manifest_path=fullfile(root_dir,'docs','codex_active','manifests','PILOT24_MANIFEST_CANDIDATE.parquet');
assert(isfile(manifest_path),'Frozen P6 manifest is missing.');
[manifest_full,manifest_report]=shape.validate_manifest(manifest_path);
assert(strcmpi(char(manifest_report.sha256), ...
    '3055262237f62b934e8337dc867ea28ad9e50f178fdddc0be767429eaa57907e'), ...
    'Frozen P6 manifest SHA-256 mismatch.');
% This is the exact population rule in both historical P6 executable runners.
is_normal=~contains(string(manifest_full.analysis_stratum),'E2B');
T=manifest_full(is_normal,:);
parents=unique(double(T.parent_trajectory_id),'stable');
assert(isequal(parents(:)',9001:9024),'Q2 requires P6 parents 9001..9024 only.');
assert(height(T)==96,'Q2 requires 24 parents x 4 siblings.');
assert(numel(unique(string(T.run_uid)))==96,'Q2 contains duplicate run UIDs.');
assert(sum(~is_normal)==20,'Frozen P6 manifest no longer contains the expected 20 excluded E2-B rows.');

binding_path=fullfile(root_dir,'docs','codex_active','manifests', ...
    'PILOT24_TRAJECTORY_BINDING_CANDIDATE_V2.parquet');
assert(isfile(binding_path) && strcmpi(shape.sha256_file(binding_path), ...
    'e51122549278d5ae2597605bbeaa75f4f4fff1e244657dad399a2428d85e15ef'), ...
    'Frozen Pilot V2 trajectory binding is missing or changed.');
models=shape.load_models(code_dir);
cfg=shape.config('run_pilot',true,'overwrite',false,'max_retries',1, ...
    'fast_restart',true,'mpc_shared_rnea_enabled',true,'mpc_mass_backend',1, ...
    'observer_ctdq_backend','finite_difference_batch_mex', ...
    'observer_ctdq_mex_enabled',true,'observer_ctdq_selftest_enabled',true, ...
    'performance_instrumentation',true, ...
    'code_state_id','NONPRODUCTION_EOF_WORKER_CACHE_ISOLATION_Q2');
cfg.active_manifest_path=manifest_path; cfg.active_manifest_sha256=char(manifest_report.sha256);
cfg.require_worker_filegen=true; cfg.runtime_session_id=qualification_id;
cfg.repository_root=root_dir; cfg.operational_log_dir=fullfile(session_root,'logs');
assert(strcmpi(shape.sha256_file(cfg.trajectory_binding_path), ...
    'e51122549278d5ae2597605bbeaa75f4f4fff1e244657dad399a2428d85e15ef'), ...
    'Q2 runtime trajectory binding differs from the frozen P6 binding.');

output_root=local_canonical(fullfile(session_root,'outputs'));
local_assert_descendant(output_root,session_root); local_assert_not_descendant(output_root,root_dir);
local_assert_not_descendant(output_root,protected_production_root);
parent_rows=cell(numel(parents),1);
rows_per_parent=zeros(numel(parents),1);
artifacts=repmat(struct('parent_id',0,'trajectory_path','','trajectory_sha256','', ...
    'qualification_path','','qualification_sha256','','bound_trajectory_sha256',''),numel(parents),1);
for k=1:numel(parents)
    rows=T(T.parent_trajectory_id==parents(k),:);
    rows_per_parent(k)=height(rows);
    assert(height(rows)==4 && numel(unique(string(rows.run_uid)))==4,'P6 sibling set invalid.');
    assert(isequal(sort(string(rows.fault_class)),["Friction";"LoE";"Nominal";"Vibration"]), ...
        'P6 sibling fault identities differ from historical authority.');
    parent_rows{k}=rows;
    trajectory_path=fullfile(cfg.trajectory_registry_dir,sprintf('parent_%04d_trajectory.mat',parents(k)));
    qualification_path=fullfile(cfg.trajectory_registry_dir,sprintf('parent_%04d_qualification.json',parents(k)));
    assert(isfile(trajectory_path) && isfile(qualification_path), ...
        'Required frozen P6 input artifact is missing for parent %d.',parents(k));
    ref=shape.load_frozen_trajectory(rows(1,:),cfg.trajectory_registry_dir,cfg,models);
    artifacts(k)=struct('parent_id',parents(k),'trajectory_path',trajectory_path, ...
        'trajectory_sha256',shape.sha256_file(trajectory_path), ...
        'qualification_path',qualification_path, ...
        'qualification_sha256',shape.sha256_file(qualification_path), ...
        'bound_trajectory_sha256',char(string(ref.trajectory_sha256)));
end

run_identity=repmat(struct('parent_id',0,'run_uid','','fault_class','', ...
    'analysis_stratum','','trajectory_mode','','K_segments',0,'trajectory_seed',0, ...
    'parameter_seed',0,'fault_seed',0,'noise_seed',0,'planned_output_path',''),height(T),1);
planned_paths=strings(height(T),1);
for k=1:height(T)
    planned_paths(k)=string(shape.output_path(output_root,T(k,:)));
    local_assert_descendant(char(planned_paths(k)),session_root);
    local_assert_not_descendant(char(planned_paths(k)),protected_production_root);
    run_identity(k)=struct('parent_id',double(T.parent_trajectory_id(k)), ...
        'run_uid',char(string(T.run_uid(k))),'fault_class',char(string(T.fault_class(k))), ...
        'analysis_stratum',char(string(T.analysis_stratum(k))), ...
        'trajectory_mode',char(string(T.trajectory_mode(k))),'K_segments',double(T.K_segments(k)), ...
        'trajectory_seed',double(T.trajectory_seed(k)),'parameter_seed',double(T.parameter_seed(k)), ...
        'fault_seed',double(T.fault_seed(k)),'noise_seed',double(T.noise_seed(k)), ...
        'planned_output_path',char(planned_paths(k)));
end
assert(numel(unique(planned_paths))==height(T),'Q2 planned output paths are not unique.');
q1=local_verify_q1(worker_info,session_root,root_dir,workers);
historical_runner=fullfile(root_dir,'docs','codex_p6_worker_topology','run_p6_worker_topology.m');
historical_recheck=fullfile(root_dir,'docs','codex_p6_worker_topology','run_p6_final_storage_recheck.m');
historical_receipt=fullfile(root_dir,'docs','codex_p6_worker_topology','P6_WORKER_TOPOLOGY_RECEIPT.json');
assert(isfile(historical_runner)&&isfile(historical_recheck)&&isfile(historical_receipt), ...
    'Historical P6 executable/receipt authority is incomplete.');
inventory=struct('schema_version','eof-q2-predispatch-inventory-v1', ...
    'qualification_id',qualification_id,'status','Q2_PREDISPATCH_PASS','ready',true, ...
    'created_utc',local_now(),'source_manifest',manifest_path, ...
    'source_manifest_sha256',char(manifest_report.sha256), ...
    'historical_population_rule','~contains(string(manifest_full.analysis_stratum),''E2B'')', ...
    'historical_runner',historical_runner,'historical_runner_sha256',shape.sha256_file(historical_runner), ...
    'historical_recheck',historical_recheck,'historical_recheck_sha256',shape.sha256_file(historical_recheck), ...
    'historical_receipt',historical_receipt,'historical_receipt_sha256',shape.sha256_file(historical_receipt), ...
    'trajectory_binding_path',binding_path,'trajectory_binding_sha256',shape.sha256_file(binding_path), ...
    'total_rows',height(T),'unique_parent_count',numel(parents),'parent_ids',parents(:)', ...
    'rows_per_parent',rows_per_parent(:)','run_identities',{run_identity}, ...
    'duplicate_run_identity_count',height(T)-numel(unique(string(T.run_uid))), ...
    'duplicate_output_path_count',height(T)-numel(unique(planned_paths)), ...
    'required_input_artifacts',{artifacts},'missing_required_input_count',0, ...
    'planned_output_root',output_root,'outputs_qualification_owned_only',true, ...
    'production_root_excluded',true,'workers',workers,'worker_isolation',q1, ...
    'worker_filegen_isolation_valid',true,'repository_root_slprj_used',false, ...
    'total_planned_physical_runs',height(T),'physical_simulations_executed',0, ...
    'production_authorized',false,'production_worker_count_authority','UNRESOLVED');
end

function q2=local_run_q2(T,parent_rows,models,cfg,output_root,session_root,worker_info,workers,predispatch)
% Physical dispatch begins only at the parfor/shape.run_parent boundary below.
assert(predispatch.ready && predispatch.total_rows==96, ...
    'Q2 pre-dispatch inventory is not ready.');
if ~isfolder(output_root), mkdir(output_root); end
parents=unique(double(T.parent_trajectory_id),'stable');
observations=cell(numel(parents),1);
parfor k=1:numel(parent_rows)
    observations{k}=local_observe_parent(parent_rows{k},models,output_root,cfg);
end

completed=0; retries=0; quarantines=0; failures=0; eof_count=0; validator_passes=0;
for k=1:numel(observations)
    ob=observations{k}; eof_count=eof_count+double(ob.eof_warning_count);
    if ~strcmp(ob.status,'SUCCESS'), failures=failures+height(parent_rows{k}); continue, end
    for j=1:numel(ob.runs)
        r=ob.runs{j}; completed=completed+1; retries=retries+double(r.retry_count);
        quarantines=quarantines+strcmp(string(r.recovery.state),'CORRUPT_OUTPUT_QUARANTINED');
        try
            shape.validate_output_gate08_fast_p4(char(r.path),char(r.run_uid),cfg,parent_rows{k}(j,:));
            validator_passes=validator_passes+1;
        catch
            failures=failures+1;
        end
    end
end
root_dir=fileparts(fileparts(fileparts(mfilename('fullpath'))));
spec=shape.production_spec(); env=shape.production_environment(spec,workers);
helper=fullfile(spec.code_dir,'+shape','configure_worker_filegen.m');
pass=completed==96 && validator_passes==96 && eof_count==0 && retries==0 && ...
    quarantines==0 && failures==0 && env.protected_authorities.all_match;
q2=struct('status','Q2_COMPLETED_NONPRODUCTION','workers',workers,'parents',parents, ...
    'pass',pass,'hostname',env.hostname,'host_identity',env.host_identity, ...
    'physical_runs_attempted',height(T),'physical_runs_completed',completed, ...
    'scientific_validator_passes',validator_passes,'eof_warning_count',eof_count, ...
    'retries',retries,'quarantines',quarantines,'failures',failures, ...
    'repository_root_slprj_used',false,'fast_restart',true, ...
    'shared_filegen_helper',helper,'shared_filegen_helper_sha256',shape.sha256_file(helper), ...
    'protected_authorities',env.protected_authorities, ...
    'worker_filegen_paths',{worker_info},'per_worker_latency',{local_per_worker_latency(observations,workers)}, ...
    'parent_observations',{observations}, ...
    'output_root',output_root,'manifest_path',predispatch.source_manifest,'completed_utc',local_now(), ...
    'production_authorized',false,'production_worker_count_authority','UNRESOLVED');
local_write_json(fullfile(session_root,'q2_controlled_physical_receipt.json'),q2);
assert(pass,'Integrated Q2 host-concurrency qualification acceptance failed.');
end

function summary=local_per_worker_latency(observations,workers)
summary=repmat(struct('worker_index',0,'parent_count',0,'parent_latency_s',[], ...
    'mean_parent_latency_s',[],'max_parent_latency_s',[]),workers,1);
for worker=1:workers
    values=[];
    for k=1:numel(observations)
        ob=observations{k};
        if ob.worker.worker_index==worker, values(end+1)=ob.latency_s; end %#ok<AGROW>
    end
    summary(worker).worker_index=worker; summary(worker).parent_count=numel(values);
    summary(worker).parent_latency_s=values;
    if ~isempty(values)
        summary(worker).mean_parent_latency_s=mean(values);
        summary(worker).max_parent_latency_s=max(values);
    end
end
end

function observation=local_observe_parent(rows,models,output_root,cfg)
info=getappdata(0,'eof_worker_cache_isolation_info');
assert(~isempty(info),'Worker does not have Q1 filegen configuration.');
shape.require_worker_filegen(char(string(cfg.runtime_session_id)),char(string(cfg.repository_root)));
lastwarn(''); captured_console=''; start_utc=local_now(); clock=tic;
try
    captured_console=evalc('runs=shape.run_parent(rows,models,output_root,cfg);');
    [warning_message,warning_identifier]=lastwarn;
    eof_warning_count=numel(strfind(captured_console, ...
        'Unexpected end-of-file while reading compressed data'));
    observation=struct('status','SUCCESS','worker',info, ...
        'parent_id',double(rows.parent_trajectory_id(1)),'start_utc',start_utc, ...
        'stop_utc',local_now(),'latency_s',toc(clock), ...
        'warning_message',warning_message,'warning_identifier',warning_identifier, ...
        'eof_warning_count',eof_warning_count, ...
        'eof_warning_detected',eof_warning_count>0 || contains(string(warning_message), ...
        'Unexpected end-of-file while reading compressed data'), ...
        'runs',{runs},'exception_identifier','','exception_message','');
catch ME
    [warning_message,warning_identifier]=lastwarn;
    eof_warning_count=numel(strfind(captured_console, ...
        'Unexpected end-of-file while reading compressed data'));
    observation=struct('status','EXCEPTION','worker',info, ...
        'parent_id',double(rows.parent_trajectory_id(1)),'start_utc',start_utc, ...
        'stop_utc',local_now(),'latency_s',toc(clock), ...
        'warning_message',warning_message,'warning_identifier',warning_identifier, ...
        'eof_warning_count',eof_warning_count, ...
        'eof_warning_detected',eof_warning_count>0 || contains(string(warning_message), ...
        'Unexpected end-of-file while reading compressed data'), ...
        'runs',{{}},'exception_identifier',ME.identifier,'exception_message',ME.message);
end
end

function local_write_owner_marker(session_root,root_dir,qualification_id)
marker=fullfile(session_root,'.qualification_owner.json');
if isfile(marker), return, end
owner=struct('schema_version','qualification-owned-directory-v1', ...
    'qualification_id',qualification_id,'session_root',session_root, ...
    'repository_root',root_dir,'production_authorized',false,'created_utc',local_now());
local_write_json(marker,owner);
end
function local_cleanup_owned_filegen(session_root,qualification_id)
marker=fullfile(session_root,'.qualification_owner.json'); filegen=fullfile(session_root,'filegen');
assert(isfile(marker) && isfolder(filegen),'Only qualification-owned filegen may be removed.');
owner=jsondecode(fileread(marker));
assert(strcmp(owner.qualification_id,qualification_id),'Qualification ownership marker mismatch.');
local_assert_descendant(local_canonical(filegen),session_root);
rmdir(filegen,'s');
end
function local_write_json(path,value)
tmp=[path '.tmp']; fid=fopen(tmp,'w'); assert(fid>=0,'Cannot write qualification receipt.');
cleanup=onCleanup(@()fclose(fid)); fprintf(fid,'%s\n',jsonencode(value)); clear cleanup
movefile(tmp,path,'f');
end
function local_assert_nonproduction_root(session_root,root_dir,protected_production_root)
local_assert_not_descendant(session_root,root_dir);
local_assert_not_descendant(session_root,protected_production_root);
end
function local_assert_descendant(path,parent)
path=lower(strrep(local_canonical(path),'\','/')); parent=lower(strrep(local_canonical(parent),'\','/'));
assert(startsWith(path,[parent '/']),'Path is outside its qualification root.');
end
function local_assert_not_descendant(path,parent)
path=lower(strrep(local_canonical(path),'\','/')); parent=lower(strrep(local_canonical(parent),'\','/'));
assert(~strcmp(path,parent) && ~startsWith(path,[parent '/']), ...
    'Qualification path overlaps protected root: %s',parent);
end
function value=local_canonical(path), value=char(java.io.File(path).getCanonicalPath()); end
function value=local_quote(path), value=strrep(path,'''',''''''); end
function local_close_pool(pool), if ~isempty(pool) && isvalid(pool), delete(pool); end, end
function value=local_now(), value=char(datetime('now','TimeZone','UTC','Format','yyyy-MM-dd''T''HH:mm:ss.SSSXXX')); end
