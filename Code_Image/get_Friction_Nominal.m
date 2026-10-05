function tau_f = get_Friction_Nominal(dq, ddq_desired)
    %#codegen
    % GET_FRICTION_Nominal (Vectorized Version)
    % Removes hard IF statements to prevent failures in ODE15s (stiff solvers).
    % Uses tanh to smooth all transitions.
    
    % Coefficients (Muraccioli 2025)
    Fv = [2.00; 2.00; 2.00; 1.36; 1.36; 1.36]; 
    Fc = [2.15; 2.15; 2.15; 1.60; 1.60; 1.60];
    Fs = Fc; 
    
    % Smoothing parameters
    k_vel = 50;  % Slope for motion detection
    k_acc = 50;  % Slope for start-up intention detection
    
    % --- OPERACIONES VECTORIZADAS ---
    
    % 1. Motion & Start-up Factors (Vectores 6x1)
    is_moving = tanh(abs(k_vel * dq)); 
    wants_to_move = tanh(abs(k_acc * ddq_desired));
    
    % 2. Dynamic Model
    tau_dynamic = Fv .* dq + Fc .* tanh(k_vel * dq);
    
    % 3. Static Model
    tau_static = Fs .* tanh(k_acc * ddq_desired);
    
    % 4. Smooth Blending
    tau_f = is_moving .* tau_dynamic + (1 - is_moving) .* wants_to_move .* tau_static;
end