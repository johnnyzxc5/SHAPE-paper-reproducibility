function [ctdq,diagnostics] = coriolis_transpose_velocity(q,dq,models)
%CORIOLIS_TRANSPOSE_VELOCITY Evaluate C(q,dq)'*dq via dT/dq.
% For the Christoffel convention used by the authority,
% C(q,dq)'*dq = gradient_q(0.5*dq'*M(q)*dq).
h=1e-6; ctdq=zeros(6,1);
mass_matrix_calls=0;
for j=1:6
    qp=q; qm=q; qp(j)=qp(j)+h; qm(j)=qm(j)-h;
    Mp=MassMatrix(qp,models.Mlist_nom,models.Glist_nom,models.Slist_nom);
    Mm=MassMatrix(qm,models.Mlist_nom,models.Glist_nom,models.Slist_nom);
    mass_matrix_calls=mass_matrix_calls+2;
    ctdq(j)=(0.5*dq'*Mp*dq-0.5*dq'*Mm*dq)/(2*h);
end
if nargout>1, diagnostics=struct('mass_matrix_calls',mass_matrix_calls); end
end
