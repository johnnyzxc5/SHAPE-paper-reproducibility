function calibration = production_e4_calibrate(index_path,artifact_path)
%PRODUCTION_E4_CALIBRATE Freeze pooled velocity RMS from existing PRIMARY Train HDF5.
index_path=char(index_path); artifact_path=char(artifact_path);
T=parquetread(index_path);
assert(height(T)==20300 && sum(string(T.cohort)=="PRIMARY")==20000, ...
    'Expected the completed 20,300-record production index.');
selected=T(string(T.cohort)=="PRIMARY" & lower(string(T.split))=="train",:);
assert(height(selected)==14000 && numel(unique(string(selected.run_uid)))==14000, ...
    'Calibration requires exactly 14,000 unique PRIMARY Train records.');
assert(all(lower(string(selected.split))=="train") && all(string(selected.cohort)=="PRIMARY"));
selected=sortrows(selected,'run_uid');
stats=cell(height(selected),1);
for k=1:height(selected)
    path=char(string(selected.path(k)));
    assert(isfile(path),'Missing PRIMARY Train HDF5: %s',path);
    assert(strcmp(string(h5readatt(path,'/','run_uid')),string(selected.run_uid(k))), ...
        'Indexed UID disagrees with HDF5: %s',path);
    embedded=jsondecode(h5readatt(path,'/','manifest_record_json'));
    assert(strcmpi(string(embedded.split),'train') && ...
        strcmp(string(embedded.run_uid),string(selected.run_uid(k))), ...
        'Calibration HDF5 is not the indexed PRIMARY Train member: %s',path);
    record=struct('run_uid',char(string(selected.run_uid(k))), ...
        'parent_trajectory_id',double(selected.parent_trajectory_id(k)), ...
        'split','train');
    telemetry=struct('dq',double(h5read(path,'/telemetry/dq_meas')));
    stats{k}=shape.e4_calibration_stats(telemetry,record);
end
candidate=shape.aggregate_e4_calibration(stats,'PRIMARY_TRAIN:existing production HDF5');
values=double(candidate.pooled_velocity_rms(:));
assert(candidate.run_count==14000 && candidate.sample_count_per_joint==14000*10001);
assert(numel(values)==6 && all(isfinite(values)) && all(values>=0));
calibration=candidate;
calibration.state='PRODUCTION_E4_CALIBRATION_FROZEN';
calibration.scope='PRIMARY_TRAIN';
calibration.units='rad/s';
calibration.input_index_path=index_path;
calibration.input_index_sha256=shape.sha256_file(index_path);
calibration.formula='sqrt(sum_over_PRIMARY_Train_runs_and_samples(dq_meas.^2)/(14000*10001))';
calibration.procedure='shape.e4_calibration_stats + shape.aggregate_e4_calibration';
calibration.code_state_git_sha=local_git_sha();
calibration.matlab_version=version;
calibration.timestamp_utc=char(datetime('now','TimeZone','UTC','Format','yyyy-MM-dd''T''HH:mm:ss.SSSXXX'));
if isfile(artifact_path)
    existing=jsondecode(fileread(artifact_path));
    fields={'state','scope','units','run_count','sample_count_per_joint', ...
        'run_uids_sha256','input_index_path','input_index_sha256','formula','procedure'};
    for k=1:numel(fields)
        key=fields{k}; assert(isequal(string(existing.(key)),string(calibration.(key))), ...
            'Existing frozen E4 calibration conflicts at %s.',key);
    end
    assert(isequal(double(existing.pooled_velocity_rms(:)),values), ...
        'Existing frozen E4 calibration RMS conflicts.');
    calibration=existing;
    return
end
folder=fileparts(artifact_path); if ~isfolder(folder), mkdir(folder); end
tmp=[artifact_path '.tmp'];
assert(~isfile(tmp),'Calibration temporary file already exists; inspect it before retry.');
fid=fopen(tmp,'w'); assert(fid>=0); cleanup=onCleanup(@() fclose(fid));
fprintf(fid,'%s',jsonencode(calibration,'PrettyPrint',true)); clear cleanup
assert(~isfile(artifact_path),'Calibration appeared during write.');
movefile(tmp,artifact_path);
end

function value=local_git_sha()
value='UNAVAILABLE';
root=fileparts(fileparts(fileparts(mfilename('fullpath'))));
[status,out]=system(sprintf('git -C "%s" rev-parse HEAD',root));
if status==0, value=strtrim(out); end
end
