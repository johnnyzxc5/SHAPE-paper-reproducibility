function v_total=solve_flatness_mpc_runtime_MR(q_curr,dq_curr,t,Mlist_nom,Glist_nom,Slist_nom)
%SOLVE_FLATNESS_MPC_RUNTIME_MR Numeric-boundary wrapper for Stateflow.
prep=shape.mpc_runtime_context('get');
v_total=solve_flatness_mpc_step_MR(q_curr,dq_curr,t,prep, ...
    Mlist_nom,Glist_nom,Slist_nom);
end
