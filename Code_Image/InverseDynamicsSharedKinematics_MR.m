function taulist=InverseDynamicsSharedKinematics_MR(dthetalist,ddthetalist,g,Ftip,Glist,kin)
%INVERSEDYNAMICSSHAREDKINEMATICS_MR Qualified RNEA with direct exact ad(V) construction.
n=kin.n; Ai=kin.Ai; AdTi=kin.AdTi;
Vi=zeros(6,n+1); Vdi=zeros(6,n+1); Vdi(4:6,1)=-g;
Fi=Ftip; taulist=zeros(n,1);
for i=1:n
    Vi(:,i+1)=AdTi(:,:,i)*Vi(:,i)+Ai(:,i)*dthetalist(i);
    ad_V = local_ad_direct(Vi(:,i+1));
    Vdi(:,i+1)=AdTi(:,:,i)*Vdi(:,i)+Ai(:,i)*ddthetalist(i) ...
        +ad_V*Ai(:,i)*dthetalist(i);
end
for i=n:-1:1
    ad_V = local_ad_direct(Vi(:,i+1));
    Fi=AdTi(:,:,i+1)'*Fi+Glist(:,:,i)*Vdi(:,i+1) ...
        -ad_V'*(Glist(:,:,i)*Vi(:,i+1));
    taulist(i)=Fi'*Ai(:,i);
end
end

function adV = local_ad_direct(V)
adV = [   0, -V(3),  V(2),    0,     0,     0; ...
       V(3),     0, -V(1),    0,     0,     0; ...
      -V(2),  V(1),     0,    0,     0,     0; ...
          0, -V(6),  V(5),    0, -V(3),  V(2); ...
       V(6),     0, -V(4), V(3),     0, -V(1); ...
      -V(5),  V(4),     0,-V(2),  V(1),     0];
end
