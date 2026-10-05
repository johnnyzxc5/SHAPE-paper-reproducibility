function stats = e4_calibration_stats(telemetry,record)
%E4_CALIBRATION_STATS Additive sufficient statistics for pooled dq RMS.
dq=double(telemetry.dq);
assert(size(dq,1)==6 && all(isfinite(dq(:))));
stats=struct('sum_squares',sum(dq.^2,2),'sample_count',size(dq,2), ...
    'run_uid',char(string(record.run_uid)),'parent_trajectory_id',double(record.parent_trajectory_id), ...
    'split',char(string(record.split)),'state','CALIBRATION_NOT_YET_FROZEN');
end
