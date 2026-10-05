function [candidate,lower,upper] = truncated_reachable_box_sample(q_i,reach,q_min,q_max,U)
%TRUNCATED_REACHABLE_BOX_SAMPLE Uniform map over reachable/valid intersection.
q_i=q_i(:); reach=reach(:); q_min=q_min(:); q_max=q_max(:); U=U(:);
assert(isequal(size(q_i),size(reach),size(q_min),size(q_max),size(U)), ...
    'shape:trajectory:ProposalShape','Proposal inputs must have identical column shapes.');
assert(all(isfinite([q_i;reach;q_min;q_max;U])) && all(reach>=0) && ...
    all(U>=0 & U<=1),'shape:trajectory:ProposalDomain','Invalid proposal input domain.');
lower=max(q_min,q_i-reach);
upper=min(q_max,q_i+reach);
if any(lower>upper)
    error('shape:trajectory:InvalidReachIntersection', ...
        'Reachable box and valid joint-position box do not intersect.');
end
candidate=lower+U.*(upper-lower);
end
