function tau_f = get_Friction_Sucia(dq, ddq_desired)
    %#codegen
    % GET_FRICTION_Sucia (Vectorized Version)
    
    % Coefficients (Muraccioli 2025)
    Fv_nom = [2.00; 2.00; 2.00; 1.36; 1.36; 1.36]; 
    Fc_nom = [2.15; 2.15; 2.15; 1.60; 1.60; 1.60];
    
    % UNCERTAINTY INJECTION
    error_Fv = [1.12; 1.05; 1.15; 1.08; 1.10; 1.04]; 
    error_Fc = [1.08; 1.06; 1.10; 1.05; 1.09; 1.03]; 
    
    Fv = Fv_nom .* error_Fv;
    Fc = Fc_nom .* error_Fc;
    Fs = Fc; 
    
    k_vel = 50;  
    k_acc = 50;  
    
    % --- OPERACIONES VECTORIZADAS (Sin bucle for) ---
    
    % 1. Motion & Start-up Factors (Vectores 6x1)
    is_moving = tanh(abs(k_vel * dq)); 
    wants_to_move = tanh(abs(k_acc * ddq_desired));
    
    % 2. Dynamic Model (Vector 6x1)
    tau_dynamic = Fv .* dq + Fc .* tanh(k_vel * dq);
    
    % 3. Static Model (Vector 6x1)
    tau_static = Fs .* tanh(k_acc * ddq_desired);
    
    % 4. Smooth Blending
    tau_f = is_moving .* tau_dynamic + (1 - is_moving) .* wants_to_move .* tau_static;
end