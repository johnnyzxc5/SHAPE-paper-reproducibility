function [artifact_path,receipt_path] = save_frozen_trajectory(registry_dir,artifact,receipt)
%SAVE_FROZEN_TRAJECTORY Persist canonical accepted geometry and receipt.
if ~isfolder(registry_dir), mkdir(registry_dir); end
id=double(artifact.parent_trajectory_id);
artifact_path=fullfile(registry_dir,sprintf('parent_%04d_trajectory.mat',id));
receipt_path=fullfile(registry_dir,sprintf('parent_%04d_qualification.json',id));
if isfile(artifact_path)
    old=load(artifact_path,'artifact');
    if ~isfield(old,'artifact') || ~strcmp(old.artifact.trajectory_sha256,artifact.trajectory_sha256)
        error('shape:trajectory:ImmutableArtifactConflict','Existing artifact differs for parent %d.',id);
    end
else
    tmp=[artifact_path '.tmp']; save(tmp,'artifact','-v7.3'); movefile(tmp,artifact_path,'f');
end
shape.write_json_atomic(receipt_path,receipt);
end
