function tau = inverse_dynamics_kinova_MR(q, dq, ddq_ref, Mlist_nom, Glist_nom, Slist_nom)
    %#codegen
    
    % 1. PRE-ASIGNACIÓN
    tau = zeros(6, 1);
    
    % 2. FORZAR VECTORES COLUMNA
    q = reshape(q, 6, 1);
    dq = reshape(dq, 6, 1);
    ddq_ref = reshape(ddq_ref, 6, 1);
    
    % Constantes físicas
    J_rotors = diag([0.172, 0.172, 0.172, 0.089, 0.089, 0.089]);
    g = [0; 0; -9.80665];
    Ftip = zeros(6, 1); 
    
    % 3. CÁLCULO DE DINÁMICA INVERSA (RNEA)
    tau_geo = InverseDynamics(q, dq, ddq_ref, g, Ftip, Mlist_nom, Glist_nom, Slist_nom);
    
    % 4. COMPENSACIÓN DE FRICCIÓN NOMINAL
    tau_fric = reshape(get_Friction_Nominal(dq, ddq_ref), 6, 1);
    
    % 5. ENSAMBLAJE FINAL
    tau = tau_geo + (J_rotors * ddq_ref) + tau_fric;
end
