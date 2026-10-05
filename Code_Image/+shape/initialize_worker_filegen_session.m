function marker=initialize_worker_filegen_session(session_root,session_id,owner_kind,repository_root)
%INITIALIZE_WORKER_FILEGEN_SESSION Establish an auditable generated-file root.
session_root=local_canonical(session_root); repository_root=local_canonical(repository_root);
assert(~strcmpi(session_root,repository_root) && ...
    ~startsWith(lower(strrep(session_root,'\','/')),[lower(strrep(repository_root,'\','/')) '/']), ...
    'shape:filegen:RepositoryOverlap','Worker file-generation root must be outside the repository.');
assert(~isempty(regexp(session_id,'^[A-Za-z0-9][A-Za-z0-9_-]{2,127}$','once')), ...
    'shape:filegen:InvalidSession','Invalid file-generation session identity.');
if ~isfolder(session_root), mkdir(session_root); end
marker_path=fullfile(session_root,'.worker_filegen_owner.json');
marker=struct('schema_version','worker-filegen-session-v1','session_id',session_id, ...
    'owner_kind',owner_kind,'session_root',session_root,'repository_root',repository_root, ...
    'created_utc',local_now(),'cleanup_scope','SESSION_ROOT_ONLY');
if isfile(marker_path)
    existing=jsondecode(fileread(marker_path));
    assert(strcmp(existing.session_id,session_id) && ...
        strcmpi(local_canonical(existing.session_root),session_root) && ...
        strcmpi(local_canonical(existing.repository_root),repository_root), ...
        'shape:filegen:OwnershipMismatch','Existing file-generation ownership marker differs.');
    marker=existing;
else
    shape.write_json_atomic(marker_path,marker);
end
end

function value=local_canonical(path)
value=char(java.io.File(char(string(path))).getCanonicalPath());
end
function value=local_now()
value=char(datetime('now','TimeZone','UTC','Format','yyyy-MM-dd''T''HH:mm:ss.SSSXXX'));
end
