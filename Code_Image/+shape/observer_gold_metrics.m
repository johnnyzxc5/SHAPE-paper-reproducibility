function metrics = observer_gold_metrics(candidate,gold)
%OBSERVER_GOLD_METRICS Pilot GATE-03 metrics; no GOLD means PILOT_PENDING.
if nargin<2 || isempty(gold)
    metrics=struct('state','PILOT_PENDING','gmo_rmse_Nm',NaN,'gmo_correlation',NaN, ...
        'eo_rmse_W',NaN,'eo_correlation',NaN,'gmo_pass',false,'eo_pass',false);
    return
end
[gmo_rmse,gmo_corr]=local_metrics(double(candidate.gmo),double(gold.gmo));
joint_rmse=zeros(6,1); joint_corr=zeros(6,1);
for j=1:6
    [joint_rmse(j),joint_corr(j)]=local_metrics(double(candidate.gmo(j,:)),double(gold.gmo(j,:)));
end
[eo_rmse,eo_corr]=local_metrics(double(candidate.energy),double(gold.energy));
metrics=struct('state','PILOT_MEASURED','gmo_rmse_Nm',gmo_rmse, ...
    'gmo_correlation',gmo_corr,'gmo_rmse_by_joint_Nm',joint_rmse, ...
    'gmo_correlation_by_joint',joint_corr,'eo_rmse_W',eo_rmse,'eo_correlation',eo_corr, ...
    'gmo_pass',gmo_rmse<=.020 && gmo_corr>=.995 && all(joint_rmse<=.020) && all(joint_corr>=.995), ...
    'eo_pass',eo_rmse<=.010 && eo_corr>=.999);
end
function [rmse,corr_value]=local_metrics(a,b)
assert(isequal(size(a),size(b)));
d=a(:)-b(:); rmse=sqrt(mean(d.^2));
if std(a(:))==0 || std(b(:))==0, corr_value=double(isequal(a,b));
else, R=corrcoef(a(:),b(:)); corr_value=R(1,2); end
end
