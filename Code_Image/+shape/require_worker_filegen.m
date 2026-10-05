function info=require_worker_filegen(session_id,repository_root)
%REQUIRE_WORKER_FILEGEN Fail closed before model load if worker isolation drifted.
assert(isappdata(0,'shape_worker_filegen_info'), ...
    'shape:filegen:NotConfigured','Worker-local Simulink file generation is not configured.');
info=getappdata(0,'shape_worker_filegen_info');
assert(strcmp(info.session_id,session_id), ...
    'shape:filegen:SessionMismatch','Worker file-generation session mismatch.');
actual_cache=char(Simulink.fileGenControl('get','CacheFolder'));
actual_codegen=char(Simulink.fileGenControl('get','CodeGenFolder'));
assert(strcmpi(local_canonical(actual_cache),local_canonical(info.cache_folder)) && ...
    strcmpi(local_canonical(actual_codegen),local_canonical(info.codegen_folder)), ...
    'shape:filegen:ReadbackDrift','Worker file-generation read-back changed after configuration.');
repo_slprj=local_canonical(fullfile(repository_root,'slprj'));
assert(~local_same_or_descendant(actual_cache,repo_slprj) && ...
    ~local_same_or_descendant(actual_codegen,repo_slprj), ...
    'shape:filegen:RepositorySlprj','Repository-root slprj is active.');
end

function tf=local_same_or_descendant(path,parent)
p=lower(strrep(local_canonical(path),'\','/')); q=lower(strrep(local_canonical(parent),'\','/'));
tf=strcmp(p,q)||startsWith(p,[q '/']);
end
function value=local_canonical(path)
value=char(java.io.File(char(string(path))).getCanonicalPath());
end
