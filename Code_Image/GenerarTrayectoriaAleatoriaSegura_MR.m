function [t_traj,q_ref,dq_ref,ddq_ref,tau_ref,metadata] = GenerarTrayectoriaAleatoriaSegura_MR(Mlist_nom,Glist_nom,Slist_nom,target_joint,varargin)
%GENERARTRAYECTORIAALEATORIASEGURA_MR Ratified sequential parent generator.
% One local MT19937 stream is initialized per parent. Every outer attempt
% consumes exactly 6*50*(K+1) uniforms: a q0 candidate block followed by K
% sequential next-waypoint blocks. Mode does not alter RNG consumption.
p=inputParser;
addParameter(p,'Mode','fly'); addParameter(p,'KSegments',2);
addParameter(p,'Seed',20260913); addParameter(p,'Duration',10.0);
addParameter(p,'SampleTime',0.001); addParameter(p,'MaxAttempts',500);
parse(p,varargin{:}); o=p.Results;
mode=lower(string(o.Mode)); K=double(o.KSegments);
assert(any(mode==["fly","stop"]) && any(K==[2 3]));
assert(o.Duration==10.0 && o.SampleTime==0.001 && o.MaxAttempts==500, ...
    'shape:trajectory:FrozenContract','Qualification requires T=10, dt=.001, max_attempts=500.');

stream=RandStream('mt19937ar','Seed',double(o.Seed));
safety=0.85; static_headroom=0.95; proposal_headroom=0.92;
q_min=[-pi;-2.25;-2.58;-pi;-2.10;-pi]*0.9;
q_max=[ pi; 2.25; 2.58; pi; 2.10; pi]*0.9;
tau_limit=[39;39;39;9;9;9]*safety;
dq_limit=[1.3962634016;1.3962634016;1.3962634016;1.2217304764;1.2217304764;1.2217304764]*safety;
ddq_limit=[5.2;5.2;5.2;10;10;10]*safety;
g=[0;0;-9.80665];
t=(0:o.SampleTime:o.Duration); knot_t=linspace(0,o.Duration,K+1);
reason_names={'Q_LIMIT','DQ_LIMIT','DDQ_LIMIT','TORQUE_LIMIT','OBSERVABILITY', ...
    'STATIC_FEASIBILITY','SPLINE_INVALID','NONFINITE','OTHER'};
counts=zeros(size(reason_names)); accepted=false;
t_traj=[]; q_ref=[]; dq_ref=[]; ddq_ref=[]; tau_ref=[];
way=zeros(6,0); vbc=zeros(6,0); abc=zeros(6,0);

for attempt=1:o.MaxAttempts
    % Fixed draw dimensionality makes attempt consumption independent of
    % early rejection and of fly/stop branching.
    U=rand(stream,6,50,K+1);
    way=zeros(6,K+1); q0=[];
    for j=1:50
        cand=q_min+U(:,j,1).*(q_max-q_min);
        tau_static=GravityForces(cand,g,Mlist_nom,Glist_nom,Slist_nom);
        if all(isfinite(tau_static)) && all(abs(tau_static)<=static_headroom*tau_limit)
            q0=cand; break
        end
    end
    if isempty(q0), counts=local_count(counts,reason_names,{'STATIC_FEASIBILITY'}); continue, end
    way(:,1)=q0; seq_ok=true;
    for s=1:K
        dt=knot_t(s+1)-knot_t(s);
        reach=dt*(dq_limit/1.875)*proposal_headroom;
        next=[];
        for j=1:50
            cand=shape.truncated_reachable_box_sample( ...
                way(:,s),reach,q_min,q_max,U(:,j,s+1));
            tau_static=GravityForces(cand,g,Mlist_nom,Glist_nom,Slist_nom);
            if all(isfinite(tau_static)) && all(abs(tau_static)<=static_headroom*tau_limit)
                next=cand; break
            end
        end
        if isempty(next), seq_ok=false; break, end
        way(:,s+1)=next;
    end
    if ~seq_ok, counts=local_count(counts,reason_names,{'STATIC_FEASIBILITY'}); continue, end

    vbc=zeros(6,K+1); abc=zeros(6,K+1);
    if mode=="fly"
        for s=2:K
            tangent=0.5*((way(:,s)-way(:,s-1))/(knot_t(s)-knot_t(s-1)) + ...
                (way(:,s+1)-way(:,s))/(knot_t(s+1)-knot_t(s)));
            vbc(:,s)=max(-0.65*dq_limit,min(0.65*dq_limit,tangent));
        end
    end
    try
        [q,dq,ddq]=quinticpolytraj(way,knot_t,t, ...
            'VelocityBoundaryCondition',vbc,'AccelerationBoundaryCondition',abc);
    catch
        counts=local_count(counts,reason_names,{'SPLINE_INVALID'}); continue
    end

    reasons={};
    if ~isequal(size(q),[6 10001]) || ~isequal(size(dq),[6 10001]) || ~isequal(size(ddq),[6 10001])
        reasons{end+1}='SPLINE_INVALID'; %#ok<AGROW>
    end
    if any(~isfinite(q),'all') || any(~isfinite(dq),'all') || any(~isfinite(ddq),'all')
        reasons{end+1}='NONFINITE'; %#ok<AGROW>
    end
    if any(q<q_min | q>q_max,'all'), reasons{end+1}='Q_LIMIT'; end %#ok<AGROW>
    if any(abs(dq)>dq_limit,'all'), reasons{end+1}='DQ_LIMIT'; end %#ok<AGROW>
    if any(abs(ddq)>ddq_limit,'all'), reasons{end+1}='DDQ_LIMIT'; end %#ok<AGROW>
    L_q2=trapz(t,abs(dq(target_joint,:)));
    if ~isfinite(L_q2) || L_q2<0.8, reasons{end+1}='OBSERVABILITY'; end %#ok<AGROW>
    if ~isempty(reasons), counts=local_count(counts,reason_names,reasons); continue, end

    % Low-cost dynamic rejection precedes, but never replaces, the exact
    % final 1-kHz torque qualification below.
    coarse_idx=unique([1:20:numel(t),numel(t)]); torque_coarse_ok=true;
    for idx=coarse_idx
        tk=inverse_dynamics_kinova_MR(q(:,idx),dq(:,idx),ddq(:,idx),Mlist_nom,Glist_nom,Slist_nom);
        if any(~isfinite(tk)) || any(abs(tk)>tau_limit), torque_coarse_ok=false; break, end
    end
    if ~torque_coarse_ok, counts=local_count(counts,reason_names,{'TORQUE_LIMIT'}); continue, end

    tau=zeros(6,numel(t)); torque_ok=true;
    for idx=1:numel(t)
        tau(:,idx)=inverse_dynamics_kinova_MR(q(:,idx),dq(:,idx),ddq(:,idx),Mlist_nom,Glist_nom,Slist_nom);
        if any(~isfinite(tau(:,idx))) || any(abs(tau(:,idx))>tau_limit)
            torque_ok=false; break
        end
    end
    if ~torque_ok, counts=local_count(counts,reason_names,{'TORQUE_LIMIT'}); continue, end

    accepted=true; t_traj=t'; q_ref=q'; dq_ref=dq'; ddq_ref=ddq'; tau_ref=tau';
    break
end

metadata=struct('qualification_status',string(local_status(accepted)), ...
    'accepted_attempt',double(ternary(accepted,attempt,NaN)), ...
    'attempt_count',double(ternary(accepted,attempt,o.MaxAttempts)), ...
    'failure_counts',cell2struct(num2cell(counts),reason_names,2), ...
    'K_segments',K,'trajectory_mode',mode,'trajectory_seed',double(o.Seed), ...
    'rng_algorithm','MATLAB RandStream mt19937ar','rng_draw_contract','6x50x(K+1) uniforms per attempt; continued parent stream; no mode-dependent draws', ...
    'q_waypoints',ternary(accepted,way,zeros(6,0)),'t_knots',knot_t, ...
    'velocity_boundary_conditions',ternary(accepted,vbc,zeros(6,0)), ...
    'acceleration_boundary_conditions',ternary(accepted,abc,zeros(6,0)), ...
    'limits',struct('q_min',q_min,'q_max',q_max,'dq',dq_limit,'ddq',ddq_limit,'tau',tau_limit), ...
    'static_headroom',static_headroom,'proposal_headroom',proposal_headroom);
if accepted
    metadata.metrics=struct('q_margin_rad',min([q-q_min;q_max-q],[],'all'), ...
        'dq_margin_rad_s',min(dq_limit-max(abs(dq),[],2)), ...
        'ddq_margin_rad_s2',min(ddq_limit-max(abs(ddq),[],2)), ...
        'torque_margin_Nm',min(tau_limit-max(abs(tau),[],2)), ...
        'L_q2_rad',L_q2);
else
    metadata.metrics=struct('q_margin_rad',NaN,'dq_margin_rad_s',NaN, ...
        'ddq_margin_rad_s2',NaN,'torque_margin_Nm',NaN,'L_q2_rad',NaN);
    if nargout<6
        error('shape:trajectory:NoFeasibleTrajectory', ...
            'No feasible %s K=%d trajectory after %d deterministic attempts.',mode,K,o.MaxAttempts);
    end
end
end

function counts=local_count(counts,names,reasons)
for k=1:numel(reasons), counts(strcmp(names,reasons{k}))=counts(strcmp(names,reasons{k}))+1; end
end
function value=ternary(condition,a,b)
if condition, value=a; else, value=b; end
end
function value=local_status(accepted)
if accepted, value='PASS'; else, value='TRAJECTORY_QUALIFICATION_FAIL'; end
end
