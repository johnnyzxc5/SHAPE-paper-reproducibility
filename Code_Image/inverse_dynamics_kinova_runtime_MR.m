function tau = inverse_dynamics_kinova_runtime_MR(q, dq, ddq_ref, Mlist_nom, Glist_nom, Slist_nom)
%INVERSE_DYNAMICS_KINOVA_RUNTIME_MR Runtime-only wrapper measuring Computed_Torque execution.
% Specializes geometric inverse dynamics via qualified P3 shared kinematics.
% Preserves exact semantic decomposition: rigid-body RNEA, rotor inertia, nominal friction.
%#codegen

coder.extrinsic('p0_profile_bridge');
t0 = tic;

% 1. Pre-allocation
tau = zeros(6, 1);

% 2. Force column vectors
q = reshape(q, 6, 1);
dq = reshape(dq, 6, 1);
ddq_ref = reshape(ddq_ref, 6, 1);

% Physical constants (identical to frozen inverse_dynamics_kinova_MR)
J_rotors = diag([0.172, 0.172, 0.172, 0.089, 0.089, 0.089]);
g = [0; 0; -9.80665];
Ftip = zeros(6, 1);

% 3. Rigid-body inverse dynamics (RNEA via qualified shared kinematics)
kin = rnea_shared_kinematics_MR(q, Mlist_nom, Slist_nom);
tau_geo = InverseDynamicsSharedKinematics_MR(dq, ddq_ref, g, Ftip, Glist_nom, kin);

% 4. Nominal friction compensation
tau_fric = reshape(get_Friction_Nominal(dq, ddq_ref), 6, 1);

% 5. Final assembly
tau = tau_geo + (J_rotors * ddq_ref) + tau_fric;

dt = toc(t0);
p0_profile_bridge('ct', dt);
end

