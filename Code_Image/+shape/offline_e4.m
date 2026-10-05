function views = offline_e4(clean,ref,models,cfg,noise_seed,calibration)
%OFFLINE_E4 Deterministic diagnostic-only sensor perturbations (10 conditions).
if nargin<6 || isempty(calibration), calibration=cfg.e4_calibration; end
local_validate_calibration(calibration);
conditions=struct('name',{},'velocity_snr_db',{},'position_sigma_deg',{});
for x=cfg.e4_velocity_snr_db
    conditions(end+1)=struct('name',sprintf('velocity_%gdB',x),'velocity_snr_db',x,'position_sigma_deg',0); %#ok<AGROW>
end
for x=cfg.e4_position_sigma_deg
    conditions(end+1)=struct('name',sprintf('position_%gdeg',x),'velocity_snr_db',Inf,'position_sigma_deg',x); %#ok<AGROW>
end
for x=cfg.e4_position_sigma_deg
    conditions(end+1)=struct('name',sprintf('combined_40dB_%gdeg',x),'velocity_snr_db',40,'position_sigma_deg',x); %#ok<AGROW>
end
views=cell(1,numel(conditions));
pool=gcp('nocreate');
if ~isempty(pool) && pool.NumWorkers>1
parfor k=1:numel(conditions)
    views{k}=local_view(clean,ref,models,cfg,noise_seed,calibration,conditions(k),k);
end
else
for k=1:numel(conditions)
    views{k}=local_view(clean,ref,models,cfg,noise_seed,calibration,conditions(k),k);
end
end
end
function view=local_view(clean,ref,models,cfg,noise_seed,calibration,condition,k)
    s=RandStream('mt19937ar','Seed',mod(double(noise_seed)+104729*k,2^32-1));
    qnoise=deg2rad(condition.position_sigma_deg)*randn(s,size(clean.q));
    dqnoise=zeros(size(clean.dq));
    if isfinite(condition.velocity_snr_db)
        scale=double(calibration.pooled_velocity_rms(:))./ ...
            10.^(condition.velocity_snr_db/20);
        dqnoise=scale.*randn(s,size(clean.dq));
    end
    noisy=clean; noisy.q=clean.q+qnoise; noisy.dq=clean.dq+dqnoise;
    [res,~]=shape.compute_residuals(noisy,ref,models,cfg);
    view=struct('condition',condition,'q_noise',single(qnoise), ...
        'dq_noise',single(dqnoise),'residuals',res, ...
        'normalized',shape.normalize_residuals(res,cfg), ...
        'calibration_provenance',calibration);
end
function local_validate_calibration(c)
assert(isstruct(c) && isfield(c,'state') && isfield(c,'pooled_velocity_rms') && isfield(c,'source'), ...
    'shape:e4:CalibrationRequired','Explicit pooled calibration and provenance are required.');
assert(any(strcmp(c.state,{'CALIBRATION_CANDIDATE','PRODUCTION_E4_CALIBRATION_FROZEN'})), ...
    'shape:e4:CalibrationState','Calibration must be candidate or frozen.');
assert(isequal(size(c.pooled_velocity_rms(:)),[6 1]) && all(isfinite(c.pooled_velocity_rms(:))) ...
    && all(c.pooled_velocity_rms(:)>=0),'shape:e4:CalibrationValues','Expected six pooled RMS values.');
assert(strlength(string(c.source))>0,'shape:e4:CalibrationSource','Calibration source is required.');
end
