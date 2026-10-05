function out=p0_profiler(action,varargin)
%P0_PROFILER In-memory, disableable P0 counters emitted once per run.
persistent state
if isempty(state), state=local_empty(''); end
switch lower(char(action))
    case 'reset'
        state=local_empty(char(varargin{1}));
        state.enabled = true;
        out=[];
    case 'disable'
        state.enabled = false;
        out=[];
    case 'enable'
        state.enabled = true;
        out=[];
    case 'mpc'
        if ~state.enabled, out=[]; return; end
        v=double(varargin{1}); flag=double(varargin{2}); qp_called=logical(varargin{3});
        state.controller_entries=state.controller_entries+1;
        state.mpc_entries=state.mpc_entries+1;
        state.mpc_total_s=state.mpc_total_s+v(1);
        state.mpc_reference_build_s=state.mpc_reference_build_s+v(2);
        state.mpc_prediction_build_s=state.mpc_prediction_build_s+v(3);
        state.mpc_cost_build_s=state.mpc_cost_build_s+v(4);
        state.mpc_mass_matrix_s=state.mpc_mass_matrix_s+v(5);
        state.mpc_inverse_dynamics_s=state.mpc_inverse_dynamics_s+v(6);
        state.mpc_friction_s=state.mpc_friction_s+v(7);
        state.mpc_constraint_build_s=state.mpc_constraint_build_s+v(8);
        state.mpc_bounds_build_s=state.mpc_bounds_build_s+v(9);
        state.mpc_cache_hits=state.mpc_cache_hits+uint64(v(11));
        state.mpc_cache_misses=state.mpc_cache_misses+uint64(v(12));
        state.mpc_cache_rebuilds=state.mpc_cache_rebuilds+uint64(v(13));
        state.mpc_shared_kinematics_s=state.mpc_shared_kinematics_s+v(14);
        state.mpc_mass_recursion_s=state.mpc_mass_recursion_s+v(15);
        state.mpc_bias_recursion_s=state.mpc_bias_recursion_s+v(16);
        state.mpc_dynamics_misc_s=state.mpc_dynamics_misc_s+v(17);
        state.mpc_rnea_equivalent_evaluations=state.mpc_rnea_equivalent_evaluations+uint64(v(18));
        state.mpc_shared_kinematics_builds=state.mpc_shared_kinematics_builds+uint64(v(19));
        state.mpc_matrixexp6_evaluations=state.mpc_matrixexp6_evaluations+uint64(v(20));
        state.mpc_q_dependent_adjoint_builds=state.mpc_q_dependent_adjoint_builds+uint64(v(21));
        state.mpc_baseline_effective_kinematics_builds= ...
            state.mpc_baseline_effective_kinematics_builds+uint64(v(22));
        if numel(v)>=23
            state.mpc_zero_state_mass_calls=state.mpc_zero_state_mass_calls+uint64(v(23));
        end
        if numel(v)>=26
            state.mpc_state_cost_prep_s = state.mpc_state_cost_prep_s + v(24);
            state.mpc_dynamics_constraint_s = state.mpc_dynamics_constraint_s + v(25);
            state.mpc_postsolve_s = state.mpc_postsolve_s + v(26);
        else
            % Fallback for legacy test callers passing 22-23 elements
            state.mpc_state_cost_prep_s = state.mpc_state_cost_prep_s + v(2) + v(3) + v(4);
            state.mpc_dynamics_constraint_s = state.mpc_dynamics_constraint_s + v(5) + v(6) + v(7) + v(8) + v(9);
            state.mpc_postsolve_s = state.mpc_postsolve_s + max(0, v(1) - (v(2)+v(3)+v(4)+v(5)+v(6)+v(7)+v(8)+v(9)+v(10)));
        end
        if numel(v)>=29
            state.mpc_b1_robot_dynamics_s = state.mpc_b1_robot_dynamics_s + v(27);
            state.mpc_b2_block_torque_s = state.mpc_b2_block_torque_s + v(28);
            state.mpc_b3_constraint_assembly_s = state.mpc_b3_constraint_assembly_s + v(29);
        end
        if numel(v)>=32
            state.mpc_b1a_shared_kinematics_s = state.mpc_b1a_shared_kinematics_s + v(30);
            state.mpc_b1b_mass_matrix_s = state.mpc_b1b_mass_matrix_s + v(31);
            state.mpc_b1c_bias_friction_s = state.mpc_b1c_bias_friction_s + v(32);
        end
        % Legacy aggregate names remain for prior readers.
        state.mpc_state_reference_s=state.mpc_state_reference_s+v(2);
        state.mpc_matrix_s=state.mpc_matrix_s+v(3)+v(4);
        state.mpc_constraint_s=state.mpc_constraint_s+v(8)+v(9);
        if qp_called
            state.quadprog_calls=state.quadprog_calls+1;
            state.controller_mass_matrix_calls=state.controller_mass_matrix_calls+1;
            state.controller_inverse_dynamics_calls=state.controller_inverse_dynamics_calls+1;
            state.physical_mass_matrix_calls=state.physical_mass_matrix_calls+1;
            state.physical_inverse_dynamics_calls=state.physical_inverse_dynamics_calls+1;
            state.quadprog_total_s=state.quadprog_total_s+v(10);
            state.qp_times(state.quadprog_calls)=v(10);
            state.qp_flags(state.quadprog_calls)=flag;
        end
        out=[];
    case 'plant'
        if ~state.enabled, out=[]; return; end
        v=double(varargin{1});
        state.plant_rhs_entries=state.plant_rhs_entries+1;
        state.kinova_entries=state.kinova_entries+1;
        state.physical_inverse_dynamics_calls=state.physical_inverse_dynamics_calls+1;
        state.physical_mass_matrix_calls=state.physical_mass_matrix_calls+1;
        state.plant_inverse_dynamics_calls=state.plant_inverse_dynamics_calls+1;
        state.plant_mass_matrix_calls=state.plant_mass_matrix_calls+1;
        state.plant_total_s=state.plant_total_s+v(1);
        state.plant_fault_s=state.plant_fault_s+v(2);
        state.plant_friction_s=state.plant_friction_s+v(3);
        state.plant_inverse_dynamics_s=state.plant_inverse_dynamics_s+v(4);
        state.plant_mass_matrix_s=state.plant_mass_matrix_s+v(5);
        state.plant_linear_solve_s=state.plant_linear_solve_s+v(6);
        out=[];
    case 'ct'
        if ~state.enabled, out=[]; return; end
        dt=double(varargin{1});
        state.computed_torque_entries=state.computed_torque_entries+1;
        state.computed_torque_total_s=state.computed_torque_total_s+dt;
        out=[];
    case 'snapshot'
        out=state;
        n=state.quadprog_calls;
        if n>0
            q=state.qp_times(1:n); f=state.qp_flags(1:n);
            out.quadprog_mean_s=mean(q); out.quadprog_median_s=median(q); out.quadprog_max_s=max(q);
            out.quadprog_successes=sum(f>0); out.quadprog_fallbacks=sum(f<=0);
            [flags,~,ix]=unique(f); out.exitflag_values=flags; out.exitflag_counts=accumarray(ix(:),1);
        else
            out.quadprog_mean_s=NaN; out.quadprog_median_s=NaN; out.quadprog_max_s=NaN;
            out.quadprog_successes=0; out.quadprog_fallbacks=0;
            out.exitflag_values=[]; out.exitflag_counts=[];
        end
        out.mpc_non_qp_s=out.mpc_total_s-out.quadprog_total_s;
        out.mpc_dynamics_build_s=out.mpc_mass_matrix_s+out.mpc_inverse_dynamics_s+ ...
            out.mpc_friction_s;
        explained=out.mpc_reference_build_s+out.mpc_prediction_build_s+ ...
            out.mpc_cost_build_s+out.mpc_mass_matrix_s+out.mpc_inverse_dynamics_s+ ...
            out.mpc_friction_s+out.mpc_constraint_build_s+out.mpc_bounds_build_s+ ...
            out.quadprog_total_s;
        out.mpc_allocation_misc_s=max(0,out.mpc_total_s-explained);
        out.mpc_bucket_sum_s=out.mpc_state_cost_prep_s+out.mpc_dynamics_constraint_s+ ...
            out.quadprog_total_s+out.mpc_postsolve_s;
        out.mpc_reconciliation_error_s=out.mpc_total_s-out.mpc_bucket_sum_s;
        out.mpc_cache_version='p2-exact-invariants-v1';
        out.plant_other_s=out.plant_total_s-(out.plant_fault_s+out.plant_friction_s+ ...
            out.plant_inverse_dynamics_s+out.plant_mass_matrix_s+out.plant_linear_solve_s);
        if state.computed_torque_entries > 0
            out.computed_torque_mean_s = state.computed_torque_total_s / double(state.computed_torque_entries);
        else
            out.computed_torque_mean_s = 0;
        end
        out.mpc_b1_robot_dynamics_s = state.mpc_b1_robot_dynamics_s;
        out.mpc_b2_block_torque_s = state.mpc_b2_block_torque_s;
        out.mpc_b3_constraint_assembly_s = state.mpc_b3_constraint_assembly_s;
        out.mpc_b123_sum_s = state.mpc_b1_robot_dynamics_s + state.mpc_b2_block_torque_s + state.mpc_b3_constraint_assembly_s;
        out.mpc_b123_reconciliation_error_s = state.mpc_dynamics_constraint_s - out.mpc_b123_sum_s;
        out.mpc_b1a_shared_kinematics_s = state.mpc_b1a_shared_kinematics_s;
        out.mpc_b1b_mass_matrix_s = state.mpc_b1b_mass_matrix_s;
        out.mpc_b1c_bias_friction_s = state.mpc_b1c_bias_friction_s;
        out.mpc_b1abc_sum_s = state.mpc_b1a_shared_kinematics_s + state.mpc_b1b_mass_matrix_s + state.mpc_b1c_bias_friction_s;
        out.mpc_b1abc_reconciliation_error_s = state.mpc_b1_robot_dynamics_s - out.mpc_b1abc_sum_s;
        out=rmfield(out,{'qp_times','qp_flags'});
    otherwise
        error('shape:p0:ProfilerAction','Unknown P0 profiler action %s.',action);
end
end
function s=local_empty(uid)
s=struct('run_uid',uid,'enabled',~isempty(uid),'controller_entries',0,'mpc_entries',0,'quadprog_calls',0, ...
    'plant_rhs_entries',0,'kinova_entries',0,'physical_inverse_dynamics_calls',0, ...
    'physical_mass_matrix_calls',0,'controller_inverse_dynamics_calls',0, ...
    'controller_mass_matrix_calls',0,'plant_inverse_dynamics_calls',0, ...
    'plant_mass_matrix_calls',0,'computed_torque_entries',0,'computed_torque_total_s',0, ...
    'mpc_total_s',0,'mpc_state_reference_s',0, ...
    'mpc_matrix_s',0,'mpc_mass_matrix_s',0,'mpc_inverse_dynamics_s',0, ...
    'mpc_friction_s',0,'mpc_constraint_s',0,'mpc_reference_build_s',0, ...
    'mpc_prediction_build_s',0,'mpc_cost_build_s',0,'mpc_constraint_build_s',0, ...
    'mpc_bounds_build_s',0,'mpc_state_cost_prep_s',0,'mpc_dynamics_constraint_s',0, ...
    'mpc_b1_robot_dynamics_s',0,'mpc_b2_block_torque_s',0,'mpc_b3_constraint_assembly_s',0, ...
    'mpc_b1a_shared_kinematics_s',0,'mpc_b1b_mass_matrix_s',0,'mpc_b1c_bias_friction_s',0, ...
    'mpc_postsolve_s',0,'mpc_cache_hits',uint64(0),'mpc_cache_misses',uint64(0), ...
    'mpc_cache_rebuilds',uint64(0),'mpc_shared_kinematics_s',0, ...
    'mpc_mass_recursion_s',0,'mpc_bias_recursion_s',0,'mpc_dynamics_misc_s',0, ...
    'mpc_rnea_equivalent_evaluations',uint64(0), ...
    'mpc_shared_kinematics_builds',uint64(0),'mpc_matrixexp6_evaluations',uint64(0), ...
    'mpc_q_dependent_adjoint_builds',uint64(0), ...
    'mpc_baseline_effective_kinematics_builds',uint64(0), ...
    'mpc_zero_state_mass_calls',uint64(0),'quadprog_total_s',0, ...
    'plant_total_s',0,'plant_fault_s',0,'plant_friction_s',0, ...
    'plant_inverse_dynamics_s',0,'plant_mass_matrix_s',0,'plant_linear_solve_s',0, ...
    'qp_times',zeros(1,200000),'qp_flags',zeros(1,200000));
end
