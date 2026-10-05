function report=production_environment(spec,workers)
%PRODUCTION_ENVIRONMENT Static qualified-host compatibility checks; no Simulink.
if nargin<2, workers=1; end
products=ver; names=string({products.Name});
required=["Simulink" "Stateflow" "Optimization Toolbox" "Wavelet Toolbox" "Parallel Computing Toolbox" "MATLAB Coder"];
toolbox_checks=local_toolbox_checks(names);
present=[toolbox_checks.pass];
license_ok=license('test','Distrib_Computing_Toolbox');
cluster_workers=0; cluster_error='';
try c=parcluster('Processes'); cluster_workers=double(c.NumWorkers); catch ME, cluster_error=ME.message; end
cc_name=''; cc_version='';
try cc=mex.getCompilerConfigurations('C++','Selected'); if ~isempty(cc), cc_name=cc(1).Name; cc_version=cc(1).Version; end, catch, end
git=local_git(spec.root);
authority=local_hashes(spec);
cpu_model=local_cpu_model();
host_identity=shape.production_host_identity();
cfg=shape.config();
operational=local_operational_dependencies(spec);
try
    models=shape.load_models(spec.code_dir);
    mex_test=shape.ctdq_mex_selftest(models,cfg);
catch ME
    mex_test=struct('pass',false,'status','SELFTEST_ERROR','reason',ME.message,'identifier',ME.identifier);
end
runtime_env=struct('arch',computer('arch'),'matlab_version',version, ...
    'coder_version','','compiler_name',cc_name,'compiler_version',cc_version);
v=products(names=="MATLAB Coder"); if ~isempty(v), runtime_env.coder_version=v(1).Version; end
environment_policy=shape.observer_ctdq_environment_policy(runtime_env,cfg);
report=struct('hostname',local_hostname(),'session_id',char(java.util.UUID.randomUUID()), ...
    'matlab_version',version,'release',version('-release'),'architecture',computer('arch'), ...
    'os',char(system_dependent('getos')),'required_toolboxes',{cellstr(required)}, ...
    'toolbox_checks',toolbox_checks,'toolboxes_present',logical(present), ...
    'all_required_toolboxes_present',all(present), ...
    'parallel_license_available',logical(license_ok),'process_cluster_capacity',cluster_workers, ...
    'process_cluster_error',cluster_error,'requested_workers',workers, ...
    'requested_workers_feasible',license_ok && workers>=1 && workers==floor(workers) && workers<=cluster_workers, ...
    'compiler_name',cc_name,'compiler_version',cc_version,'cpu_model',cpu_model, ...
    'host_identity',host_identity,'git',git, ...
    'protected_authorities',authority,'observer_mex_selftest',mex_test, ...
    'observer_environment_policy',environment_policy, ...
    'supported_environment_profile',environment_policy.profile, ...
    'fresh_physical_host_qualification_required',environment_policy.requires_fresh_physical_host_qualification, ...
    'operational_dependencies',operational);
checks=[ ...
    local_check('architecture','win64',report.architecture,strcmp(report.architecture,'win64')); ...
    local_check('supported_environment_profile', ...
        'Update 4 + MinGW historical authority OR Update 5 + MSVC 2022 candidate', ...
        sprintf('%s | MATLAB %s | %s %s',environment_policy.profile,report.matlab_version,cc_name,cc_version), ...
        environment_policy.supported); ...
    local_check('required_toolboxes','all required products available',sprintf('%d/%d available',sum(present),numel(present)),report.all_required_toolboxes_present); ...
    local_check('parallel_license','available',string(report.parallel_license_available),report.parallel_license_available); ...
    local_check('process_worker_capacity',sprintf('>= %d',workers),sprintf('%d',cluster_workers),report.requested_workers_feasible); ...
    local_check('production_monitor_dependencies','PowerShell + CIM + bundled P6 monitor',operational.summary,operational.pass); ...
    local_check('protected_authority_hashes','all exact',string(authority.all_match),authority.all_match); ...
    local_check('observer_mex_selftest','SELFTEST_PASS',string(mex_test.status),logical(mex_test.pass))];
report.compatibility_checks=checks;
report.failed_check_names={checks(~[checks.pass]).name};
report.static_compatibility_pass=all([checks.pass]);
end

function report=local_operational_dependencies(spec)
monitor=fullfile(spec.root,'docs','codex_p6_worker_topology','p6_resource_monitor.ps1');
[ps_status,ps_path]=system('where powershell.exe');
powershell_available=ps_status==0 && strlength(strtrim(string(ps_path)))>0;
cim_available=false; cim_detail='PowerShell unavailable';
if powershell_available
    [cim_status,cim_output]=system(['powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ' ...
        '"$x=Get-CimInstance Win32_OperatingSystem -ErrorAction Stop; ' ...
        'if($null -eq $x){exit 2}else{Write-Output $x.Caption}"']);
    cim_available=cim_status==0;
    cim_detail=strtrim(cim_output);
end
monitor_present=isfile(monitor);
report=struct('pass',powershell_available && cim_available && monitor_present, ...
    'powershell_available',powershell_available,'powershell_path',strtrim(ps_path), ...
    'cim_available',cim_available,'cim_detail',cim_detail, ...
    'monitor_script_present',monitor_present,'monitor_script',monitor, ...
    'summary',sprintf('powershell=%d; cim=%d; monitor=%d',powershell_available,cim_available,monitor_present));
end

function checks=local_toolbox_checks(names)
required=["Simulink" "Stateflow" "Optimization Toolbox" "Wavelet Toolbox" "Parallel Computing Toolbox" "MATLAB Coder"];
checks=repmat(struct('name','','detection_method','','observed','','pass',false),numel(required),1);
for k=1:numel(required)
    name=required(k);
    if name=="Stateflow"
        licensed=license('test','Stateflow'); implementation=which('sfroot');
        pass=licensed && ~isempty(implementation);
        observed=sprintf('license=%d; sfroot=%s',licensed,implementation);
        method='Stateflow license feature plus public sfroot implementation';
    else
        pass=any(names==name); observed=sprintf('ver product listed=%d',pass); method='MATLAB ver product listing';
    end
    checks(k)=struct('name',char(name),'detection_method',method,'observed',observed,'pass',logical(pass));
end
end

function check=local_check(name,expected,observed,pass)
check=struct('name',name,'expected',char(string(expected)),'observed',char(string(observed)),'pass',logical(pass));
end

function report=local_hashes(spec)
items=repmat(struct('path','','expected_sha256','','actual_sha256','','match',false),size(spec.authorities,1),1);
for k=1:size(spec.authorities,1)
    p=fullfile(spec.root,strrep(spec.authorities{k,1},'/',filesep)); actual=''; if isfile(p), actual=shape.sha256_file(p); end
    items(k)=struct('path',spec.authorities{k,1},'expected_sha256',spec.authorities{k,2}, ...
        'actual_sha256',actual,'match',strcmpi(actual,spec.authorities{k,2}));
end
report=struct('all_match',all([items.match]),'files',items);
end

function g=local_git(root)
[s1,head]=system(sprintf('git -C "%s" rev-parse HEAD',root)); [~,branch]=system(sprintf('git -C "%s" branch --show-current',root));
[s3,status]=system(sprintf('git -C "%s" status --porcelain',root));
g=struct('available',s1==0,'head',strtrim(head),'branch',strtrim(branch),'dirty',s3~=0||strlength(strtrim(status))>0);
end
function h=local_hostname()
h=getenv('COMPUTERNAME'); if isempty(h), [~,h]=system('hostname'); h=strtrim(h); end
end
function value=local_cpu_model()
value='';
if ispc
    try value=strtrim(winqueryreg('HKEY_LOCAL_MACHINE', ...
            'HARDWARE\DESCRIPTION\System\CentralProcessor\0','ProcessorNameString')); catch, end
end
end
