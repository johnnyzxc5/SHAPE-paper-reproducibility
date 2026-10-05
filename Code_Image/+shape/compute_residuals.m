function [res,diagnostics] = compute_residuals(telemetry,ref,models,cfg)
%COMPUTE_RESIDUALS Canonical R1--R4 with causal Tustin observer states.
q=double(telemetry.q); dq=double(telemetry.dq); tau=double(telemetry.tau_cmd);
assert(isequal(size(q),[6 cfg.n_time]) && isequal(size(dq),size(q)) && isequal(size(tau),size(q)));
tau_nom=double(ref.tau_nom);
algebra_tic=tic;
res.torque=single(tau-tau_nom);
res.shape=single(tau.*dq-tau_nom.*double(ref.dq));
timing=struct('algebra_s',toc(algebra_tic),'mass_matrix_s',0,'gravity_s',0, ...
    'coriolis_transpose_s',0,'friction_s',0,'observer_update_s',0);
K=cfg.observer_gain; dt=cfg.telemetry_dt_s;
instrument=isfield(cfg,'performance_instrumentation') && cfg.performance_instrumentation;
counts=struct('temporal_samples',0,'direct_mass_matrix_calls',0, ...
    'coriolis_transpose_calls',0,'finite_difference_mass_matrix_calls',0, ...
    'gravity_calls',0,'friction_calls',0,'observer_state_update_calls',0);
a=(1-K*dt/2)/(1+K*dt/2); b=dt/(2*(1+K*dt/2));
xi=zeros(6,cfg.n_time); xiE=zeros(1,cfg.n_time);
mom=zeros(6,cfg.n_time); kinetic=zeros(1,cfg.n_time);
u=zeros(6,cfg.n_time); uE=zeros(1,cfg.n_time);
ctdq_batch=[]; ctdq_batch_diag=struct();
ctdq_calls_per_sample=12;
if isfield(cfg,'observer_ctdq_precomputed') && ~isempty(cfg.observer_ctdq_precomputed)
    ctdq_batch=double(cfg.observer_ctdq_precomputed);
    assert(isequal(size(ctdq_batch),size(q)),'shape:ctdq:PrecomputedSizeMismatch');
    assert(all(isfinite(ctdq_batch(:))),'shape:ctdq:PrecomputedNonFinite');
    ctdq_calls_per_sample=0;
    ctdq_batch_diag=struct('requested_backend',cfg.observer_ctdq_backend, ...
        'actual_backend','finite_difference_gold_cache','fallback_used',false, ...
        'mass_matrix_calls_per_sample',0,'implementation','verified noncanonical P1B GOLD cache', ...
        'status','GOLD_CACHE_ACTIVE','backend_version',cfg.observer_ctdq_gold_version, ...
        'requested_backend_version',cfg.observer_ctdq_gold_version, ...
        'actual_backend_version',cfg.observer_ctdq_gold_version, ...
        'mex_sha256','','source_sha256',shape.sha256_file(fullfile( ...
        fileparts(mfilename('fullpath')),'coriolis_transpose_velocity.m')));
elseif ~strcmp(cfg.observer_ctdq_backend,'finite_difference_gold')
    component_tic=tic;
    [ctdq_batch,ctdq_batch_diag]=shape.evaluate_ctdq(q,dq,models,cfg);
    timing.coriolis_transpose_s=toc(component_tic);
end
% Reset shared kinematics cache state to prevent cross-observer state inheritance
rnea_shared_kinematics_MR([], [], [], 'reset');
zero6 = zeros(6, 1);
for k=1:cfg.n_time
    if instrument, counts.temporal_samples=counts.temporal_samples+1; end
    component_tic=tic;
    kin=rnea_shared_kinematics_MR(q(:,k),models.Mlist_nom,models.Slist_nom);
    M=MassMatrixZeroStateSharedKinematics_MR(models.Glist_nom,kin)+cfg.rotor_inertia;
    if instrument, counts.direct_mass_matrix_calls=counts.direct_mass_matrix_calls+1; end
    timing.mass_matrix_s=timing.mass_matrix_s+toc(component_tic); component_tic=tic;
    g=InverseDynamicsSharedKinematics_MR(zero6,zero6,cfg.gravity,zero6,models.Glist_nom,kin);
    if instrument, counts.gravity_calls=counts.gravity_calls+1; end
    timing.gravity_s=timing.gravity_s+toc(component_tic); component_tic=tic;
    if isempty(ctdq_batch)
        component_tic=tic;
        if instrument
            [ctdq,cdiag]=shape.coriolis_transpose_velocity(q(:,k),dq(:,k),models);
        else
            ctdq=shape.coriolis_transpose_velocity(q(:,k),dq(:,k),models);
        end
        timing.coriolis_transpose_s=timing.coriolis_transpose_s+toc(component_tic);
    else
        ctdq=ctdq_batch(:,k);
        cdiag=ctdq_batch_diag;
    end
    if instrument
        counts.coriolis_transpose_calls=counts.coriolis_transpose_calls+1;
        counts.finite_difference_mass_matrix_calls=counts.finite_difference_mass_matrix_calls+ctdq_calls_per_sample;
    end
    component_tic=tic;
    fric=get_Friction_Nominal(dq(:,k),zeros(6,1));
    if instrument, counts.friction_calls=counts.friction_calls+1; end
    timing.friction_s=timing.friction_s+toc(component_tic); component_tic=tic;
    mom(:,k)=M*dq(:,k); kinetic(k)=0.5*dq(:,k)'*M*dq(:,k);
    u(:,k)=K*mom(:,k)+tau(:,k)-g+ctdq-fric;
    uE(k)=K*kinetic(k)+dq(:,k)'*(tau(:,k)-g-fric);
    if k==1
        xi(:,k)=mom(:,k); xiE(k)=kinetic(k);
    else
        xi(:,k)=a*xi(:,k-1)+b*(u(:,k)+u(:,k-1));
        xiE(k)=a*xiE(k-1)+b*(uE(k)+uE(k-1));
    end
    if instrument, counts.observer_state_update_calls=counts.observer_state_update_calls+1; end
    timing.observer_update_s=timing.observer_update_s+toc(component_tic);
end
res.gmo=single(K*(mom-xi)); res.gmo(:,1)=0;
res.energy=single(K*(kinetic-xiE)); res.energy(1)=0;
diagnostics=struct('momentum',mom,'kinetic_energy',kinetic,'gmo_state',xi, ...
    'energy_state',xiE,'observer_input',u,'energy_input',uE,'timing',timing);
diagnostics.ctdq_backend=cfg.observer_ctdq_backend;
diagnostics.ctdq_backend_details=ctdq_batch_diag;
if isempty(fieldnames(ctdq_batch_diag))
    diagnostics.ctdq_backend_details=struct('requested_backend','finite_difference_gold', ...
        'actual_backend','finite_difference_gold','fallback_used',false, ...
        'mass_matrix_calls_per_sample',12,'implementation','MATLAB central finite difference GOLD', ...
        'status','GOLD_ACTIVE','backend_version',cfg.observer_ctdq_gold_version, ...
        'requested_backend_version',cfg.observer_ctdq_gold_version, ...
        'actual_backend_version',cfg.observer_ctdq_gold_version, ...
        'mex_sha256','','source_sha256',shape.sha256_file(fullfile( ...
        fileparts(mfilename('fullpath')),'coriolis_transpose_velocity.m')));
end
if instrument, diagnostics.timing.counts=counts; end
end
