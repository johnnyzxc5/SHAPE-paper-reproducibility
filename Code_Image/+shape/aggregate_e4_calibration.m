function calibration = aggregate_e4_calibration(stats,source)
%AGGREGATE_E4_CALIBRATION Build a non-final pooled RMS candidate.
assert(~isempty(stats),'At least one clean telemetry statistic is required.');
total=zeros(6,1); count=0; uids=strings(numel(stats),1);
for k=1:numel(stats)
    total=total+double(stats{k}.sum_squares(:));
    count=count+double(stats{k}.sample_count);
    uids(k)=string(stats{k}.run_uid);
end
calibration=struct('state','CALIBRATION_CANDIDATE', ...
    'pooled_velocity_rms',sqrt(total/count),'source',char(string(source)), ...
    'run_count',numel(stats),'sample_count_per_joint',count, ...
    'run_uids_sha256',local_text_sha(join(sort(uids),newline)));
end
function value=local_text_sha(text)
md=java.security.MessageDigest.getInstance('SHA-256');
bytes=typecast(md.digest(uint8(char(text))),'uint8');
value=lower(reshape(dec2hex(bytes,2).',1,[]));
end
