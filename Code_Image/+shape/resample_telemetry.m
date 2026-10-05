function telemetry = resample_telemetry(t,q,dq,tau,cfg)
%RESAMPLE_TELEMETRY PCHIP continuous output to the canonical 1-ms grid.
t=double(t(:)'); [t,idx]=unique(t,'stable'); q=local_orient(q,idx); dq=local_orient(dq,idx); tau=local_orient(tau,idx);
target=linspace(0,cfg.duration_s,cfg.n_time);
telemetry=struct('t',target,'q',interp1(t,q',target,'pchip')', ...
 'dq',interp1(t,dq',target,'pchip')','tau_cmd',interp1(t,tau',target,'pchip')');
assert(all(isfinite([telemetry.q(:);telemetry.dq(:);telemetry.tau_cmd(:)])));
end
function x=local_orient(x,idx)
x=squeeze(x); if size(x,1)~=6, x=x'; end; x=x(:,idx);
end
