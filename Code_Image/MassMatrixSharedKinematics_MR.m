function M=MassMatrixSharedKinematics_MR(Glist,kin)
%MASSMATRIXSHAREDKINEMATICS_MR Baseline six RNEA columns with one kinematics build.
n=kin.n; M=zeros(n);
for i=1:n
    ddthetalist=zeros(n,1); ddthetalist(i)=1;
    M(:,i)=InverseDynamicsSharedKinematics_MR(zeros(n,1),ddthetalist, ...
        [0;0;0],[0;0;0;0;0;0],Glist,kin);
end
end
