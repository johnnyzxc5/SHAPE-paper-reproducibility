function [telemetry,profile] = simulate_run(record,ref,models,cfg)
%SIMULATE_RUN Execute one physical run; E4 never calls this function.
instrument=isfield(cfg,'performance_instrumentation') && cfg.performance_instrumentation;
if instrument, shape.p0_profiler('reset',char(string(record.run_uid))); end
x=tic;
prep=shape.prepare_mpc(ref.t,ref.q,ref.dq,ref.ddq);
prep.P0InstrumentationEnabled=instrument;
prep.P3SharedRNEAEnabled=cfg.mpc_shared_rnea_enabled;
prep.P3SharedRNEAVersion=cfg.mpc_shared_rnea_version;
prep.P4BMassBackend=cfg.mpc_mass_backend;
shape.mpc_runtime_context('clear');
shape.mpc_runtime_context('set',prep);
context_cleanup=onCleanup(@() shape.mpc_runtime_context('clear'));
profile.mpc_prepare_s=toc(x);
fault=shape.build_fault_config(record,cfg);
model='Kinova_Fault_Simulator';
x=tic;
in=Simulink.SimulationInput(model);
if bdIsLoaded(model) && strcmp(get_param(model,'FastRestart'),'on')
    in=in.setModelParameter('StopTime',num2str(cfg.duration_s,17), ...
        'ReturnWorkspaceOutputs','on','SimulationMode','normal');
else
    in=in.setModelParameter('StopTime',num2str(cfg.duration_s,17),'Solver','ode45', ...
        'RelTol',num2str(cfg.solver_rel_tol,17),'AbsTol',num2str(cfg.solver_abs_tol,17), ...
        'MaxStep',local_max_step(cfg), ...
        'ReturnWorkspaceOutputs','on','SimulationMode','normal');
end
vars=struct('q_ref_ts',[ref.t',ref.q'],'dq_ref_ts',[ref.t',ref.dq'], ...
 'ddq_ref_ts',[ref.t',ref.ddq'],'tau_ref_ts',[ref.t',ref.tau_nom'], ...
 'q0',ref.q(:,1),'dq0',ref.dq(:,1),'x0',[ref.q(:,1);ref.dq(:,1)], ...
 'uop',prep.uop,'xop',prep.xop,'yop',prep.yop, ...
 'y_ref',prep.y_ref,'t_ref',prep.t,'yref',prep.y_ref,'tau_ref',ref.tau_nom, ...
 'acc_ref',prep.uop,'Ts',cfg.telemetry_dt_s,'FaultConfig',fault);
fn=fieldnames(models); for k=1:numel(fn), vars.(fn{k})=models.(fn{k}); end
fn=fieldnames(vars); for k=1:numel(fn), in=in.setVariable(fn{k},vars.(fn{k})); end
profile.simulation_input_setup_s=toc(x);
x=tic; out=sim(in); profile.simulink_s=toc(x);
if instrument, profile.p0=shape.p0_profiler('snapshot'); end
profile.logged_output_points=numel(out.tout);
x=tic;
telemetry=shape.resample_telemetry(out.tout,squeeze(out.q_sim),squeeze(out.dq_sim),squeeze(out.tau_sim),cfg);
profile.telemetry_extraction_s=toc(x);
profile.final_output_points=numel(telemetry.q(1,:));
clear context_cleanup
end
function value=local_max_step(cfg)
if isempty(cfg.solver_max_step_s), value='auto';
else, value=num2str(cfg.solver_max_step_s,17); end
end
