function receipt=run_reproduction(varargin)
%RUN_REPRODUCTION Standalone regeneration with frozen sources, seeds and bindings.
% PLAN reads metadata only. Other stages must be explicitly armed. This new
% serial route does not reuse/issue historical production concurrency receipts.
p=inputParser;
p.addParameter('Stage','PLAN',@(x)ischar(x)||isstring(x));
p.addParameter('WorkRoot','',@(x)ischar(x)||isstring(x));
p.addParameter('Arm','',@(x)ischar(x)||isstring(x)); p.parse(varargin{:}); o=p.Results;
stage=upper(string(o.Stage)); assert(any(stage==["PLAN" "INPUTS" "QUALIFY" "SIMULATE"]));
code=fileparts(mfilename('fullpath')); root=fileparts(code);
addpath(code); addpath(genpath(fullfile(code,'MATLAB','mr')));
spec=shape.production_spec();
pilot_manifest=fullfile(root,'docs','codex_active','manifests','PILOT24_MANIFEST_CANDIDATE.parquet');
pilot_binding=fullfile(root,'docs','codex_active','manifests','PILOT24_TRAJECTORY_BINDING_CANDIDATE_V2.parquet');
assert(strcmpi(shape.sha256_file(pilot_manifest),'3055262237f62b934e8337dc867ea28ad9e50f178fdddc0be767429eaa57907e'));
assert(strcmpi(shape.sha256_file(pilot_binding),'e51122549278d5ae2597605bbeaa75f4f4fff1e244657dad399a2428d85e15ef'));
assert(strcmpi(shape.sha256_file(spec.primary_manifest),spec.primary_sha));
assert(strcmpi(shape.sha256_file(spec.e2b_manifest),spec.e2b_sha));
assert(strcmpi(shape.sha256_file(spec.binding),spec.binding_sha));
[primary,~]=shape.validate_manifest(spec.primary_manifest);
[e2b,~]=shape.validate_manifest(spec.e2b_manifest);
[pilot,~]=shape.validate_manifest(pilot_manifest);
receipt=struct('schema_version','shape-reproduction-stage-v1','stage',char(stage), ...
    'status','PLAN_ONLY','primary_parents',5000,'primary_runs',20000, ...
    'e2b_parents',30,'e2b_runs',300,'pilot_parents',numel(unique(pilot.parent_trajectory_id)), ...
    'physical_simulations_executed',0,'historical_concurrency_authorization',false);
if stage=="PLAN", disp(receipt); return; end
assert(string(o.Arm)=="I_REQUEST_THIS_REPRODUCTION_STAGE",'Explicit reproduction stage request required.');
work=char(java.io.File(char(string(o.WorkRoot))).getCanonicalPath());
assert(~isempty(o.WorkRoot),'Dedicated WorkRoot is required.');
local_outside(work,root);
marker_path=fullfile(work,'.shape-reproduction.json');
assert(isfile(marker_path),'Prepare a new work root with tools/reproduce.py plan --prepare first.');
marker=jsondecode(fileread(marker_path));
assert(strcmpi(marker.repository_root,root)&&strcmpi(marker.work_root,work),'Work root ownership mismatch.');
local_verify_seal(root);
models=shape.load_models(code);
production_registry=local_child(work,'inputs','production');
pilot_registry=local_child(work,'inputs','pilot');
receipts=local_child(work,'receipts'); if ~isfolder(receipts), mkdir(receipts); end
if stage=="INPUTS"
    local_generate([primary;e2b],spec.binding,production_registry,models);
    local_generate(pilot,pilot_binding,pilot_registry,models);
    receipt.status='INPUTS_GENERATED_AND_FROZEN_CONTENT_VERIFIED';
    receipt.production_registry=production_registry; receipt.pilot_registry=pilot_registry;
    shape.write_json_atomic(fullfile(receipts,'inputs.json'),receipt); return;
end

% No model loading/physical calculation occurs until an armed QUALIFY/SIMULATE.
env=shape.production_environment(spec,1);
assert(env.static_compatibility_pass,'Unsupported host/backend; inspect frozen environment policy.');
session_id=['reproduction_' char(java.util.UUID.randomUUID())];
session_root=local_child(work,'runtime',session_id);
shape.initialize_worker_filegen_session(session_root,session_id,'REPRODUCTION_SERIAL',root);
assert(isempty(gcp('nocreate')),'Close existing parallel pool before reproduction.');
pool=parpool('Processes',1); cleanup=onCleanup(@()delete(pool));
qualification_path=fullfile(receipts,'serial_host_qualification.json');
signatures_path=fullfile(root,'metadata','simulation','qualified_pilot_signatures.json');
if stage=="QUALIFY"
    shape.write_json_atomic(qualification_path,struct('status','QUALIFICATION_RUNNING','pass',false));
    signatures=jsondecode(fileread(signatures_path));
    cfg=shape.config('run_pilot',true,'num_workers',1,'max_retries',0, ...
        'mpc_shared_rnea_enabled',true,'mpc_mass_backend',1,'performance_instrumentation',true, ...
        'trajectory_registry_dir',pilot_registry,'trajectory_binding_path',pilot_binding, ...
        'code_state_id','standalone-reproduction-qualification');
    cfg.active_manifest_path=pilot_manifest; cfg.active_manifest_sha256=shape.sha256_file(pilot_manifest);
    checks=cell(numel(signatures.cases),1);
    for k=1:numel(signatures.cases)
        fixture=signatures.cases(k); rows=pilot(string(pilot.run_uid)==string(fixture.run_uid),:);
        assert(height(rows)==1,'Qualification UID absent/duplicated in frozen manifest.');
        shape.load_frozen_trajectory(rows,pilot_registry,cfg,models);
        % Fresh outputs on every qualification: a resumed old run cannot
        % establish numerical agreement of the current host/runtime.
        outputs=local_child(work,'qualification',session_id);
        f=parfeval(pool,@local_worker,1,rows,models,outputs,cfg,session_root,session_id,root);
        result=fetchOutputs(f); path=char(result{1}.path);
        shape.validate_output_gate08_fast_p4(path,char(string(rows.run_uid)),cfg,rows);
        for j=1:numel(fixture.datasets)
            item=fixture.datasets(j); value=h5read(path,item.path);
            assert(strcmpi(shape.sha256_canonical(value),item.sha256), ...
                'Reproduced qualification dataset differs from ratified numerical fingerprint: %s',item.path);
        end
        checks{k}=struct('run_uid',fixture.run_uid,'datasets_verified',numel(fixture.datasets), ...
            'path',path,'sha256',shape.sha256_file(path));
        receipt.physical_simulations_executed=receipt.physical_simulations_executed+ ...
            double(~(isfield(result{1}.profile,'resumed')&&result{1}.profile.resumed));
    end
    receipt.status='REPRODUCTION_SERIAL_HOST_PASS'; receipt.pass=true;
    assert(receipt.physical_simulations_executed==2,'Qualification must execute two fresh physical cases.');
    receipt.host_identity=env.host_identity; receipt.matlab_version=env.matlab_version;
    receipt.compiler_name=env.compiler_name; receipt.compiler_version=env.compiler_version;
    receipt.signatures_sha256=shape.sha256_file(signatures_path);
    receipt.source_seal_sha256=shape.sha256_file(fullfile(root,'provenance','SHA256SUMS.txt'));
    receipt.checks=checks; receipt.workers=1;
    receipt.scope='Fresh two-case numerical fingerprint agreement; one Process worker only; not historical Q2';
    shape.write_json_atomic(qualification_path,receipt); return;
end
assert(isfile(qualification_path),'Run QUALIFY on this host/work root first.');
q=jsondecode(fileread(qualification_path));
assert(strcmp(q.status,'REPRODUCTION_SERIAL_HOST_PASS')&&q.pass&&q.workers==1);
assert(strcmpi(q.host_identity.fingerprint_sha256,env.host_identity.fingerprint_sha256) && ...
    strcmp(q.matlab_version,env.matlab_version)&&strcmp(q.compiler_name,env.compiler_name) && ...
    strcmp(q.compiler_version,env.compiler_version),'Qualification belongs to another host/runtime.');
assert(strcmpi(q.signatures_sha256,shape.sha256_file(signatures_path)) && ...
    strcmpi(q.source_seal_sha256,shape.sha256_file(fullfile(root,'provenance','SHA256SUMS.txt'))), ...
    'Qualification source/fingerprint contract has changed.');
spec=shape.production_spec('TrajectoryRegistry',production_registry);
cohorts=["PRIMARY" "E2B"]; ids={1:5000,5001:5030};
receipt.status='SIMULATION_IN_PROGRESS';
for c=1:numel(cohorts)
    [~,rows,models,cfg]=shape.production_assignment(spec,cohorts(c),ids{c},1,['reproduction_' char(cohorts(c))]);
    output=local_child(work,'outputs',char(cohorts(c)));
    for id=ids{c}
        siblings=rows(rows.parent_trajectory_id==id,:);
        f=parfeval(pool,@local_worker,1,siblings,models,output,cfg,session_root,session_id,root);
        result=fetchOutputs(f);
        for j=1:numel(result)
            shape.validate_output_gate08_fast_p4(char(result{j}.path),char(string(siblings.run_uid(j))),cfg,siblings(j,:));
            receipt.physical_simulations_executed=receipt.physical_simulations_executed+ ...
                double(~(isfield(result{j}.profile,'resumed')&&result{j}.profile.resumed));
        end
        receipt.last_completed_parent=id;
        shape.write_json_atomic(fullfile(receipts,'simulation.json'),receipt);
    end
end
receipt.status='SIMULATION_COMPLETE';
receipt.completed_utc=char(datetime('now','TimeZone','UTC'));
shape.write_json_atomic(fullfile(receipts,'simulation.json'),receipt);
end

function local_generate(rows,binding,registry,models)
[~,indices]=unique(rows.parent_trajectory_id,'stable'); parents=rows(indices,:);
cfg=shape.config('trajectory_registry_dir',registry,'trajectory_binding_path',binding);
if ~isfolder(registry), mkdir(registry); end
for k=1:height(parents)
    row=parents(k,:); path=fullfile(registry,sprintf('parent_%04d_trajectory.mat',row.parent_trajectory_id));
    if ~isfile(path)
        result=shape.qualify_parent(row,models,registry,cfg);
        assert(strcmp(result.qualification_status,'PASS'),'Seed exhausted its 500-attempt budget.');
    end
    % Both existing and freshly generated contents must match the original
    % immutable binding; file timestamps/serialization are not the identity.
    shape.load_frozen_trajectory(row,registry,cfg,models);
end
end

function result=local_worker(rows,models,output,cfg,session_root,session_id,root)
code=fullfile(root,'Code_Image'); addpath(code); addpath(genpath(fullfile(code,'MATLAB','mr')));
shape.configure_worker_filegen(session_root,session_id,root,1,1);
cfg.require_worker_filegen=true; cfg.runtime_session_id=session_id; cfg.repository_root=root;
result=shape.run_parent(rows,models,output,cfg);
for k=1:numel(result)
    assert(strcmp(result{k}.profile.observer_ctdq.actual_backend,'finite_difference_batch_mex') && ...
        ~result{k}.profile.observer_ctdq.fallback_used,'Observer backend fallback is prohibited.');
end
end

function path=local_child(work,varargin)
path=char(java.io.File(fullfile(work,varargin{:})).getCanonicalPath());
assert(startsWith(lower(strrep(path,'\','/')),[lower(strrep(work,'\','/')) '/']), ...
    'Reproduction path escapes its owned work root.');
end
function local_outside(path,root)
a=lower(strrep(path,'\','/')); b=lower(strrep(root,'\','/'));
assert(~strcmp(a,b)&&~startsWith(a,[b '/'])&&~startsWith(b,[a '/']), ...
    'Work root must be separate from the source repository.');
end
function local_verify_seal(root)
lines=splitlines(string(fileread(fullfile(root,'provenance','SHA256SUMS.txt'))));
for k=1:numel(lines)
    if strlength(lines(k))==0, continue; end
    tokens=regexp(char(lines(k)),'^([a-f0-9]{64})  (.+)$','tokens','once');
    assert(~isempty(tokens),'Malformed source seal.');
    path=char(java.io.File(fullfile(root,tokens{2})).getCanonicalPath());
    assert(startsWith(lower(strrep(path,'\','/')),[lower(strrep(root,'\','/')) '/']));
    assert(isfile(path)&&strcmpi(shape.sha256_file(path),tokens{1}),'Source seal mismatch: %s',tokens{2});
end
end
