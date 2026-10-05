function kin=rnea_shared_kinematics_MR(thetalist,Mlist,Slist,mode)
%RNEA_SHARED_KINEMATICS_MR Exact common kinematics from InverseDynamics.
% Supports 'cached' (default, exact invariant-hoisting and state-key caching) and 'legacy' modes.
persistent cached_Mlist cached_Slist cached_n cached_Ai cached_invM cached_AdTi_end
persistent cached_q_u64 cached_kin
persistent stats_calls stats_hits stats_misses stats_rebuilds

if isempty(stats_calls)
    stats_calls = uint64(0);
    stats_hits = uint64(0);
    stats_misses = uint64(0);
    stats_rebuilds = uint64(0);
end

if nargin >= 4 && strcmp(mode, 'reset')
    cached_Mlist = []; cached_Slist = []; cached_n = [];
    cached_Ai = []; cached_invM = []; cached_AdTi_end = [];
    cached_q_u64 = []; cached_kin = [];
    stats_calls = uint64(0); stats_hits = uint64(0);
    stats_misses = uint64(0); stats_rebuilds = uint64(0);
    kin = struct('Ai', zeros(6, 0), 'AdTi', zeros(6, 6, 0), 'n', 0);
    return;
end

if nargin >= 4 && strcmp(mode, 'stats')
    kin = struct('calls', stats_calls, 'hits', stats_hits, ...
                 'misses', stats_misses, 'rebuilds', stats_rebuilds);
    return;
end

n = size(thetalist, 1);

if nargin >= 4 && strcmp(mode, 'legacy')
    Mi = eye(4); Ai = zeros(6, n); AdTi = zeros(6, 6, n+1);
    AdTi(:,:,n+1) = Adjoint(TransInv(Mlist(:,:,n+1)));
    for i = 1:n
        Mi = Mi * Mlist(:,:,i);
        Ai(:,i) = Adjoint(TransInv(Mi)) * Slist(:,i);
        AdTi(:,:,i) = Adjoint(MatrixExp6(VecTose3(Ai(:,i) * -thetalist(i))) ...
            * TransInv(Mlist(:,:,i)));
    end
    kin = struct('Ai', Ai, 'AdTi', AdTi, 'n', n);
    return;
end

stats_calls = stats_calls + 1;

% CACHED PATH: Exact Invariant Hoisting with Safe Cache Invalidation
need_rebuild = isempty(cached_Mlist) || isempty(cached_Slist) || ...
    ~isequal(size(cached_Mlist), size(Mlist)) || ...
    ~isequal(size(cached_Slist), size(Slist)) || ...
    ~strcmp(class(cached_Mlist), class(Mlist)) || ...
    ~strcmp(class(cached_Slist), class(Slist)) || ...
    ~isequal(cached_Mlist, Mlist) || ...
    ~isequal(cached_Slist, Slist);

if need_rebuild
    cached_n = n;
    cached_Mlist = Mlist;
    cached_Slist = Slist;
    Mi = eye(4);
    cached_Ai = zeros(6, n);
    cached_invM = zeros(4, 4, n);
    for i = 1:n
        Mi = Mi * Mlist(:,:,i);
        cached_Ai(:,i) = Adjoint(TransInv(Mi)) * Slist(:,i);
        cached_invM(:,:,i) = TransInv(Mlist(:,:,i));
    end
    cached_AdTi_end = Adjoint(TransInv(Mlist(:,:,n+1)));
    cached_q_u64 = [];
    cached_kin = [];
    stats_rebuilds = stats_rebuilds + 1;
end

% STATE CACHE LOOKUP: exact raw bitwise uint64 comparison
if ~need_rebuild && ~isempty(cached_q_u64) && isa(thetalist, 'double') && ...
        isequal(size(thetalist), [cached_n, 1])
    q_u64 = typecast(thetalist, 'uint64');
    if all(cached_q_u64 == q_u64)
        stats_hits = stats_hits + 1;
        kin = cached_kin;
        return;
    end
end

stats_misses = stats_misses + 1;

AdTi = zeros(6, 6, n+1);
AdTi(:,:,n+1) = cached_AdTi_end;
for i = 1:n
    AdTi(:,:,i) = Adjoint(MatrixExp6(VecTose3(cached_Ai(:,i) * -thetalist(i))) ...
        * cached_invM(:,:,i));
end
kin = struct('Ai', cached_Ai, 'AdTi', AdTi, 'n', n);

if isa(thetalist, 'double') && isequal(size(thetalist), [n, 1])
    cached_q_u64 = typecast(thetalist, 'uint64');
    cached_kin = kin;
else
    cached_q_u64 = [];
    cached_kin = [];
end
end
