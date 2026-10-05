function v_total = solve_flatness_mpc_step_MR(q_curr, dq_curr, t, MPCPrepFlat, Mlist_nom, Glist_nom, Slist_nom)
    %#codegen
    coder.extrinsic('p0_profile_bridge');
    p0_enabled = isfield(MPCPrepFlat,'P0InstrumentationEnabled') && ...
        MPCPrepFlat.P0InstrumentationEnabled;
    if p0_enabled, p0_total_tic=tic; end
    
    % 1. PRE-ASIGNACIÓN Y DIMENSIONES
    v_total = zeros(6, 1);
    q_curr = reshape(q_curr, 6, 1);
    dq_curr = reshape(dq_curr, 6, 1);
    
    Ts = MPCPrepFlat.Ts;
    N_total = MPCPrepFlat.N;
    nu = 6; nq = 6;
    p0_b1_robot_dynamics_s = 0;
    p0_b2_block_torque_s = 0;
    p0_b3_constraint_assembly_s = 0;
    p0_b1a_shared_kinematics_s = 0;
    p0_b1b_mass_matrix_s = 0;
    p0_b1c_bias_friction_s = 0;

    % 2. Horizonte de tiempo k
    k = floor(t / Ts) + 1;
    if k >= N_total, k = N_total - 1; end

    % 3. Horizontes
    Np_max = 15; 
    Nc_max = 10;
    f = min(Np_max, N_total - k);
    v = min(Nc_max, f);

    if f <= 0
        v_total = MPCPrepFlat.uop(:, k);
        if p0_enabled
            early_profile=zeros(1,32); early_profile(1)=toc(p0_total_tic);
            p0_profile_bridge('mpc',early_profile,0,false);
        end
        return;
    end

    % ---------------------------------------------------------------------
    % MACRO BUCKET A: mpc_state_cost_prep_s
    % Context/cache retrieval, state error dx_k, reference residual s, cost f_B
    % ---------------------------------------------------------------------
    if p0_enabled, p0_tic=tic; end

    % 4. Matrices del Modelo
    AdF = MPCPrepFlat.Adseq(:,:,1);
    BdF = MPCPrepFlat.Bdseq(:,:,1);
    CdF = MPCPrepFlat.Cdseq(:,:,1);
    
    cache_enabled=isfield(MPCPrepFlat,'P2ExactCacheEnabled') && MPCPrepFlat.P2ExactCacheEnabled && ...
        isfield(MPCPrepFlat,'P2ExactCacheVersion') && ...
        strcmp(MPCPrepFlat.P2ExactCacheVersion,'p2-exact-invariants-v1');
    if cache_enabled
        [fixed,cache_meta]=mpc_exact_invariants_MR('get',AdF,BdF,CdF,Ts,f,v,Np_max,Nc_max);
    else
        [fixed,cache_meta]=mpc_exact_invariants_MR('recompute',AdF,BdF,CdF,Ts,f,v,Np_max,Nc_max);
    end

    % 5. Estado actual y error
    x_curr = [q_curr; dq_curr];
    dx_k = x_curr - MPCPrepFlat.xop(:,k);
    
    yref_seg = MPCPrepFlat.y_ref(:, k+1:k+f);
    yop_seg = MPCPrepFlat.yop(:, k+1:k+f);
    dr = reshape(yref_seg - yop_seg, [], 1);
    Ox = fixed.O * dx_k;
    s = dr - Ox;

    % 6. Pesos del MPC 
    w_s = 20*s;
    if any(w_s == 0)
        % Exact signed-zero/underflow fallback to the frozen dense GEMV.
        w_s = fixed.W4*s;
    end
    f_B = -2*(fixed.M_lift'*w_s);
    if p0_enabled
        p0_state_cost_prep_s = toc(p0_tic);
        p0_tic = tic;
    end

    % ---------------------------------------------------------------------
    % MACRO BUCKET B: mpc_dynamics_constraint_s
    % Robot dynamics (M_dyn, b_vec, friction), block mass M_blk, constraints
    % ---------------------------------------------------------------------
    % 7. Restricciones de Torque (Con vector de Fallos Alpha)
    if p0_enabled, p0_b1_tic = tic; end
    J_rotors = diag([0.172, 0.172, 0.172, 0.089, 0.089, 0.089]);
    g_vec = [0; 0; -9.81];
    shared_enabled=isfield(MPCPrepFlat,'P3SharedRNEAEnabled') && ...
        MPCPrepFlat.P3SharedRNEAEnabled && isfield(MPCPrepFlat,'P3SharedRNEAVersion') && ...
        strcmp(MPCPrepFlat.P3SharedRNEAVersion,'p3-shared-rnea-v1');
    zero_state_mass_enabled=shared_enabled && isfield(MPCPrepFlat,'P4BMassBackend') && ...
        isnumeric(MPCPrepFlat.P4BMassBackend) && MPCPrepFlat.P4BMassBackend==1;
    if p0_enabled, b1_sub_tic = tic; end
    if shared_enabled
        kin=rnea_shared_kinematics_MR(q_curr,Mlist_nom,Slist_nom);
    end
    if p0_enabled
        p0_b1a_shared_kinematics_s = toc(b1_sub_tic);
        b1_sub_tic = tic;
    end
    if shared_enabled
        if zero_state_mass_enabled
            M_geo=MassMatrixZeroStateSharedKinematics_MR(Glist_nom,kin);
        else
            M_geo=MassMatrixSharedKinematics_MR(Glist_nom,kin);
        end
    else
        M_geo=MassMatrix(q_curr,Mlist_nom,Glist_nom,Slist_nom);
    end
    M_dyn = M_geo + J_rotors;
    if p0_enabled
        p0_b1b_mass_matrix_s = toc(b1_sub_tic);
        b1_sub_tic = tic;
    end
    if shared_enabled
        b_vec=InverseDynamicsSharedKinematics_MR(dq_curr,zeros(6,1),g_vec, ...
            zeros(6,1),Glist_nom,kin);
    else
        b_vec=InverseDynamics(q_curr,dq_curr,zeros(6,1),g_vec,zeros(6,1), ...
            Mlist_nom,Glist_nom,Slist_nom);
    end
    tau_bias = b_vec + get_Friction_Nominal(dq_curr, zeros(nq,1));
    if p0_enabled
        p0_b1c_bias_friction_s = toc(b1_sub_tic);
        p0_b1_robot_dynamics_s = toc(p0_b1_tic);
    end

    persistent m_blk_diag_idx m_blk_rep_idx
    if isempty(m_blk_diag_idx)
        m_blk_diag_idx = cell(10,1);
        m_blk_rep_idx = cell(10,1);
        for k_dim = 1:10
            mask_k = false(6*k_dim, 6*k_dim);
            for j_blk = 1:k_dim
                idx_k = (j_blk-1)*6 + (1:6);
                mask_k(idx_k, idx_k) = true;
            end
            m_blk_diag_idx{k_dim} = find(mask_k);
            m_blk_rep_idx{k_dim} = repmat((1:36)', k_dim, 1);
        end
    end
    if v == 1
        M_blk = M_dyn;
    else
        M_blk = repmat(0.0 * M_dyn, v, v);
        M_blk(m_blk_diag_idx{v}) = M_dyn(m_blk_rep_idx{v});
    end
    uop_k = MPCPrepFlat.uop(:, k:k+v-1);
    tau_nom_vec = M_blk * reshape(uop_k, [], 1) + repmat(tau_bias, v, 1);
    
    % RESTAURADO: Límites con tolerancia a fallos
    A_u = [ M_blk; -M_blk ];
    b_u = [ fixed.tau_lim - tau_nom_vec; fixed.tau_lim + tau_nom_vec ];

    % 8. Límites Cinemáticos
    yop_flat = reshape(yop_seg, [], 1);
    b_y = [ fixed.qmax_flat - yop_flat - Ox; fixed.qmax_flat + yop_flat + Ox ];

    A_v = zeros(0, v*nu);
    b_v = zeros(0, 1);
    if f >= 2
        A_v = fixed.A_v;
        D1_y = fixed.D1 * (yop_flat + Ox);
        b_v = [ fixed.qd_max - D1_y; ...
            fixed.qd_max + D1_y ];
    end
    
    % 9. Optimization (QP)
    Aineq = [A_u; fixed.A_y; A_v];
    bineq = [b_u; b_y; b_v];
    
    % --- INICIO DEL PARCHE: Límites Nativos de Aceleración ---
    uop_k_vec = reshape(uop_k, [], 1);
    
    % Despejando dU_B (Límite predictivo = Físico - Nominal)
    lb = fixed.v_min_vec - uop_k_vec;
    ub = fixed.v_max_vec - uop_k_vec;
    % --- FIN DEL PARCHE ---
    
    persistent options options_key
    requested_options_key=uint32(1); % active-set, Display=off
    if isempty(options) || isempty(options_key) || options_key~=requested_options_key
        options = optimoptions('quadprog', 'Display', 'off', 'Algorithm', 'active-set');
        options_key=requested_options_key;
    end
    x0 = fixed.x0;
    if p0_enabled
        p0_dynamics_constraint_s = toc(p0_tic);
        p0_tic = tic;
    end
    
    % ---------------------------------------------------------------------
    % MACRO BUCKET C: mpc_qp_s (Preserving quadprog timing authority)
    % ---------------------------------------------------------------------
    [dU_B, ~, flag] = quadprog(fixed.H_B, f_B, Aineq, bineq, [], [], lb, ub, x0, options);
    if p0_enabled
        p0_qp_s = toc(p0_tic);
        p0_tic = tic;
    end
    
    % ---------------------------------------------------------------------
    % MACRO BUCKET D: mpc_postsolve_s (Solution unpacking & reconstruction)
    % ---------------------------------------------------------------------
    % 10. Salida
    if flag > 0
        v_total = MPCPrepFlat.uop(:,k) + dU_B(1:nu);
    else
        v_total = MPCPrepFlat.uop(:,k);
    end
    if p0_enabled
        p0_postsolve_s = toc(p0_tic);
        if shared_enabled
            shared_builds=1; matrixexp_count=6; q_adjoint_count=6;
        else
            shared_builds=0; matrixexp_count=42; q_adjoint_count=42;
        end
        p0_profile_bridge('mpc',[toc(p0_total_tic), 0, 0, 0, ...
            0, 0, 0, 0, 0, p0_qp_s, ...
            double(cache_meta.hit),double(cache_meta.miss),double(cache_meta.rebuild), ...
            0, 0, 0, 0, ...
            7,shared_builds,matrixexp_count,q_adjoint_count,7, ...
            double(zero_state_mass_enabled), ...
            p0_state_cost_prep_s, p0_dynamics_constraint_s, p0_postsolve_s, ...
            p0_b1_robot_dynamics_s, p0_b2_block_torque_s, p0_b3_constraint_assembly_s, ...
            p0_b1a_shared_kinematics_s, p0_b1b_mass_matrix_s, p0_b1c_bias_friction_s],flag,true);
    end
end
