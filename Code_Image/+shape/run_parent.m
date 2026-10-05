function out = run_parent(rows,models,output_dir,cfg)
%RUN_PARENT Execute siblings together to preserve affinity and hot caches.
assert(numel(unique(rows.parent_trajectory_id))==1 && numel(unique(rows.trajectory_seed))==1 && ...
    numel(unique(rows.K_segments))==1 && numel(unique(string(rows.trajectory_mode)))==1, ...
    'shape:trajectory:SiblingMismatch','Sibling rows must bind to one identical frozen parent reference.');
ref=shape.load_frozen_trajectory(rows(1,:),cfg.trajectory_registry_dir,cfg,models);
if isfield(cfg,'require_worker_filegen') && cfg.require_worker_filegen
    shape.require_worker_filegen(char(string(cfg.runtime_session_id)),char(string(cfg.repository_root)));
end
x=tic; model='Kinova_Fault_Simulator'; load_system(model); model_load_s=toc(x);
x=tic;
set_param(model,'Solver','ode45','RelTol',num2str(cfg.solver_rel_tol,17), ...
    'AbsTol',num2str(cfg.solver_abs_tol,17),'MaxStep',local_max_step(cfg), ...
    'StopTime',num2str(cfg.duration_s,17)); model_parameter_setup_s=toc(x);
x=tic; if cfg.fast_restart, set_param(model,'FastRestart','on'); end; fast_restart_setup_s=toc(x);
cleanup=onCleanup(@() local_finish(model,cfg.fast_restart));
out=cell(height(rows),1);
for j=1:height(rows)
    out{j}=local_run_record_observed(rows(j,:),ref,models,output_dir,cfg);
    if isfield(cfg,'performance_instrumentation') && cfg.performance_instrumentation
        out{j}.profile.model_load_s=model_load_s;
        out{j}.profile.model_parameter_setup_s=model_parameter_setup_s;
        out{j}.profile.fast_restart_setup_s=fast_restart_setup_s;
    end
end
end

function result=local_run_record_observed(record,ref,models,output_dir,cfg)
if ~isfield(cfg,'operational_log_dir') || strlength(string(cfg.operational_log_dir))==0
    result=shape.run_record(record,ref,models,output_dir,cfg); return
end
log_dir=char(string(cfg.operational_log_dir)); if ~isfolder(log_dir), mkdir(log_dir); end
uid=char(string(record.run_uid)); console_path=fullfile(log_dir,['run_' uid '_console.log']);
event_path=fullfile(log_dir,['run_' uid '_runtime.json']);
worker=shape.require_worker_filegen(char(string(cfg.runtime_session_id)),char(string(cfg.repository_root)));
event=local_event(record,cfg,worker); event.started_utc=local_now();
lastwarn(''); diary(console_path); diary_cleanup=onCleanup(@()diary('off'));
try
    result=shape.run_record(record,ref,models,output_dir,cfg);
    [warning_message,warning_identifier]=lastwarn;
    diary('off'); clear diary_cleanup
    event.completed_utc=local_now(); event.status='SUCCESS';
    event.attempt_count=double(result.retry_count)+1;
    event.warning_identifier=warning_identifier; event.warning_message=warning_message;
    resumed=isfield(result.profile,'resumed') && logical(result.profile.resumed);
    event.simulation_returned=~resumed;
    event.resumed_valid_output=resumed;
    event.serialization_completed=isfile(char(result.path));
    event.canonical_validation_pass=event.serialization_completed;
    event.output_path=char(result.path); event.output_sha256=char(result.sha256);
    shape.write_json_atomic(event_path,event);
catch ME
    [warning_message,warning_identifier]=lastwarn;
    diary('off'); clear diary_cleanup
    event.completed_utc=local_now(); event.status='EXCEPTION';
    event.attempt_count=double(cfg.max_retries)+1;
    event.warning_identifier=warning_identifier; event.warning_message=warning_message;
    event.error_identifier=ME.identifier; event.error_message=ME.message;
    shape.write_json_atomic(event_path,event); rethrow(ME)
end
end

function event=local_event(record,cfg,worker)
event=struct('schema_version','production-run-runtime-event-v1', ...
    'runtime_session_id',char(string(cfg.runtime_session_id)), ...
    'host',worker.hostname,'process_pid',worker.process_id, ...
    'worker_index',worker.worker_index,'worker_identity',worker.worker_identity, ...
    'parent_id',double(record.parent_trajectory_id),'run_uid',char(string(record.run_uid)), ...
    'fault_class',local_field(record,'fault_class'),'trajectory_mode',local_field(record,'trajectory_mode'), ...
    'cache_folder',worker.cache_folder,'codegen_folder',worker.codegen_folder, ...
    'started_utc','','completed_utc','','status','STARTING','attempt_count',0, ...
    'warning_identifier','','warning_message','','error_identifier','','error_message','', ...
    'simulation_returned',false,'resumed_valid_output',false, ...
    'serialization_completed',false,'canonical_validation_pass',false, ...
    'output_path','','output_sha256','');
end
function value=local_field(record,name)
if ismember(name,record.Properties.VariableNames), value=char(string(record.(name)(1))); else, value=''; end
end
function value=local_now()
value=char(datetime('now','TimeZone','UTC','Format','yyyy-MM-dd''T''HH:mm:ss.SSSXXX'));
end
function value=local_max_step(cfg)
if isempty(cfg.solver_max_step_s), value='auto';
else, value=num2str(cfg.solver_max_step_s,17); end
end
function local_finish(model,fast)
if fast
    try set_param(model,'FastRestart','off'); catch, end
end
try close_system(model,0); catch, end
end
