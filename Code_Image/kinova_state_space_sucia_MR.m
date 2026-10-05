function dq_state = kinova_state_space_sucia_MR(x, tau_control, t, Mlist_suc, Glist_suc, Slist_suc, FaultConfig)
    %#codegen
    coder.extrinsic('p0_profile_bridge');
    p0_enabled = isfield(FaultConfig,'P0InstrumentationEnabled') && FaultConfig.P0InstrumentationEnabled;
    % A single timestamp keeps code-generation types fixed; all accumulation
    % and bridge traffic remain disabled when the P0 flag is false.
    p0_total_tic=tic; p0_tic=p0_total_tic;
    p0_fault_s=0; p0_friction_s=0; p0_inverse_s=0; p0_mass_s=0; p0_solve_s=0;
    
    dq_state = zeros(12, 1);
    q  = reshape(x(1:6), 6, 1);
    dq = reshape(x(7:12), 6, 1);
    tau_control = reshape(tau_control, 6, 1);
    
    % --- 1. LOGICA DE FALLAS (Inyeccion Parametrica) ---
    if p0_enabled, p0_tic=tic; end
    alpha = ones(6, 1);
    tau_dist = zeros(6, 1);
    delta_Fc = zeros(6, 1);
    
    if FaultConfig.Active
        % A. Falla LoE (Perdida de Efectividad)
        if t >= FaultConfig.LoE_time && FaultConfig.LoE_joint > 0 && FaultConfig.LoE_joint <= 6
            alpha(FaultConfig.LoE_joint) = FaultConfig.LoE_sev;
        end
        
        % B. Vibraciones Mecanicas (Torque Aditivo)
        if t >= FaultConfig.Vib_time && FaultConfig.Vib_joint > 0 && FaultConfig.Vib_joint <= 6
            % Frequency is in Hz; phase is a deterministic manifest value.
            vib_phase = 0;
            if isfield(FaultConfig, 'Vib_phase')
                vib_phase = FaultConfig.Vib_phase;
            end
            tau_dist(FaultConfig.Vib_joint) = FaultConfig.Vib_amp * ...
                sin(2*pi*FaultConfig.Vib_freq*t + vib_phase);
        end
        
        % C. Friccion Anomala (Degradacion de Coulomb)
        if t >= FaultConfig.Fric_time && FaultConfig.Fric_joint > 0 && FaultConfig.Fric_joint <= 6
            delta_Fc(FaultConfig.Fric_joint) = FaultConfig.Fric_delta_Fc;
        end
    end
    
    % Aplicar dano al torque (LoE) y sumar la vibracion
    tau_real_applied = (tau_control .* alpha) + tau_dist; 
    if p0_enabled, p0_fault_s=toc(p0_tic); p0_tic=tic; end
    
    % --- 2. DINAMICA DE LA PLANTA Y FRICCION ---
    J_rotors = diag([0.172, 0.172, 0.172, 0.089, 0.089, 0.089]);
    
    % Friccion base sucia
    tau_fric_base = reshape(get_Friction_Sucia(dq, zeros(6,1)), 6, 1); 
    
    % Anadir la anomalia de friccion (Stick-Slip)
    tau_fric_anomala = delta_Fc .* tanh(50 * dq);
    
    % Friccion Total
    tau_fric_total = tau_fric_base + tau_fric_anomala;
    if p0_enabled, p0_friction_s=toc(p0_tic); p0_tic=tic; end
    
    % Terminos Inerciales y de Gravedad (RNEA P4: Shared Kinematics + Zero-State MassMatrix)
    g = [0; 0; -9.80665];
    Ftip = zeros(6, 1);
    
    % Shared Kinematics (inlined Coder-compliant equivalent of rnea_shared_kinematics_MR)
    n = 6;
    Mi = eye(4);
    Ai = zeros(6, n);
    AdTi = zeros(6, 6, n + 1);
    AdTi(:, :, n + 1) = Adjoint(TransInv(Mlist_suc(:, :, n + 1)));
    for i = 1:n
        Mi = Mi * Mlist_suc(:, :, i);
        Ai(:, i) = Adjoint(TransInv(Mi)) * Slist_suc(:, i);
        AdTi(:, :, i) = Adjoint(MatrixExp6(VecTose3(Ai(:, i) * -q(i))) * TransInv(Mlist_suc(:, :, i)));
    end
    kin = struct('Ai', Ai, 'AdTi', AdTi, 'n', n);
    
    b_vector = InverseDynamicsSharedKinematics_MR(dq, zeros(6,1), g, Ftip, Glist_suc, kin);
    if p0_enabled, p0_inverse_s=toc(p0_tic); p0_tic=tic; end
    M_geo = MassMatrixZeroStateSharedKinematics_MR(Glist_suc, kin);
    if p0_enabled, p0_mass_s=toc(p0_tic); p0_tic=tic; end
    M_total = M_geo + J_rotors;
    
    % Resolver Aceleracion
    ddq = M_total \ (tau_real_applied - tau_fric_total - b_vector);
    if p0_enabled, p0_solve_s=toc(p0_tic); end
    
    % Ensamblaje Final
    dq_state(1:6)  = dq;
    dq_state(7:12) = reshape(ddq, 6, 1);
    if p0_enabled
        p0_profile_bridge('plant',[toc(p0_total_tic),p0_fault_s,p0_friction_s, ...
            p0_inverse_s,p0_mass_s,p0_solve_s]);
    end
end
