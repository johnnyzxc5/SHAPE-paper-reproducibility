function info=configure_worker_filegen(session_root,session_id,repository_root,worker_index,worker_count)
%CONFIGURE_WORKER_FILEGEN Assign and verify worker-local Simulink file generation.
session_root=local_canonical(session_root); repository_root=local_canonical(repository_root);
marker_path=fullfile(session_root,'.worker_filegen_owner.json');
assert(isfile(marker_path),'shape:filegen:UnownedSession','Worker file-generation session is not initialized.');
marker=jsondecode(fileread(marker_path));
assert(strcmp(marker.session_id,session_id) && ...
    strcmpi(local_canonical(marker.session_root),session_root) && ...
    strcmpi(local_canonical(marker.repository_root),repository_root), ...
    'shape:filegen:OwnershipMismatch','Worker file-generation ownership marker mismatch.');
assert(isscalar(worker_index)&&worker_index>=1&&worker_index==floor(worker_index) && ...
    isscalar(worker_count)&&worker_count>=worker_index&&worker_count==floor(worker_count), ...
    'shape:filegen:InvalidWorkerIdentity','Invalid process-worker index/count.');
cache=local_canonical(fullfile(session_root,'cache',sprintf('worker_%03d',worker_index)));
codegen=local_canonical(fullfile(session_root,'codegen',sprintf('worker_%03d',worker_index)));
local_assert_descendant(cache,session_root); local_assert_descendant(codegen,session_root);
repo_slprj=local_canonical(fullfile(repository_root,'slprj'));
assert(~local_same_or_descendant(cache,repo_slprj) && ~local_same_or_descendant(codegen,repo_slprj), ...
    'shape:filegen:RepositorySlprj','Repository-root slprj cannot be used.');
if ~isfolder(cache), mkdir(cache); end
if ~isfolder(codegen), mkdir(codegen); end
Simulink.fileGenControl('set','CacheFolder',cache,'CodeGenFolder',codegen,'CreateDir',true);
actual_cache=local_canonical(char(Simulink.fileGenControl('get','CacheFolder')));
actual_codegen=local_canonical(char(Simulink.fileGenControl('get','CodeGenFolder')));
assert(strcmpi(actual_cache,cache) && strcmpi(actual_codegen,codegen), ...
    'shape:filegen:ReadbackMismatch','Simulink file-generation read-back mismatch.');
task=getCurrentTask();
assert(~isempty(task),'shape:filegen:ProcessWorkerRequired','Configuration must execute inside a Process worker.');
info=struct('schema_version','worker-filegen-runtime-v1','session_id',session_id, ...
    'worker_index',double(worker_index),'worker_count',double(worker_count), ...
    'worker_identity',sprintf('process-worker-%03d',worker_index), ...
    'hostname',getenv('COMPUTERNAME'),'process_id',double(matlabProcessID), ...
    'cache_folder',actual_cache,'codegen_folder',actual_codegen, ...
    'cache_readback_match',true,'codegen_readback_match',true, ...
    'repository_root_slprj_used',false,'configured_utc',local_now());
setappdata(0,'shape_worker_filegen_info',info);
end

function local_assert_descendant(path,parent)
assert(local_same_or_descendant(path,parent) && ~strcmpi(path,parent), ...
    'shape:filegen:OutsideSession','Worker path is outside its owned session root.');
end
function tf=local_same_or_descendant(path,parent)
p=lower(strrep(local_canonical(path),'\','/')); q=lower(strrep(local_canonical(parent),'\','/'));
tf=strcmp(p,q)||startsWith(p,[q '/']);
end
function value=local_canonical(path)
value=char(java.io.File(char(string(path))).getCanonicalPath());
end
function value=local_now()
value=char(datetime('now','TimeZone','UTC','Format','yyyy-MM-dd''T''HH:mm:ss.SSSXXX'));
end
