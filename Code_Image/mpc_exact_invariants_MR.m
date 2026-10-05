function [z,meta] = mpc_exact_invariants_MR(action,A,B,C,Ts,f,v,Np,Nc)
%MPC_EXACT_INVARIANTS_MR Exact cache for MPC model/horizon invariants.
% The build order intentionally matches solve_flatness_mpc_step_MR GOLD.
%#codegen
persistent cache signature hits misses rebuilds invalidations
if isempty(hits)
    cache=cell(Np,Nc); signature=local_key(A,B,C,Ts,Np,Nc);
    hits=uint64(0); misses=uint64(0); rebuilds=uint64(0); invalidations=uint64(0);
end
if strcmp(action,'reset')
    cache=cell(Np,Nc); signature=local_key(A,B,C,Ts,Np,Nc);
    hits=uint64(0); misses=uint64(0); rebuilds=uint64(0); invalidations=uint64(0);
    z=local_build(A,B,C,Ts,f,v,Np,Nc);
    meta=local_meta(false,true,true,false,hits,misses,rebuilds,invalidations);
    return
end
if strcmp(action,'recompute')
    z=local_build(A,B,C,Ts,f,v,Np,Nc);
    meta=local_meta(false,true,true,false,hits,misses,rebuilds,invalidations);
    return
end
assert(strcmp(action,'get'),'shape:mpc:CacheAction');
key=local_key(A,B,C,Ts,Np,Nc); invalidated=false;
if ~isequal(signature,key)
    cache=cell(Np,Nc); signature=key; invalidations=invalidations+1;
    invalidated=true;
end
if isempty(cache{f,v})
    cache{f,v}=local_build(A,B,C,Ts,f,v,Np,Nc);
    misses=misses+1; rebuilds=rebuilds+1;
    z=cache{f,v};
    meta=local_meta(false,true,true,invalidated,hits,misses,rebuilds,invalidations);
else
    hits=hits+1; z=cache{f,v};
    meta=local_meta(true,false,false,invalidated,hits,misses,rebuilds,invalidations);
end
end

function key=local_key(A,B,C,Ts,Np,Nc)
key=struct('A',A,'B',B,'C',C,'Ts',Ts,'Np',Np,'Nc',Nc, ...
    'nu',6,'ny',6,'Q0F',1e-1,'QkF',5e-1,'R_F',1e-3, ...
    'position_weight',20,'tau_max',[39;39;39;9;9;9], ...
    'q_lim',[pi;deg2rad(128.9);deg2rad(147.8);pi;deg2rad(120.3);pi], ...
    'dq_lim',[1.39;1.39;1.39;1.22;1.22;1.22], ...
    'acc_lim',[5.2;5.2;5.2;10;10;10]);
end

function z=local_build(A,B,C,Ts,f,v,Np,Nc)
nu=6; ny=6;
[O_full,M_full]=local_build_lifted_LTI(A,B,C,f,v,Np,Nc);
z.O=O_full(1:f*ny,:);
z.M_lift=M_full(1:f*ny,1:v*nu);
z.W4=kron(eye(f),diag(20*ones(ny,1)));
D_op=local_diff_operator(v,nu);
W3_blk=eye(v*nu)*5e-1;
W3_blk(1:nu,1:nu)=eye(nu)*1e-1;
z.W3=(D_op'*W3_blk*D_op)+eye(v*nu)*1e-3;
z.H_B=2*(z.M_lift'*(z.W4*z.M_lift)+z.W3);
z.H_B=0.5*(z.H_B+z.H_B');
z.A_y=[z.M_lift;-z.M_lift];
z.qmax_flat=repmat([pi;deg2rad(128.9);deg2rad(147.8);pi;deg2rad(120.3);pi],f,1);
if f>=2
    z.D1=local_build_D1(f,ny)/Ts;
    z.A_v=[z.D1*z.M_lift;-z.D1*z.M_lift];
    z.qd_max=repmat([1.39;1.39;1.39;1.22;1.22;1.22],f-1,1);
else
    z.D1=zeros(0,f*ny); z.A_v=zeros(0,v*nu); z.qd_max=zeros(0,1);
end
z.tau_lim=repmat([39;39;39;9;9;9],v,1);
z.v_max_vec=repmat([5.2;5.2;5.2;10;10;10],v,1);
z.v_min_vec=-z.v_max_vec;
z.x0=zeros(v*nu,1);
end

function meta=local_meta(hit,miss,rebuild,invalidation,hits,misses,rebuilds,invalidations)
meta=struct('cache_version','p2-exact-invariants-v1','hit',hit,'miss',miss, ...
    'rebuild',rebuild,'invalidation',invalidation,'total_hits',hits, ...
    'total_misses',misses,'total_rebuilds',rebuilds,'total_invalidations',invalidations);
end

function [O,M]=local_build_lifted_LTI(A,B,C,f,v,Np,Nc)
nx=12; nu=6; r=6; O=zeros(Np*r,nx); M=zeros(Np*r,Nc*nu); Ap=A;
for i=1:f
    if i==1, O(1:r,:)=C*A;
    else, Ap=Ap*A; O((i-1)*r+1:i*r,:)=C*Ap; end
end
for i=1:f
    if i<=v
        Ap=eye(nx);
        for j=0:i-1
            if j>0, Ap=Ap*A; end
            M((i-1)*r+1:i*r,(i-j-1)*nu+1:(i-j)*nu)=C*(Ap*B);
        end
    else
        S=zeros(nx); Ap=eye(nx);
        for s=0:(i-v)
            if s>0, Ap=Ap*A; end
            S=S+Ap;
        end
        M((i-1)*r+1:i*r,(v-1)*nu+1:v*nu)=C*(S*B);
        Ap=A;
        for j=1:v-1
            M((i-1)*r+1:i*r,(v-1-j)*nu+1:(v-j)*nu)=C*(Ap*B);
            Ap=Ap*A;
        end
    end
end
end

function W1=local_diff_operator(v,m)
W1=zeros(v*m,v*m);
for i=1:v
    rr=(i-1)*m+(1:m); W1(rr,rr)=eye(m);
    if i>1, cc=(i-2)*m+(1:m); W1(rr,cc)=-eye(m); end
end
end

function D1=local_build_D1(Np,ny)
D1=zeros((Np-1)*ny,Np*ny);
for i=1:Np-1
    r=(i-1)*ny+(1:ny);
    D1(r,(i-1)*ny+(1:ny))=-eye(ny);
    D1(r,i*ny+(1:ny))=eye(ny);
end
end
