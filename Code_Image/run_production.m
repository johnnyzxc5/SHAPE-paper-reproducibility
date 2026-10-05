function receipt=run_production(varargin)
%RUN_PRODUCTION Safely preflight, execute, or resume one complete-parent shard.
% Production execution requires Mode="PRODUCTION", an exact arming token,
% and a host-bound HOST_QUALIFICATION_PASS receipt.
p=inputParser;
p.addParameter('Mode',"PREFLIGHT",@(x)ischar(x)||isstring(x));
p.addParameter('Cohort',"",@(x)ischar(x)||isstring(x));
p.addParameter('ParentRange',[],@(x)isnumeric(x)&&(isempty(x)||numel(x)==2));
p.addParameter('ParentIDs',[],@isnumeric);
p.addParameter('Workers',[],@(x)isnumeric(x)&&isscalar(x));
p.addParameter('OutputRoot',"",@(x)ischar(x)||isstring(x));
p.addParameter('ShardID',"",@(x)ischar(x)||isstring(x));
p.addParameter('TrajectoryRegistry',"",@(x)ischar(x)||isstring(x));
p.addParameter('HostQualificationReceipt',"",@(x)ischar(x)||isstring(x));
p.addParameter('Arm',"",@(x)ischar(x)||isstring(x)); p.parse(varargin{:}); o=p.Results;
mode=upper(string(o.Mode)); assert(any(mode==["PREFLIGHT" "PRODUCTION"]),'Mode must be PREFLIGHT or PRODUCTION.');
assert(~isempty(o.Workers) && isfinite(o.Workers) && o.Workers>=1 && o.Workers==floor(o.Workers),'Workers must be a positive integer.');
assert(strlength(string(o.OutputRoot))>0 && strlength(string(o.ShardID))>0,'OutputRoot and ShardID are required.');
assert(~isempty(regexp(char(string(o.ShardID)),'^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$','once')),'ShardID must be 3-64 safe characters.');
assert(xor(isempty(o.ParentRange),isempty(o.ParentIDs)),'Specify exactly one of ParentRange or ParentIDs.');
if isempty(o.ParentIDs), ids=double(o.ParentRange(1):o.ParentRange(2)); else, ids=double(o.ParentIDs(:)'); end

code_dir=fileparts(mfilename('fullpath')); addpath(code_dir); addpath(genpath(fullfile(code_dir,'MATLAB','mr')));
spec=shape.production_spec('TrajectoryRegistry',o.TrajectoryRegistry);
output_root=char(string(o.OutputRoot)); local_assert_output_root(spec,output_root);
shard_root=fullfile(output_root,upper(char(string(o.Cohort))),['shard_' char(string(o.ShardID))]);
dirs={shard_root,fullfile(shard_root,'outputs'),fullfile(shard_root,'receipts'),fullfile(shard_root,'logs')};
for k=1:numel(dirs), if ~isfolder(dirs{k}), mkdir(dirs{k}); end, end
session_id=char(java.util.UUID.randomUUID()); session_start=local_now();
preflight_path=fullfile(shard_root,'preflight_receipt.json'); checkpoint_path=fullfile(shard_root,'checkpoint_receipt.json');
final_path=fullfile(shard_root,'final_receipt.json'); assignment_path=fullfile(shard_root,'assignment.json');
receipt=struct('schema_version','production-shard-session-v1','status','INITIALIZING','mode',char(mode), ...
    'session_id',session_id,'session_started_utc',session_start,'production_authorized',false, ...
    'physical_simulations_executed_by_codex',0,'errors',{{}},'warnings',{{}});
shape.write_json_atomic(preflight_path,receipt);
try
    environment=shape.production_environment(spec,double(o.Workers));
    diagnostic=struct('schema_version','production-shard-preflight-v1','status','HOST_STATIC_COMPATIBILITY_FAIL', ...
        'mode',char(mode),'session_id',session_id,'hostname',environment.hostname, ...
        'environment',environment,'production_armed',false,'production_authorized',false, ...
        'physical_simulations_executed',0,'created_utc',local_now(),'errors',{{}},'warnings',{{}});
    if environment.static_compatibility_pass, diagnostic.status='HOST_STATIC_COMPATIBILITY_PASS'; end
    shape.write_json_atomic(preflight_path,diagnostic); receipt=diagnostic;
    local_print_compatibility(environment);
    if ~environment.static_compatibility_pass
        error('shape:production:HostStaticCompatibilityFail', ...
            'Host static compatibility failed checks: %s',strjoin(environment.failed_check_names,', '));
    end
    host_qualification=struct('accepted',false,'status','NOT_PROVIDED');
    if strlength(string(o.HostQualificationReceipt))>0
        host_qualification=shape.verify_host_concurrency_receipt( ...
            char(string(o.HostQualificationReceipt)),environment,spec,double(o.Workers));
    elseif mode=="PRODUCTION"
        error('shape:production:HostReceiptRequired', ...
            'PRODUCTION requires a host-specific concurrency qualification receipt.');
    end
    [candidate,rows,models,cfg]=shape.production_assignment(spec,o.Cohort,ids,double(o.Workers),string(o.ShardID));
    candidate.owner_hostname=environment.hostname; candidate.created_utc=local_now(); candidate.git=environment.git;
    launcher_path=[mfilename('fullpath') '.m'];
    candidate.launcher_sha256=shape.sha256_file(launcher_path);
    if isfile(assignment_path)
        existing=jsondecode(fileread(assignment_path)); local_assert_same_assignment(existing,candidate);
    else
        shape.write_json_atomic(assignment_path,candidate);
    end
    shard_state=shape.validate_production_shard(shard_root);
    assert(~strcmp(shard_state.status,'SHARD_CONFLICT'),'Existing shard contains conflicting outputs.');
    disk=local_disk_check(shard_root,shard_state.pending_outputs);
    assert(disk.sufficient,'Insufficient free disk space for pending shard outputs.');
    preflight=struct('schema_version','production-shard-preflight-v1','status','PRODUCTION_PREFLIGHT_PASS', ...
        'mode',char(mode),'session_id',session_id,'hostname',environment.hostname,'cohort',candidate.cohort, ...
        'shard_id',candidate.shard_id,'parent_ids',candidate.parent_ids,'expected_parents',candidate.parent_count, ...
        'expected_runs',candidate.expected_run_count,'workers',double(o.Workers),'worker_pool_type','Processes', ...
        'environment',environment,'assignment_path',assignment_path,'shard_root',shard_root, ...
        'trajectory_generation_count',0,'canonical_validator',spec.validator,'resume_state',shard_state, ...
        'disk',disk,'host_concurrency_qualification',host_qualification, ...
        'host_specific_concurrency_ready',logical(host_qualification.accepted), ...
        'concurrency_authority',spec.concurrency_authority, ...
        'production_armed',mode=="PRODUCTION",'production_authorized',false, ...
        'physical_simulations_executed',0, ...
        'created_utc',local_now(),'errors',{{}},'warnings',{{}});
    shape.write_json_atomic(preflight_path,preflight); receipt=preflight;
    fprintf('PRODUCTION PREFLIGHT PASS: %s parents %d..%d (%d parents, %d runs), workers=%d\n', ...
        candidate.cohort,min(candidate.parent_ids),max(candidate.parent_ids),candidate.parent_count,candidate.expected_run_count,o.Workers);
    fprintf('Shard root: %s\n',shard_root);
    if mode=="PREFLIGHT"
        fprintf('No physical simulations executed. Production remains unarmed.\n'); return
    end

    assert(string(o.Arm)=="I_AUTHORIZE_THIS_PRODUCTION_SHARD", ...
        'PRODUCTION requires Arm="I_AUTHORIZE_THIS_PRODUCTION_SHARD".');
    receipt.host_qualification=host_qualification; receipt.status='PRODUCTION_ARMED_EXECUTION_STARTING';
    shape.write_json_atomic(checkpoint_path,receipt);
    before_trajectory_sha=string({candidate.trajectories.file_sha256});
    monitor_script=fullfile(spec.root,'docs','codex_p6_worker_topology','p6_resource_monitor.ps1');
    assert(isfile(monitor_script),'P6 resource monitor is missing.');
    monitor_csv=fullfile(shard_root,'logs',['resource_' session_id '.csv']); stop_file=[monitor_csv '.stop'];
    mon=local_start_monitor(monitor_script,monitor_csv,stop_file); mon_cleanup=onCleanup(@()local_stop_monitor(mon,stop_file));
    runtime_root=fullfile(shard_root,'runtime_sessions',session_id,'filegen');
    shape.initialize_worker_filegen_session(runtime_root,session_id,'PRODUCTION',spec.root);
    cfg.require_worker_filegen=true; cfg.runtime_session_id=session_id;
    cfg.repository_root=spec.root; cfg.operational_log_dir=fullfile(shard_root,'logs','runs',session_id);
    pool_cleanup=onCleanup(@()local_close_pool());
    worker_filegen=local_prepare_pool(double(o.Workers),spec.code_dir,runtime_root,session_id,spec.root);
    receipt.worker_filegen=worker_filegen; shape.write_json_atomic(checkpoint_path,receipt);
    wall=tic; results=local_dispatch(rows,models,fullfile(shard_root,'outputs'),cfg); elapsed=toc(wall);
    local_stop_monitor(mon,stop_file); clear mon_cleanup
    local_close_pool(); clear pool_cleanup
    resources=local_parse_monitor(monitor_csv); if isfile(stop_file), delete(stop_file); end
    validation=shape.validate_production_shard(shard_root,'RequireComplete',true);
    resumed=0; retries=0; quarantines=0;
    for k=1:numel(results)
        resumed=resumed+(isfield(results{k}.profile,'resumed')&&logical(results{k}.profile.resumed));
        retries=retries+double(results{k}.retry_count);
        quarantines=quarantines+strcmp(string(results{k}.recovery.state),"CORRUPT_OUTPUT_QUARANTINED");
    end
    after_trajectory_sha=strings(size(before_trajectory_sha));
    for k=1:numel(candidate.trajectories), after_trajectory_sha(k)=shape.sha256_file(candidate.trajectories(k).path); end
    registry_unchanged=isequal(before_trajectory_sha,after_trajectory_sha);
    post_environment=shape.production_environment(spec,double(o.Workers));
    pass=validation.pass && registry_unchanged && post_environment.protected_authorities.all_match && ...
        validation.fallbacks==0 && validation.temporary_residue_count==0;
    final=struct('schema_version','production-shard-final-v1','status','PRODUCTION_SHARD_FAIL', ...
        'pass',pass,'cohort',candidate.cohort,'shard_id',candidate.shard_id,'parent_ids',candidate.parent_ids, ...
        'expected_parents',candidate.parent_count,'expected_runs',candidate.expected_run_count, ...
        'completed_parents',numel(unique(double(rows.parent_trajectory_id))), ...
        'completed_runs',validation.valid_outputs,'valid_outputs',validation.valid_outputs, ...
        'pending_outputs',validation.pending_outputs,'newly_executed_physical_runs',numel(results)-resumed, ...
        'resumed_skipped_valid_runs',resumed,'retries',retries,'quarantines',quarantines, ...
        'fallbacks',validation.fallbacks,'failures',validation.invalid_outputs,'worker_count',double(o.Workers), ...
        'hostname',environment.hostname,'session_id',session_id,'elapsed_walltime_s',elapsed, ...
        'throughput_new_runs_per_hour',3600*(numel(results)-resumed)/max(elapsed,eps), ...
        'resource_telemetry',resources,'worker_filegen',{worker_filegen}, ...
        'uid_uniqueness',validation.uid_duplicates==0, ...
        'missing_output_count',validation.missing_outputs,'temporary_residue_count',validation.temporary_residue_count, ...
        'trajectory_binding_verified',validation.trajectory_sha_mismatches==0, ...
        'protected_authority_postrun',post_environment.protected_authorities, ...
        'registry_unchanged',registry_unchanged,'registry_check_scope','ASSIGNED_PARENT_ARTIFACTS', ...
        'registry_write_operations',0,'output_inventory',{validation.inventory}, ...
        'readiness_for_consolidation',pass,'production_authorized',false, ...
        'completed_utc',local_now(),'errors',{{}},'warnings',{{}});
    if pass, final.status='PRODUCTION_SHARD_PASS'; end
    shape.write_json_atomic(checkpoint_path,final); shape.write_json_atomic(final_path,final); receipt=final;
    assert(pass,'Production shard post-run validation failed.');
    fprintf('PRODUCTION SHARD PASS: %d valid outputs; receipt: %s\n',validation.valid_outputs,final_path);
catch ME
    receipt.status='PRODUCTION_SHARD_ERROR'; receipt.pass=false; receipt.production_authorized=false; receipt.completed_utc=local_now();
    receipt.errors={struct('identifier',ME.identifier,'message',ME.message,'report',getReport(ME,'extended','hyperlinks','off'))};
    if isfile(assignment_path)
        try
            partial=shape.validate_production_shard(shard_root);
            receipt.partial_shard_state=partial;
            receipt.valid_outputs=partial.valid_outputs;
            receipt.pending_outputs=partial.pending_outputs;
        catch validation_error
            receipt.partial_validation_error=struct('identifier',validation_error.identifier,'message',validation_error.message);
        end
    end
    shape.write_json_atomic(checkpoint_path,receipt); rethrow(ME)
end
end

function local_assert_same_assignment(a,b)
assert(strcmpi(a.cohort,b.cohort) && strcmp(a.shard_id,b.shard_id),'Existing shard assignment identity differs.');
assert(isequal(double(a.parent_ids(:)'),double(b.parent_ids(:)')),'Existing shard parent assignment differs.');
assert(strcmpi(a.manifest_sha256,b.manifest_sha256) && strcmpi(a.binding_sha256,b.binding_sha256),'Existing shard authority differs.');
assert(string(a.owner_hostname)==string(b.owner_hostname),'Shard belongs to a different host.');
end

function results=local_dispatch(T,models,output_dir,cfg)
parents=unique(T.parent_trajectory_id,'stable'); groups=cell(numel(parents),1); tables=cell(numel(parents),1); pr=cell(numel(parents),1);
for k=1:numel(parents), groups{k}=find(T.parent_trajectory_id==parents(k)); tables{k}=T(groups{k},:); end
parfor k=1:numel(parents), pr{k}=shape.run_parent(tables{k},models,output_dir,cfg); end
results=cell(height(T),1); for k=1:numel(parents), results(groups{k})=pr{k}; end
end

function info=local_prepare_pool(n,code_dir,runtime_root,session_id,repository_root)
pool=gcp('nocreate'); if isempty(pool)||pool.NumWorkers~=n, if ~isempty(pool), delete(pool); end, pool=parpool('Processes',n); end
assert(pool.NumWorkers==n,'Requested process pool size was not established.');
q=strrep(code_dir,'''',''''''); mr=strrep(fullfile(code_dir,'MATLAB','mr'),'''','''''');
cmd=sprintf('addpath(''%s''); addpath(genpath(''%s''));',q,mr); pctRunOnAll(cmd);
spmd
    per_lab=shape.configure_worker_filegen(runtime_root,session_id,repository_root,spmdIndex,spmdSize);
    c=shape.config(); m=shape.load_models(code_dir);
    s=shape.ctdq_mex_selftest(m,c); assert(s.pass && strcmp(s.status,'SELFTEST_PASS'));
end
info=repmat(per_lab{1},n,1);
for k=1:n, info(k)=per_lab{k}; end
assert(isequal([info.worker_index],1:n),'Worker file-generation indexes are incomplete.');
assert(numel(unique(string({info.cache_folder})))==n,'Worker CacheFolder collision.');
assert(numel(unique(string({info.codegen_folder})))==n,'Worker CodeGenFolder collision.');
assert(all([info.cache_readback_match])&&all([info.codegen_readback_match]), ...
    'Worker file-generation read-back failed.');
assert(~any([info.repository_root_slprj_used]),'Repository-root slprj is active on a worker.');
end

function disk=local_disk_check(path,pending)
f=javaObject('java.io.File',path); free=double(f.getUsableSpace()); estimated=double(pending)*25e6;
disk=struct('free_bytes',free,'pending_run_count',pending,'estimated_required_bytes',estimated, ...
    'estimate_bytes_per_run',25e6,'sufficient',free>=max(estimated*1.10,1e9));
end

function local_assert_output_root(spec,path)
path=char(javaObject('java.io.File',path).getCanonicalPath()); n=lower(strrep(path,'\','/'));
for forbidden={spec.root,fullfile(spec.root,'pilot24_outputs'),fullfile(spec.root,'postpilot_outputs'), ...
        fullfile(spec.root,'outputs_integrated_production_regression'),spec.trajectory_registry,fullfile(spec.root,'docs')}
    f=lower(strrep(char(javaObject('java.io.File',forbidden{1}).getCanonicalPath()),'\','/'));
    assert(~strcmp(n,f) && ~startsWith(n,[f '/']),'Production OutputRoot overlaps a protected/repository evidence location.');
end
end

function proc=local_start_monitor(script,csv,stop)
if isfile(stop), delete(stop); end; if isfile(csv), delete(csv); end
args=sprintf('-ExecutionPolicy Bypass -WindowStyle Hidden -File "%s" -CsvPath "%s" -StopFilePath "%s" -IntervalSec 2 -ParentPid %d',script,csv,stop,matlabProcessID);
proc=System.Diagnostics.Process.Start('powershell.exe',args); assert(~isempty(proc),'Resource monitor failed to start.');
end
function local_stop_monitor(proc,stop)
if ~isfile(stop), fid=fopen(stop,'w'); if fid>=0, fprintf(fid,'STOP\n'); fclose(fid); end, end
if ~isempty(proc)
    try
        if ~proc.WaitForExit(10000), proc.Kill(); end
    catch
    end
end
end
function s=local_parse_monitor(csv)
assert(isfile(csv)); T=readtable(csv,detectImportOptions(csv)); assert(height(T)>0);
s=struct('sample_count',height(T),'system_ram_pct_peak',max(T.system_ram_pct), ...
    'system_free_ram_min_mb',min(T.system_free_ram_mb),'pagefile_used_peak_mb',max(T.pagefile_used_mb), ...
    'matlab_total_rss_peak_mb',max(T.matlab_total_rss_mb),'system_cpu_mean_pct',mean(T.system_cpu_pct));
end
function local_close_pool()
pool=gcp('nocreate'); if ~isempty(pool), delete(pool); end
end
function local_print_compatibility(environment)
fprintf('HOST STATIC COMPATIBILITY CHECKS\n');
checks=environment.compatibility_checks;
for k=1:numel(checks)
    if checks(k).pass, verdict='PASS'; else, verdict='FAIL'; end
    fprintf('  [%s] %s | expected: %s | observed: %s\n',verdict,checks(k).name,checks(k).expected,checks(k).observed);
end
toolboxes=environment.toolbox_checks;
for k=1:numel(toolboxes)
    if toolboxes(k).pass, verdict='PASS'; else, verdict='FAIL'; end
    fprintf('  [%s] toolbox %s | %s | %s\n',verdict,toolboxes(k).name,toolboxes(k).detection_method,toolboxes(k).observed);
end
fprintf('HOST STATIC COMPATIBILITY: %s\n',local_pass_fail(environment.static_compatibility_pass));
end
function value=local_pass_fail(pass)
if pass, value='PASS'; else, value='FAIL'; end
end
function v=local_now()
v=char(datetime('now','TimeZone','UTC','Format','yyyy-MM-dd''T''HH:mm:ss.SSSXXX'));
end
