function receipt=run_production_host_qualification(varargin)
%RUN_PRODUCTION_HOST_QUALIFICATION Static or physical host qualification.
% STATIC executes zero simulations and never authorizes production.
% PHYSICAL reuses the established four-run C1/C2 runtime qualification.
p=inputParser; p.addParameter('Mode',"STATIC",@(x)ischar(x)||isstring(x));
p.addParameter('QualificationRoot',"",@(x)ischar(x)||isstring(x));
p.addParameter('TrajectoryRegistry',"",@(x)ischar(x)||isstring(x));
p.addParameter('Workers',[],@(x)isnumeric(x)&&(isempty(x)||isscalar(x)));
p.addParameter('EvidenceReceipt',"",@(x)ischar(x)||isstring(x));
p.addParameter('BaseHostQualificationReceipt',"",@(x)ischar(x)||isstring(x));
p.addParameter('Arm',"",@(x)ischar(x)||isstring(x)); p.parse(varargin{:}); o=p.Results;
mode=upper(string(o.Mode)); assert(any(mode==["STATIC" "PHYSICAL" "ADOPT_FINAL_REGRESSION" "CONCURRENCY_Q2"]),'Invalid host qualification mode.');
assert(strlength(string(o.QualificationRoot))>0,'QualificationRoot is required.');
code_dir=fileparts(mfilename('fullpath')); addpath(code_dir); addpath(genpath(fullfile(code_dir,'MATLAB','mr')));
spec=shape.production_spec('TrajectoryRegistry',o.TrajectoryRegistry); root=char(string(o.QualificationRoot));
if ~isfolder(root), mkdir(root); end
workers=1; if ~isempty(o.Workers), workers=double(o.Workers); end
assert(isfinite(workers)&&workers>=1&&workers==floor(workers),'Workers must be a positive integer.');
if mode=="CONCURRENCY_Q2", receipt_path=fullfile(root,sprintf('HOST_CONCURRENCY_QUALIFICATION_W%d.json',workers));
else, receipt_path=fullfile(root,'HOST_QUALIFICATION_RECEIPT.json'); end
env=shape.production_environment(spec,workers);
receipt=struct('schema_version','production-host-qualification-v1','status','HOST_STATIC_CHECK_RUNNING', ...
    'pass',false,'production_qualified',false,'production_authorized',false,'mode',char(mode), ...
    'hostname',env.hostname,'matlab_version',env.matlab_version,'architecture',env.architecture, ...
    'environment',env,'binding_sha256',spec.binding_sha,'trajectory_generation_count',0, ...
    'physical_simulations_executed',0,'errors',{{}},'warnings',{{}},'created_utc',local_now());
shape.write_json_atomic(receipt_path,receipt);
try
    assert(env.static_compatibility_pass,'Static environment compatibility failed.');
    trajectory_audit=local_audit_all_trajectories(spec);
    assert(trajectory_audit.pass,'Frozen production trajectory audit failed.');
    receipt.trajectory_audit=trajectory_audit;
    if mode=="STATIC"
        receipt.status='HOST_STATIC_COMPATIBILITY_PASS'; receipt.static_pass=true;
        receipt.warnings={'Static compatibility does not qualify this host for production. Run PHYSICAL or explicitly adopt this host''s existing final-regression evidence.'};
    elseif mode=="CONCURRENCY_Q2"
        assert(string(o.Arm)=="I_ADOPT_INTEGRATED_Q2_HOST_CONCURRENCY", ...
            'Exact integrated Q2 adoption arming token required.');
        evidence_path=char(string(o.EvidenceReceipt));
        q2=local_verify_q2_concurrency_evidence(evidence_path,spec,env,workers);
        receipt=local_concurrency_receipt(receipt,q2,evidence_path,spec,env,workers);
        receipt.base_host_qualification=local_verify_base_host_if_required( ...
            char(string(o.BaseHostQualificationReceipt)),env);
    elseif mode=="ADOPT_FINAL_REGRESSION"
        assert(string(o.Arm)=="I_ATTEST_THIS_HOST_RAN_FINAL_REGRESSION",'Exact adoption arming token required.');
        evidence=local_verify_final_regression(spec,env); receipt.existing_final_regression=evidence.final_regression;
        receipt.existing_p6=evidence.p6;
        assert(evidence.pass,'Existing final integrated regression evidence is unavailable or invalid.');
        receipt.status='HISTORICAL_HOST_EVIDENCE_PASS'; receipt.pass=true; receipt.production_qualified=false;
        receipt.host_binding=struct('current_hostname',env.hostname,'historical_hostname_available',false, ...
            'hardware_fingerprint_match',evidence.p6.hardware_fingerprint_match, ...
            'binding_method','EXPLICIT_OPERATOR_ATTESTATION_PLUS_P6_HARDWARE_AND_72_RUN_ENVIRONMENT_PROVENANCE');
        receipt.qualification_basis='EXISTING_LOCAL_P6_W8_AND_72_RUN_FINAL_REGRESSION_PLUS_OPERATOR_HOST_ATTESTATION';
        receipt.warnings={'Historical evidence does not authorize any active production worker count. Run host-specific concurrency Q2.'};
    else
        assert(string(o.Arm)=="I_AUTHORIZE_HOST_QUALIFICATION_SIMULATIONS",'Exact physical qualification arming token required.');
        local_require_physical_evidence(spec);
        runtime_dir=fullfile(spec.root,'docs','codex_postgate_runtime'); addpath(runtime_dir);
        runtime_receipt=run_runtime_qualification();
        receipt.runtime_qualification=runtime_receipt;
        receipt.physical_simulations_executed=double(runtime_receipt.physical_simulations_executed);
        assert(strcmp(runtime_receipt.status,'QUALIFICATION_PASS') && runtime_receipt.physical_simulations_executed==4, ...
            'Established C1/C2 runtime qualification did not pass exactly four simulations.');
        receipt.status='HOST_SCIENTIFIC_QUALIFICATION_PASS'; receipt.pass=true; receipt.production_qualified=false;
        receipt.qualification_basis='FRESH_C1_C2_NORMAL_ACCELERATOR_LEVEL1A_LEVEL1B_LEVEL2';
        receipt.warnings={'Four-run scientific host qualification does not authorize production concurrency. Run host-specific concurrency Q2.'};
    end
    receipt.completed_utc=local_now(); shape.write_json_atomic(receipt_path,receipt);
    fprintf('%s\nReceipt: %s\n',receipt.status,receipt_path);
catch ME
    receipt.status='HOST_QUALIFICATION_FAIL'; receipt.pass=false; receipt.production_qualified=false;
    receipt.errors={struct('identifier',ME.identifier,'message',ME.message)}; receipt.completed_utc=local_now();
    shape.write_json_atomic(receipt_path,receipt); rethrow(ME)
end

function report=local_verify_base_host_if_required(path,env)
report=struct('required',logical(env.fresh_physical_host_qualification_required), ...
    'status','NOT_REQUIRED_HISTORICAL_ENVIRONMENT');
if ~report.required, return, end
assert(~isempty(path)&&isfile(path), ...
    'Candidate environment requires a fresh four-run base host qualification receipt.');
q=jsondecode(fileread(path));
assert(strcmp(q.status,'HOST_SCIENTIFIC_QUALIFICATION_PASS') && logical(q.pass) && ...
    double(q.physical_simulations_executed)==4, ...
    'Fresh base host qualification receipt did not pass four physical simulations.');
assert(isfield(q,'environment') && isfield(q.environment,'host_identity') && ...
    strcmpi(q.environment.host_identity.fingerprint_sha256,env.host_identity.fingerprint_sha256) && ...
    strcmp(q.matlab_version,env.matlab_version) && strcmp(q.architecture,env.architecture), ...
    'Fresh base host qualification belongs to a different host/runtime.');
report=struct('required',true,'status','FRESH_BASE_HOST_QUALIFICATION_PASS', ...
    'path',path,'sha256',shape.sha256_file(path));
end

function receipt=local_concurrency_receipt(base,q2,evidence_path,spec,env,workers)
receipt=base;
receipt.schema_version='production-host-concurrency-qualification-v2';
receipt.status='HOST_CONCURRENCY_QUALIFICATION_PASS'; receipt.pass=true;
receipt.production_qualified=true; receipt.production_authorized=false;
receipt.concurrency_authority='HOST_SPECIFIC_QUALIFIED_CONCURRENCY';
receipt.qualified_workers=workers; receipt.exact_concurrency_only=true;
receipt.worker_profile='Processes'; receipt.host_identity=env.host_identity;
receipt.matlab_release=env.release; receipt.compiler_name=env.compiler_name;
receipt.compiler_version=env.compiler_version;
receipt.scientific_release_authority=spec.scientific_release_authority;
receipt.protected_authorities_all_match=logical(env.protected_authorities.all_match);
receipt.protected_authorities=env.protected_authorities;
receipt.observer_mex_selftest_pass=logical(env.observer_mex_selftest.pass);
receipt.observer_mex_sha256=env.observer_mex_selftest.mex_sha256;
receipt.observer_source_sha256=env.observer_mex_selftest.source_sha256;
receipt.toolbox_license_readiness=struct('all_required_toolboxes_present',env.all_required_toolboxes_present, ...
    'parallel_license_available',env.parallel_license_available, ...
    'process_worker_capacity',env.process_cluster_capacity);
receipt.cache_isolation_pass=true; receipt.physical_qualification_pass=true;
receipt.filegen_readback_pass=true; receipt.repository_root_slprj_used=false;
receipt.physical_population=struct('authority','PILOT24_P6_NON_E2B_24X4', ...
    'parent_ids',9001:9024,'siblings_per_parent',4,'run_count',96);
receipt.physical_runs_attempted=double(q2.physical_runs_attempted);
receipt.physical_runs_completed=double(q2.physical_runs_completed);
receipt.scientific_validator_passes=double(q2.scientific_validator_passes);
receipt.eof_warning_count=double(q2.eof_warning_count);
receipt.retries=double(q2.retries); receipt.quarantines=double(q2.quarantines);
receipt.failures=double(q2.failures);
receipt.evidence_receipt_path=evidence_path;
receipt.evidence_receipt_sha256=shape.sha256_file(evidence_path);
receipt.qualification_basis='INTEGRATED_WORKER_FILEGEN_Q1_PLUS_96_RUN_Q2';
end

function q2=local_verify_q2_concurrency_evidence(path,spec,env,workers)
assert(~isempty(path)&&isfile(path),'Integrated Q2 evidence receipt is required.');
q2=jsondecode(fileread(path));
assert(strcmp(q2.status,'Q2_COMPLETED_NONPRODUCTION') && double(q2.workers)==workers, ...
    'Q2 evidence status/concurrency mismatch.');
assert(double(q2.physical_runs_attempted)==96 && double(q2.physical_runs_completed)==96 && ...
    double(q2.scientific_validator_passes)==96 && double(q2.eof_warning_count)==0 && ...
    double(q2.retries)==0 && double(q2.quarantines)==0 && double(q2.failures)==0, ...
    'Q2 physical acceptance criteria failed.');
assert(~logical(q2.repository_root_slprj_used) && logical(q2.fast_restart), ...
    'Q2 file-generation/FastRestart evidence failed.');
assert(numel(q2.worker_filegen_paths)==workers,'Q2 worker evidence count mismatch.');
cache=string({q2.worker_filegen_paths.cache_folder}); codegen=string({q2.worker_filegen_paths.codegen_folder});
assert(numel(unique(cache))==workers && numel(unique(codegen))==workers && ...
    all([q2.worker_filegen_paths.cache_readback_match]) && ...
    all([q2.worker_filegen_paths.codegen_readback_match]), ...
    'Q2 worker file-generation isolation evidence failed.');
assert(all(strcmpi(string({q2.worker_filegen_paths.hostname}),string(env.hostname))), ...
    'Q2 evidence was produced on a different host.');
helper=fullfile(spec.code_dir,'+shape','configure_worker_filegen.m');
assert(isfile(helper) && isfield(q2,'shared_filegen_helper_sha256') && ...
    strcmpi(q2.shared_filegen_helper_sha256,shape.sha256_file(helper)), ...
    'Q2 did not qualify the current shared production file-generation helper.');
assert(isfield(q2,'protected_authorities') && q2.protected_authorities.all_match && ...
    env.protected_authorities.all_match,'Q2/current protected authority evidence failed.');
end
end

function audit=local_audit_all_trajectories(spec)
assert(isfile(spec.binding) && strcmpi(shape.sha256_file(spec.binding),spec.binding_sha));
[p,~]=shape.validate_manifest(spec.primary_manifest); [e,~]=shape.validate_manifest(spec.e2b_manifest); T=[p;e];
binding=parquetread(spec.binding); assert(height(binding)==5030 && numel(unique(binding.parent_id))==5030);
models=shape.load_models(spec.code_dir); cfg=shape.config('trajectory_registry_dir',spec.trajectory_registry, ...
    'trajectory_binding_path',spec.binding);
parents=unique(T.parent_trajectory_id); failures=0;
for k=1:numel(parents)
    id=parents(k); row=T(find(T.parent_trajectory_id==id,1),:);
    try
        ref=shape.load_frozen_trajectory(row,spec.trajectory_registry,cfg,models);
        b=binding(binding.parent_id==id,:); failures=failures+(height(b)~=1 || ~strcmpi(ref.trajectory_sha256,char(string(b.trajectory_sha256))));
    catch
        failures=failures+1;
    end
end
audit=struct('pass',failures==0,'parents_checked',numel(parents),'failures',failures, ...
    'registry',spec.trajectory_registry,'binding_sha256',spec.binding_sha);
end

function evidence=local_verify_final_regression(spec,env)
path=fullfile(spec.root,'docs','codex_final_integrated_production_regression','FINAL_INTEGRATED_PRODUCTION_REGRESSION_RECEIPT.json');
assert(isfile(path),'Final integrated regression receipt is missing.'); r=jsondecode(fileread(path));
expected_receipt_sha='cd136a4ba3a5398cf95dbfa2aff204322991d1bc568ca899b3193f3f4f58c7ae';
receipt_sha=shape.sha256_file(path);
pass=strcmpi(receipt_sha,expected_receipt_sha) && ...
    strcmp(r.status,'FINAL_INTEGRATED_PRODUCTION_REGRESSION_PASS') && logical(r.final_pass) && ...
    double(r.total_physical_runs)==72 && double(r.canonical_validation_pass_count)==72 && ...
    double(r.fallbacks)==0 && double(r.second_pass_physical_runs)==0 && double(r.second_pass_sha_changes)==0;
files=r.phase1.files; available=0; sha_match=0; environment_match=0; mex_match=0;
for k=1:numel(files)
    p=fullfile(spec.root,strrep(files(k).path,'/',filesep));
    if isfile(p)
        available=available+1; sha_match=sha_match+strcmpi(shape.sha256_file(p),files(k).sha256);
        software=string(h5readatt(p,'/','software_provenance'));
        profile=jsondecode(h5readatt(p,'/','profile_json'));
        recorded=profile.observer_ctdq.selftest.environment;
        environment_match=environment_match+(software=="MATLAB "+string(env.matlab_version) && ...
            string(recorded.matlab_version)==string(env.matlab_version) && string(recorded.arch)==string(env.architecture));
        mex_match=mex_match+(strcmpi(h5readatt(p,'/','observer_ctdq_mex_sha256'),env.observer_mex_selftest.mex_sha256) && ...
            strcmpi(h5readatt(p,'/','observer_ctdq_source_sha256'),env.observer_mex_selftest.source_sha256) && ...
            strcmp(h5readatt(p,'/','observer_ctdq_status'),'MEX_ACTIVE') && ...
            ~logical(h5readatt(p,'/','observer_ctdq_fallback_used')));
    end
end
pass=pass && available==72 && sha_match==72 && environment_match==72 && mex_match==72;
final=struct('pass',pass,'receipt_path',path,'receipt_sha256',receipt_sha, ...
    'expected_receipt_sha256',expected_receipt_sha,'physical_runs',double(r.total_physical_runs), ...
    'available_outputs',available,'sha_matches',sha_match,'environment_matches',environment_match, ...
    'mex_provenance_matches',mex_match,'operator_attestation_required',true);
p6=local_verify_p6(spec,env);
evidence=struct('pass',pass && p6.pass,'final_regression',final,'p6',p6);
end

function evidence=local_verify_p6(spec,env)
path=fullfile(spec.root,'docs','codex_p6_worker_topology','P6_FINAL_STORAGE_RECHECK_RECEIPT.json');
expected_sha='5c7e29539b47f81506a006e0929c103b2b969f5325f20e6dc7a9e1de96351cdb';
assert(isfile(path),'Ratified P6 final-storage receipt is missing.'); sha=shape.sha256_file(path); r=jsondecode(fileread(path));
cpu_token=regexp(string(r.host.cpu),'[A-Za-z]\d+-\d+[A-Za-z]*','match','once');
cpu_match=strlength(cpu_token)>0 && contains(lower(string(env.cpu_model)),lower(cpu_token));
os_match=contains(lower(string(env.os)),'windows 11') && contains(lower(string(r.host.os)),'windows 11');
decision=r.decision; science=r.science_gate;
pass=strcmpi(sha,expected_sha) && science.passed && science.all_25_datasets_raw_identical && ...
    science.signed_zero_parity_pass && science.static_attribute_parity_pass && ...
    strcmp(decision.fastest_valid_final_storage_topology,'W8') && ...
    double(decision.final_production_worker_count)==8 && decision.worker_count_freeze_ready && ...
    strcmp(decision.gate08_status,'RATIFIED/CLOSED') && ~decision.physical_rerun_after_this_required && ...
    cpu_match && os_match;
evidence=struct('pass',pass,'receipt_path',path,'receipt_sha256',sha,'expected_receipt_sha256',expected_sha, ...
    'topology','W8','workers',8,'science_gate_pass',logical(science.passed), ...
    'recorded_cpu',r.host.cpu,'current_cpu',env.cpu_model,'cpu_match',cpu_match, ...
    'recorded_os',r.host.os,'current_os',env.os,'os_match',os_match, ...
    'hardware_fingerprint_match',cpu_match && os_match,'historical_hostname_available',false);
end

function local_require_physical_evidence(spec)
paths={fullfile(spec.root,'pilot24_outputs','PILOT24_CANONICAL_V2','parent_9001_9100','run_8167b058-dc6e-3b0a-b6b0-0478265cd56a.h5'), ...
 fullfile(spec.root,'pilot24_outputs','PILOT24_CANONICAL_V2','parent_9001_9100','run_216a0075-20d7-34a6-aded-c2198b018f7d.h5'), ...
 fullfile(spec.root,'data','trajectory_registry','pilot24','v2','parent_9002_trajectory.mat'), ...
 fullfile(spec.root,'data','trajectory_registry','pilot24','v2','parent_9015_trajectory.mat')};
for k=1:numel(paths), assert(isfile(paths{k}),'Required host-qualification evidence missing: %s',paths{k}); end
end
function v=local_now()
v=char(datetime('now','TimeZone','UTC','Format','yyyy-MM-dd''T''HH:mm:ss.SSSXXX'));
end
