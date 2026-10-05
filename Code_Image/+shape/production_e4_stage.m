function production_e4_stage(stage_index_path,calibration_path,matlab_workers)
%PRODUCTION_E4_STAGE Regenerate a bounded E4 chunk from existing Test HDF5.
if nargin<3, matlab_workers=0; end
assert(isscalar(matlab_workers) && matlab_workers>=0 && ...
    matlab_workers==floor(matlab_workers));
T=parquetread(char(stage_index_path));
calibration=jsondecode(fileread(char(calibration_path)));
assert(strcmp(calibration.state,'PRODUCTION_E4_CALIBRATION_FROZEN') && ...
    strcmp(calibration.scope,'PRIMARY_TRAIN') && calibration.run_count==14000);
assert(height(T)>0 && mod(height(T),10)==0);
code_dir=fileparts(fileparts(mfilename('fullpath')));
addpath(code_dir);
addpath(genpath(fullfile(code_dir,'MATLAB','mr')));
models=shape.load_models(code_dir);
cfg=shape.config();
cfg.e4_calibration=calibration;
expected=["velocity_40dB","velocity_30dB","velocity_20dB","velocity_10dB", ...
    "position_0.01deg","position_0.05deg","position_0.2deg", ...
    "combined_40dB_0.01deg","combined_40dB_0.05deg","combined_40dB_0.2deg"];
run_count=height(T)/10;
if matlab_workers>0
    pool=gcp('nocreate');
    assert(~isempty(pool) && isa(pool,'parallel.ProcessPool') && ...
        pool.NumWorkers==matlab_workers, ...
        'E4 staging requires the requested MATLAB process pool.');
    parfor run_i=1:run_count
        base=10*(run_i-1)+1;
        stage_clean_run(T(base:base+9,:),models,cfg,calibration,expected);
    end
else
    for run_i=1:run_count
        base=10*(run_i-1)+1;
        stage_clean_run(T(base:base+9,:),models,cfg,calibration,expected);
    end
end
end

function stage_clean_run(rows,models,cfg,calibration,expected)
    assert(all(string(rows.cohort)=="E4") && all(lower(string(rows.split))=="test"));
    assert(isequal(string(rows.e4_condition)',expected));
    assert(numel(unique(string(rows.clean_run_uid)))==1);
    clean_path=char(string(rows.clean_path(1)));
    assert(isfile(clean_path));
    embedded=jsondecode(h5readatt(clean_path,'/','manifest_record_json'));
    assert(strcmpi(string(embedded.split),'test') && ...
        strcmp(string(embedded.run_uid),string(rows.clean_run_uid(1))) && ...
        double(embedded.noise_seed)==double(rows.noise_seed(1)), ...
        'Clean HDF5 does not match the indexed PRIMARY Test member.');
    clean=struct('q',double(h5read(clean_path,'/telemetry/q_meas')), ...
        'dq',double(h5read(clean_path,'/telemetry/dq_meas')), ...
        'tau_cmd',double(h5read(clean_path,'/telemetry/tau_cmd')));
    ref=struct('q',double(h5read(clean_path,'/reference/q_ref')), ...
        'dq',double(h5read(clean_path,'/reference/dq_ref')), ...
        'ddq',double(h5read(clean_path,'/reference/ddq_ref')), ...
        'tau_nom',double(h5read(clean_path,'/reference/tau_nom')), ...
        't',double(h5read(clean_path,'/coordinates/telemetry_time_s')));
    views=shape.offline_e4(clean,ref,models,cfg,double(rows.noise_seed(1)),calibration);
    assert(numel(views)==10);
    for j=1:10
        row=rows(j,:); view=views{j};
        assert(strcmp(string(view.condition.name),string(row.e4_condition)));
        assert(double(view.condition.position_sigma_deg)==double(row.position_sigma_deg));
        assert(isequal(double(view.condition.velocity_snr_db),double(row.velocity_snr_db)));
        products=shape.represent_e4_view(view,cfg);
        path=char(string(row.path)); folder=fileparts(path);
        if ~isfolder(folder), mkdir(folder); end
        tmp=[path '.tmp']; assert(~isfile(path) && ~isfile(tmp), ...
            'E4 staging path already exists; inspect before regeneration: %s',path);
        copyfile(clean_path,tmp);
        h5write(tmp,'/telemetry/q_meas',single(clean.q+double(view.q_noise)));
        h5write(tmp,'/telemetry/dq_meas',single(clean.dq+double(view.dq_noise)));
        names={'shape','torque','gmo','energy'};
        for n=1:numel(names)
            name=names{n};
            h5write(tmp,['/temporal/' name],view.normalized.(name));
            h5write(tmp,['/cwt/' name '_log'],products.([name '_log']));
            h5write(tmp,['/cwt/' name '_magnitude'],products.([name '_magnitude']));
        end
        h5write(tmp,'/views/shape_fft_amplitude',products.shape_fft_amplitude);
        manifest=jsondecode(h5readatt(clean_path,'/','manifest_record_json'));
        manifest.run_uid=char(string(row.run_uid));
        manifest.clean_run_uid=char(string(row.clean_run_uid));
        manifest.e4_condition=char(string(row.e4_condition));
        manifest.velocity_snr_db=double(row.velocity_snr_db);
        manifest.position_sigma_deg=double(row.position_sigma_deg);
        manifest.position_noise_std_rad=deg2rad(double(row.position_sigma_deg));
        manifest.cohort='E4';
        h5writeatt(tmp,'/','run_uid',manifest.run_uid);
        h5writeatt(tmp,'/','manifest_record_json',jsonencode(manifest));
        h5writeatt(tmp,'/','e4_calibration_state',calibration.state);
        h5writeatt(tmp,'/','e4_calibration_source',calibration.source);
        h5writeatt(tmp,'/','e4_pooled_velocity_rms_json',jsonencode(calibration.pooled_velocity_rms));
        movefile(tmp,path);
end
end
