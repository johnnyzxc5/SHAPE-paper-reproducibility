function ctdq = ctdq_finite_difference_batch_mex_source(q,dq,Mlist,Glist,Slist)
%CTDQ_FINITE_DIFFERENCE_BATCH_MEX_SOURCE Codegen source for batched GOLD.
% This intentionally preserves the same h, perturbations, MassMatrix calls,
% scalar kinetic-energy expressions and evaluation order as the MATLAB GOLD.
h=1e-6;
ctdq=zeros(6,size(q,2));
for k=1:size(q,2)
    qk=q(:,k); dqk=dq(:,k);
    for j=1:6
        qp=qk; qm=qk; qp(j)=qp(j)+h; qm(j)=qm(j)-h;
        Mp=MassMatrix(qp,Mlist,Glist,Slist);
        Mm=MassMatrix(qm,Mlist,Glist,Slist);
        ctdq(j,k)=(0.5*dqk'*Mp*dqk-0.5*dqk'*Mm*dqk)/(2*h);
    end
end
end
