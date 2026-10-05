function M=MassMatrixZeroStateSharedKinematics_MR(Glist,kin)
%MASSMATRIXZEROSTATESHAREDKINEMATICS_MR Experimental zero-state P3 mass path.
% Zero-state forward recursion prunes structurally zero pre-j propagation.
% Backward recursion ordering is preserved.
n=kin.n; Ai=kin.Ai; AdTi=kin.AdTi; M=zeros(n);

for j=1:n
    Vdi=zeros(6,n+1);
    Vdi(4:6,1)=-[0;0;0];

    Fi=zeros(6,1);
    col=zeros(n,1);

    Vdi(:,j+1)=Ai(:,j);

    for i=j+1:n
        Vdi(:,i+1)=AdTi(:,:,i)*Vdi(:,i);
    end

    for i=n:-1:1
        Fi=AdTi(:,:,i+1)'*Fi+Glist(:,:,i)*Vdi(:,i+1);
        col(i)=Fi'*Ai(:,i);
    end

    M(:,j)=col;
end
end
