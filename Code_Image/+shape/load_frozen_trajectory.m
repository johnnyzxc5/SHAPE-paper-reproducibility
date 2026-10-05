function ref = load_frozen_trajectory(record,registry_dir,cfg,models)
%LOAD_FROZEN_TRAJECTORY Load and verify canonical parent reference.
id=double(record.parent_trajectory_id);
path=fullfile(registry_dir,sprintf('parent_%04d_trajectory.mat',id));
if isfield(cfg,'trajectory_binding_path') && ~isempty(cfg.trajectory_binding_path)
    if ~isfile(cfg.trajectory_binding_path)
        error('shape:trajectory:NotQualified','TRAJECTORY_NOT_QUALIFIED: V2 binding is missing.');
    end
    binding=parquetread(cfg.trajectory_binding_path);
    row=binding(binding.parent_id==id,:);
    if height(row)~=1 || string(row.qualification_status)~="PASS"
        error('shape:trajectory:NotQualified','TRAJECTORY_NOT_QUALIFIED: parent %d absent from V2 binding.',id);
    end
else
    row=table(); % Explicit unit-test seam; production config always binds V2.
end
if ~isfile(path)
    error('shape:trajectory:NotQualified','TRAJECTORY_NOT_QUALIFIED: parent %d.',id);
end
s=load(path,'artifact');
if ~isfield(s,'artifact'), error('shape:trajectory:CorruptArtifact','Artifact variable missing.'); end
shape.verify_frozen_trajectory(s.artifact,record,models,cfg);
if ~isempty(row)
    if string(row.trajectory_sha256)~=string(s.artifact.trajectory_sha256) || ...
            string(row.generator_sha256)~=string(s.artifact.generator_sha256) || ...
            string(row.constraint_contract_sha256)~=string(s.artifact.constraint_contract_sha256) || ...
            string(row.model_sha256)~=string(s.artifact.model_sha256)
        error('shape:trajectory:BindingMismatch','V2 binding hashes do not match frozen artifact.');
    end
end
ref=s.artifact.reference;
% Carry immutable trajectory provenance into every physical run artifact.
ref.parent_trajectory_id=double(s.artifact.parent_trajectory_id);
ref.trajectory_sha256=char(string(s.artifact.trajectory_sha256));
ref.generator_sha256=char(string(s.artifact.generator_sha256));
ref.constraint_contract_sha256=char(string(s.artifact.constraint_contract_sha256));
ref.model_sha256=char(string(s.artifact.model_sha256));
if ~isempty(row)
    ref.trajectory_binding_sha256=char(string(shape.sha256_file(cfg.trajectory_binding_path)));
else
    ref.trajectory_binding_sha256='';
end
ref.K_segments=double(s.artifact.K_segments);
ref.trajectory_mode=char(string(s.artifact.trajectory_mode));
end
