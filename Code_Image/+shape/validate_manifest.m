function [manifest, report] = validate_manifest(path)
%VALIDATE_MANIFEST Verify immutable bytes and campaign/pairing invariants.
[~,name,ext] = fileparts(path);
key = upper(string(name)+string(ext));
expected = containers.Map( ...
 {'PRIMARY_MANIFEST_DRY_RUN.PARQUET','E2B_PAIRED_MANIFEST_CANDIDATE.PARQUET','PILOT24_MANIFEST_CANDIDATE.PARQUET'}, ...
 {'676a0a412ff00943f65525034ca3c1e3f3614ac9cbfd6f5a62a70edc91a99472', ...
  '958201c8b598346c801a7df35748331cda6bc7bdb5f8abf68b627ab7dc59518c', ...
  '3055262237f62b934e8337dc867ea28ad9e50f178fdddc0be767429eaa57907e'});
if ~isKey(expected,char(key)), error('shape:manifest:Unknown','Not an active manifest: %s',path); end
actual = shape.sha256_file(path);
if ~strcmp(actual,expected(char(key)))
    error('shape:manifest:HashMismatch','Immutable manifest hash mismatch for %s.',path);
end
manifest = parquetread(path);
required = {'run_uid','parent_trajectory_id','split','fault_class','class_label', ...
 'target_joint','fault_joint','trajectory_mode','K_segments','t_fault','s_LoE', ...
 's_Friction','A_d','f_d','phi_d','analysis_stratum','trajectory_seed', ...
 'parameter_seed','fault_seed','noise_seed'};
assert(all(ismember(required,manifest.Properties.VariableNames)),'Missing canonical columns.');
assert(numel(unique(string(manifest.run_uid))) == height(manifest),'run_uid values must be unique.');
assert(all(manifest.target_joint == 2) && all(manifest.fault_joint == 2),'Fault joint must be Joint 2.');
if startsWith(key,'PRIMARY_')
    assert(height(manifest)==20000 && numel(unique(manifest.parent_trajectory_id))==5000);
    counts = groupcounts(manifest,'parent_trajectory_id');
    assert(all(counts.GroupCount==4),'Every Primary parent must have four siblings.');
elseif startsWith(key,'E2B_')
    assert(height(manifest)==300 && numel(unique(manifest.parent_trajectory_id))==30);
    local_check_e2b(manifest);
else
    assert(height(manifest)==116,'Pilot candidate must contain exactly 116 physical runs.');
end
report = struct('path',string(path),'sha256',string(actual),'rows',height(manifest), ...
    'parents',numel(unique(manifest.parent_trajectory_id)),'valid',true);
end

function local_check_e2b(T)
freq = [2 5 8 11 14 17 20 23 26 30];
parents = unique(T.parent_trajectory_id);
assert(isequal(parents(:)',5001:5030));
invariant = {'split','fault_class','class_label','target_joint','fault_joint', ...
 'trajectory_mode','K_segments','t_fault','s_LoE','s_Friction','A_d','phi_d', ...
 'trajectory_seed','parameter_seed'};
for p = parents(:)'
    rows = T(T.parent_trajectory_id==p,:);
    assert(height(rows)==10 && isequal(sort(rows.f_d(:))',freq));
    assert(all(rows.A_d==1) && all(string(rows.fault_class)=="Vibration"));
    for c = invariant
        v = rows.(c{1});
        if iscell(v) || isstring(v) || iscategorical(v), assert(numel(unique(string(v)))==1);
        else, assert(numel(unique(v))==1); end
    end
end
end
