function receipt = ctdq_mex_selftest(models,cfg)
%CTDQ_MEX_SELFTEST Lightweight deterministic load, identity and fixture test.
persistent cached_key cached_receipt
code_dir=fileparts(fileparts(mfilename('fullpath')));
source=fullfile(code_dir,'ctdq_finite_difference_batch_mex_source.m');
artifact=fullfile(cfg.observer_ctdq_mex_dir,['ctdq_finite_difference_batch_mex.' mexext]);
expected_version='p1b-fd-central-h1e-6-v1';
key=strjoin(string({artifact,cfg.observer_ctdq_backend_version, ...
    cfg.observer_ctdq_mex_expected_sha256,cfg.observer_ctdq_source_expected_sha256, ...
    cfg.observer_ctdq_qualified_arch,cfg.observer_ctdq_qualified_matlab, ...
    cfg.observer_ctdq_qualified_coder_major_minor,cfg.observer_ctdq_qualified_compiler, ...
    cfg.observer_ctdq_qualified_compiler_version, ...
    num2str(cfg.observer_ctdq_selftest_tolerance_Nm,17),num2str(cfg.observer_ctdq_mex_enabled)}),'|');
if ~isempty(cached_key) && cached_key==key
    receipt=cached_receipt; return
end
receipt=struct('pass',false,'status','SELFTEST_FAILED','fallback_status', ...
    'MEX_SELFTEST_FAILED_GOLD_FALLBACK','reason','','backend_version', ...
    cfg.observer_ctdq_backend_version,'expected_version',expected_version, ...
    'source_path',source,'source_sha256','','mex_path',artifact,'mex_sha256','', ...
    'max_abs_error_Nm',NaN,'output_shape_ok',false,'finite_output',false, ...
    'environment',local_environment(),'environment_qualified',false, ...
    'environment_profile','','requires_fresh_physical_host_qualification',true, ...
    'environment_policy',struct());
if ~cfg.observer_ctdq_mex_enabled || ~isfile(artifact)
    receipt.reason='MEX artifact unavailable or disabled';
    receipt.fallback_status='MEX_UNAVAILABLE_GOLD_FALLBACK'; cache(); return
end
if ~strcmp(cfg.observer_ctdq_backend_version,expected_version)
    receipt.reason='Backend version mismatch';
    receipt.fallback_status='MEX_VERSION_MISMATCH_GOLD_FALLBACK'; cache(); return
end
policy=shape.observer_ctdq_environment_policy(receipt.environment,cfg);
receipt.environment_policy=policy;
receipt.environment_qualified=policy.supported;
receipt.environment_profile=policy.profile;
receipt.requires_fresh_physical_host_qualification=policy.requires_fresh_physical_host_qualification;
if ~receipt.environment_qualified
    receipt.reason='Runtime is outside the P1B-qualified environment';
    receipt.fallback_status='MEX_ENVIRONMENT_UNQUALIFIED_GOLD_FALLBACK'; cache(); return
end
receipt.source_sha256=shape.sha256_file(source); receipt.mex_sha256=shape.sha256_file(artifact);
if ~isempty(cfg.observer_ctdq_source_expected_sha256) && ...
        ~strcmpi(receipt.source_sha256,cfg.observer_ctdq_source_expected_sha256)
    receipt.reason='Source hash mismatch'; receipt.fallback_status='MEX_HASH_MISMATCH_GOLD_FALLBACK'; cache(); return
end

if ~isempty(cfg.observer_ctdq_mex_expected_sha256) && ...
        ~strcmpi(receipt.mex_sha256,cfg.observer_ctdq_mex_expected_sha256)
    receipt.reason='MEX hash mismatch'; receipt.fallback_status='MEX_HASH_MISMATCH_GOLD_FALLBACK'; cache(); return
end
addpath(cfg.observer_ctdq_mex_dir,'-begin');
resolved=which('ctdq_finite_difference_batch_mex');
if isempty(resolved) || ~strcmpi(resolved,artifact)
    receipt.reason='MEX did not resolve to configured artifact';
    receipt.fallback_status='MEX_UNAVAILABLE_GOLD_FALLBACK'; cache(); return
end
q=[.1 -.25;.2 .15;-.3 .05;.12 -.08;-.09 .22;.04 -.11];
dq=[.2 -.1;-.15 .12;.08 -.2;.04 .09;-.11 .03;.17 -.07];
try
    z=ctdq_finite_difference_batch_mex(q,dq,models.Mlist_nom,models.Glist_nom,models.Slist_nom);
catch ME
    receipt.reason=['MEX load/call failure: ' ME.identifier];
    receipt.fallback_status='MEX_UNAVAILABLE_GOLD_FALLBACK'; cache(); return
end
gold=zeros(size(q));
for k=1:size(q,2), gold(:,k)=shape.coriolis_transpose_velocity(q(:,k),dq(:,k),models); end
receipt.max_abs_error_Nm=max(abs(z-gold),[],'all');
receipt.output_shape_ok=isequal(size(z),size(q)); receipt.finite_output=all(isfinite(z(:)));
receipt.pass=receipt.output_shape_ok && receipt.finite_output && ...
    receipt.max_abs_error_Nm<=cfg.observer_ctdq_selftest_tolerance_Nm;
if receipt.pass
    receipt.status='SELFTEST_PASS'; receipt.fallback_status=''; receipt.reason='';
else
    receipt.reason='Fixture numerical/shape/finite check failed';
end
cache();
    function cache()
        cached_key=key; cached_receipt=receipt;
    end
end

function env=local_environment()
env=struct('arch',computer('arch'),'matlab_version',version, ...
    'coder_version','','compiler_name','','compiler_version','');
products=ver; names=string({products.Name});
v=products(names=="MATLAB Coder");
if ~isempty(v), env.coder_version=v(1).Version; end
try
    cc=mex.getCompilerConfigurations('C++','Selected');
    if ~isempty(cc)
        env.compiler_name=cc(1).Name;
        env.compiler_version=cc(1).Version;
    end
catch
end
end
