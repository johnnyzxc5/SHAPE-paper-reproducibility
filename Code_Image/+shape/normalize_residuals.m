function out = normalize_residuals(res,cfg)
%NORMALIZE_RESIDUALS Fixed a-priori physical scaling (never sample-fitted).
out=struct();
out.shape=single(res.shape ./ cfg.power_ref);
out.torque=single(res.torque ./ cfg.tau_max);
out.gmo=single(res.gmo ./ cfg.tau_max);
out.energy=single(res.energy ./ cfg.robot_power_ref);
end
