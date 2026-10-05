function report = verify_frozen_trajectory(artifact,record,models,cfg)
%VERIFY_FROZEN_TRAJECTORY Verify provenance, identity, shape and content hash.
contract=shape.trajectory_contract(models,cfg);
if double(artifact.parent_trajectory_id)~=double(record.parent_trajectory_id)
    error('shape:trajectory:ParentMismatch','Frozen parent identity mismatch.');
end
if double(artifact.trajectory_seed)~=double(record.trajectory_seed) || ...
        double(artifact.K_segments)~=double(record.K_segments) || ...
        string(artifact.trajectory_mode)~=string(record.trajectory_mode)
    error('shape:trajectory:ManifestMismatch','Frozen trajectory does not match manifest metadata.');
end
if ~strcmp(artifact.generator_sha256,contract.generator_sha256)
    error('shape:trajectory:GeneratorVersionMismatch','Frozen generator version differs from active source.');
end
if ~strcmp(artifact.constraint_contract_sha256,contract.constraint_sha256)
    error('shape:trajectory:ConstraintVersionMismatch','Frozen constraint contract differs from active authority.');
end
if ~strcmp(artifact.model_sha256,contract.model_sha256)
    error('shape:trajectory:ModelVersionMismatch','Frozen nominal robot model differs from active model.');
end
r=artifact.reference;
if ~isequal(size(r.q),[6 cfg.n_time]) || ~isequal(size(r.dq),[6 cfg.n_time]) || ...
        ~isequal(size(r.ddq),[6 cfg.n_time]) || numel(r.t)~=cfg.n_time
    error('shape:trajectory:ArtifactShape','Frozen reference dimensions are invalid.');
end
actual=shape.trajectory_content_hash(artifact);
if ~strcmp(actual,artifact.trajectory_sha256)
    error('shape:trajectory:CorruptArtifact','Frozen trajectory content hash mismatch.');
end
report=struct('status','PASS','parent_trajectory_id',double(artifact.parent_trajectory_id), ...
    'trajectory_sha256',actual,'generator_sha256',contract.generator_sha256, ...
    'constraint_contract_sha256',contract.constraint_sha256,'model_sha256',contract.model_sha256);
end
