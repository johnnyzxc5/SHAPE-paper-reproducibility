function [assignment,rows,models,cfg]=production_assignment(spec,cohort,parent_ids,workers,shard_id)
%PRODUCTION_ASSIGNMENT Validate complete-parent assignment and frozen trajectories.
cohort=upper(string(cohort)); parent_ids=double(parent_ids(:)');
assert(~isempty(parent_ids) && all(isfinite(parent_ids)) && all(parent_ids==floor(parent_ids)) && ...
    numel(unique(parent_ids))==numel(parent_ids),'Parent IDs must be unique finite integers.');
if cohort=="PRIMARY"
    manifest_path=spec.primary_manifest; manifest_sha=spec.primary_sha; sibling_count=4; valid_domain=1:5000;
elseif cohort=="E2B"
    manifest_path=spec.e2b_manifest; manifest_sha=spec.e2b_sha; sibling_count=10; valid_domain=5001:5030;
else
    error('shape:production:InvalidCohort','Cohort must be PRIMARY or E2B.');
end
assert(all(ismember(parent_ids,valid_domain)),'Assigned parent is outside the frozen cohort.');
assert(isfile(manifest_path) && strcmpi(shape.sha256_file(manifest_path),manifest_sha),'Frozen manifest SHA mismatch.');
assert(isfile(spec.binding) && strcmpi(shape.sha256_file(spec.binding),spec.binding_sha),'Frozen binding SHA mismatch.');
[T,manifest_report]=shape.validate_manifest(manifest_path); rows=T(ismember(T.parent_trajectory_id,parent_ids),:);
assert(height(rows)==sibling_count*numel(parent_ids),'Assignment does not contain complete sibling sets.');
for id=parent_ids
    r=rows(rows.parent_trajectory_id==id,:); assert(height(r)==sibling_count && numel(unique(string(r.run_uid)))==sibling_count);
    assert(isscalar(unique(r.trajectory_seed)) && isscalar(unique(r.K_segments)) && isscalar(unique(string(r.trajectory_mode))));
    if cohort=="PRIMARY"
        assert(isequal(sort(string(r.fault_class))',sort(["Nominal" "LoE" "Friction" "Vibration"])));
    else
        assert(all(string(r.fault_class)=="Vibration") && isequal(sort(double(r.f_d))',[2 5 8 11 14 17 20 23 26 30]));
    end
end
assert(numel(unique(string(rows.run_uid)))==height(rows),'Assignment contains duplicate UIDs.');
binding=parquetread(spec.binding); models=shape.load_models(spec.code_dir);
cfg=shape.config('num_workers',workers,'fast_restart',true,'overwrite',false,'max_retries',0, ...
    'mpc_shared_rnea_enabled',true,'mpc_mass_backend',1, ...
    'observer_ctdq_backend','finite_difference_batch_mex','observer_ctdq_mex_enabled',true, ...
    'observer_ctdq_selftest_enabled',true,'performance_instrumentation',true, ...
    'trajectory_registry_dir',spec.trajectory_registry,'trajectory_binding_path',spec.binding, ...
    'code_state_id',['production-shard-' char(shard_id)]);
cfg.active_manifest_path=manifest_path; cfg.active_manifest_sha256=manifest_sha;
trajectories=repmat(struct('parent_id',0,'path','','binding_sha256','','file_sha256',''),numel(parent_ids),1);
for k=1:numel(parent_ids)
    id=parent_ids(k); r=rows(find(rows.parent_trajectory_id==id,1),:);
    ref=shape.load_frozen_trajectory(r,spec.trajectory_registry,cfg,models);
    b=binding(binding.parent_id==id,:); assert(height(b)==1 && string(b.qualification_status)=="PASS");
    assert(strcmpi(ref.trajectory_sha256,char(string(b.trajectory_sha256))),'Frozen trajectory/binding mismatch.');
    path=fullfile(spec.trajectory_registry,sprintf('parent_%04d_trajectory.mat',id));
    trajectories(k)=struct('parent_id',id,'path',path,'binding_sha256',char(string(b.trajectory_sha256)), ...
        'file_sha256',shape.sha256_file(path));
end
assignment=struct('schema_version','production-shard-assignment-v1','cohort',char(cohort), ...
    'shard_id',char(shard_id),'parent_ids',parent_ids,'parent_count',numel(parent_ids), ...
    'expected_run_count',height(rows),'expected_run_uids',{cellstr(string(rows.run_uid))}, ...
    'siblings_per_parent',sibling_count,'workers',workers,'manifest_path',manifest_path, ...
    'manifest_sha256',manifest_sha,'binding_path',spec.binding,'binding_sha256',spec.binding_sha, ...
    'trajectory_registry',spec.trajectory_registry,'trajectories',trajectories, ...
    'manifest_report',manifest_report,'trajectory_generation_count',0);
end
