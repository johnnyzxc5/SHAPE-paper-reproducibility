function report=validate_production_shard(shard_root,varargin)
%VALIDATE_PRODUCTION_SHARD Read-only canonical validation of one production shard.
p=inputParser; p.addParameter('RequireComplete',false,@(x)islogical(x)&&isscalar(x)); p.parse(varargin{:});
assignment_path=fullfile(shard_root,'assignment.json'); assert(isfile(assignment_path),'Shard assignment is missing.');
a=jsondecode(fileread(assignment_path));
spec=shape.production_spec('TrajectoryRegistry',a.trajectory_registry);
[expected,rows,~,cfg]=shape.production_assignment(spec,a.cohort,double(a.parent_ids(:)'),double(a.workers),string(a.shard_id));
assert(strcmp(jsonencode(double(expected.parent_ids)),jsonencode(double(a.parent_ids(:)'))),'Assignment parent IDs changed.');
assert(strcmpi(expected.manifest_sha256,a.manifest_sha256) && strcmpi(expected.binding_sha256,a.binding_sha256),'Assignment authority changed.');
outputs=fullfile(shard_root,'outputs'); binding=parquetread(spec.binding); n=height(rows);
inventory=repmat(struct('run_uid','','parent_id',0,'path','','sha256','','bytes',0,'state','MISSING'),n,1);
valid=0; missing=0; invalid=0; parent_mismatch=0; trajectory_mismatch=0; fallbacks=0;
for k=1:n
    r=rows(k,:); path=shape.output_path(outputs,r);
    inventory(k).run_uid=char(string(r.run_uid)); inventory(k).parent_id=double(r.parent_trajectory_id); inventory(k).path=path;
    if ~isfile(path), missing=missing+1; continue, end
    try
        shape.validate_output_gate08_fast_p4(path,char(string(r.run_uid)),cfg,r);
        uid=string(h5readatt(path,'/','run_uid')); parent=double(h5readatt(path,'/','parent_trajectory_id'));
        b=binding(binding.parent_id==r.parent_trajectory_id,:);
        tsha=string(h5readatt(path,'/','trajectory_sha256')); bsha=string(h5readatt(path,'/','trajectory_binding_sha256'));
        msha=string(h5readatt(path,'/','input_manifest_sha256'));
        backend=string(h5readatt(path,'/','observer_ctdq_backend')); status=string(h5readatt(path,'/','observer_ctdq_status'));
        fallback=logical(h5readatt(path,'/','observer_ctdq_fallback_used'));
        parent_bad=uid~=string(r.run_uid) || parent~=double(r.parent_trajectory_id);
        trajectory_bad=height(b)~=1 || tsha~=string(b.trajectory_sha256) || bsha~=string(spec.binding_sha) || msha~=string(expected.manifest_sha256);
        observer_bad=backend~="finite_difference_batch_mex" || status~="MEX_ACTIVE" || fallback;
        if parent_bad || trajectory_bad || observer_bad, error('shape:production:ProvenanceMismatch','Serialized production provenance mismatch.'); end
        info=dir(path); inventory(k).sha256=shape.sha256_file(path); inventory(k).bytes=double(info.bytes); inventory(k).state='VALID';
        valid=valid+1;
    catch
        invalid=invalid+1; inventory(k).state='INVALID';
        try
            parent_mismatch=parent_mismatch+(string(h5readatt(path,'/','run_uid'))~=string(r.run_uid) || double(h5readatt(path,'/','parent_trajectory_id'))~=double(r.parent_trajectory_id));
            b=binding(binding.parent_id==r.parent_trajectory_id,:);
            trajectory_mismatch=trajectory_mismatch+(string(h5readatt(path,'/','trajectory_sha256'))~=string(b.trajectory_sha256));
            fallbacks=fallbacks+logical(h5readatt(path,'/','observer_ctdq_fallback_used'));
        catch
        end
    end
end
actual=dir(fullfile(outputs,'**','run_*.h5')); actual_paths=strings(numel(actual),1);
for k=1:numel(actual), actual_paths(k)=string(fullfile(actual(k).folder,actual(k).name)); end
expected_paths=string({inventory.path}); extras=sum(~ismember(actual_paths,expected_paths));
tmp=dir(fullfile(outputs,'**','*.tmp')); corrupt=dir(fullfile(outputs,'**','*.corrupt.*'));
uids=string({inventory.run_uid}); uid_duplicates=numel(uids)-numel(unique(uids));
complete=valid==n && missing==0 && invalid==0 && extras==0 && uid_duplicates==0 && isempty(tmp);
if p.Results.RequireComplete, assert(complete,'Production shard is not complete and valid.'); end
if complete, status='SHARD_VALIDATION_PASS'; elseif extras>0||uid_duplicates>0, status='SHARD_CONFLICT'; else, status='SHARD_INCOMPLETE_RESUMABLE'; end
report=struct('schema_version','production-shard-validation-v1','status',status,'pass',complete, ...
    'cohort',a.cohort,'shard_id',a.shard_id,'parent_ids',double(a.parent_ids(:)'), ...
    'expected_parents',numel(a.parent_ids),'expected_runs',n,'valid_outputs',valid, ...
    'pending_outputs',missing+invalid,'missing_outputs',missing,'invalid_outputs',invalid, ...
    'unexpected_outputs',extras,'uid_duplicates',uid_duplicates,'parent_id_mismatches',parent_mismatch, ...
    'trajectory_sha_mismatches',trajectory_mismatch,'fallbacks',fallbacks, ...
    'temporary_residue_count',numel(tmp),'quarantine_count',numel(corrupt), ...
    'inventory',inventory,'validated_utc',local_now(),'production_authorized',false);
end
function value=local_now()
value=char(datetime('now','TimeZone','UTC','Format','yyyy-MM-dd''T''HH:mm:ss.SSSXXX'));
end
