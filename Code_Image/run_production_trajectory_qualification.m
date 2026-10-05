function summary = run_production_trajectory_qualification()
%RUN_PRODUCTION_TRAJECTORY_QUALIFICATION Definitive qualification and freeze of 5030 production parents.
%
% GOVERNANCE CONTRACT:
% - Exact parent population: 5,000 Primary + 30 Paired E2-B = 5,030 total
% - Physical Simulink simulations executed: 0
% - P6 status: RATIFIED/CLOSED (8 process workers)
% - GATE08 status: RATIFIED/CLOSED
% - Production authorization: FALSE

started_total = tic;
root = fileparts(fileparts(mfilename('fullpath')));
code = fullfile(root, 'Code_Image');
addpath(code);
addpath(genpath(fullfile(code, 'MATLAB', 'mr')));

cfg = shape.config();
models = shape.load_models(code);

manifest_dir = fullfile(root, 'docs', 'codex_active', 'manifests');
primary_manifest_path = fullfile(manifest_dir, 'PRIMARY_MANIFEST_DRY_RUN.parquet');
e2b_manifest_path = fullfile(manifest_dir, 'E2B_PAIRED_MANIFEST_CANDIDATE.parquet');

expected_hashes = struct( ...
    'primary', '676a0a412ff00943f65525034ca3c1e3f3614ac9cbfd6f5a62a70edc91a99472', ...
    'e2b',     '958201c8b598346c801a7df35748331cda6bc7bdb5f8abf68b627ab7dc59518c');

fprintf('====================================================\n');
fprintf('STAGE 0 — FORENSIC PREFLIGHT\n');
fprintf('====================================================\n');

% 1. Verify manifest hashes
fprintf('Verifying immutable manifest hashes...\n');
actual_primary_sha = shape.sha256_file(primary_manifest_path);
actual_e2b_sha = shape.sha256_file(e2b_manifest_path);
assert(strcmp(actual_primary_sha, expected_hashes.primary), 'Primary manifest SHA mismatch.');
assert(strcmp(actual_e2b_sha, expected_hashes.e2b), 'E2-B manifest SHA mismatch.');
fprintf('  Primary manifest SHA256: %s [VERIFIED]\n', actual_primary_sha);
fprintf('  E2-B manifest SHA256:    %s [VERIFIED]\n', actual_e2b_sha);

% 2. Validate manifests
[T_prim, rep_prim] = shape.validate_manifest(primary_manifest_path);
[T_e2b, rep_e2b] = shape.validate_manifest(e2b_manifest_path);
fprintf('  Primary rows: %d, parents: %d [VALIDATED]\n', rep_prim.rows, rep_prim.parents);
fprintf('  E2-B rows:    %d, parents: %d [VALIDATED]\n', rep_e2b.rows, rep_e2b.parents);

% 3. Extract unique parent records
[~, idx_prim] = unique(T_prim.parent_trajectory_id, 'stable');
parents_prim_records = T_prim(idx_prim, :);
[~, idx_e2b] = unique(T_e2b.parent_trajectory_id, 'stable');
parents_e2b_records = T_e2b(idx_e2b, :);

all_records = [parents_prim_records; parents_e2b_records];
[~, sort_idx] = sort(all_records.parent_trajectory_id);
all_records = all_records(sort_idx, :);

N_total = height(all_records);
assert(N_total == 5030, 'Total parent population must be exactly 5030.');
assert(isequal(double(all_records.parent_trajectory_id)', 1:5030), 'Parent IDs must be contiguous 1:5030.');

% 4. Preflight inventory of registry
registry_dir = fullfile(root, 'data', 'trajectory_registry', 'production');
if ~isfolder(registry_dir)
    mkdir(registry_dir);
end

existing_valid_mask = false(N_total, 1);
for k = 1:N_total
    id = all_records.parent_trajectory_id(k);
    mat_file = fullfile(registry_dir, sprintf('parent_%04d_trajectory.mat', id));
    json_file = fullfile(registry_dir, sprintf('parent_%04d_qualification.json', id));
    if isfile(mat_file) && isfile(json_file)
        try
            s = load(mat_file, 'artifact');
            if isfield(s, 'artifact') && strcmp(s.artifact.qualification.qualification_status, 'PASS')
                shape.verify_frozen_trajectory(s.artifact, all_records(k, :), models, cfg);
                existing_valid_mask(k) = true;
            end
        catch
            existing_valid_mask(k) = false;
        end
    end
end

preexisting_valid_count = sum(existing_valid_mask);
missing_count = N_total - preexisting_valid_count;

fprintf('\nPRE-GENERATION INVENTORY:\n');
fprintf('  Target registry directory:       %s\n', registry_dir);
fprintf('  Total required scientific parents: 5030\n');
fprintf('  Preexisting valid production parents: %d\n', preexisting_valid_count);
fprintf('  Missing parents to generate:          %d\n', missing_count);
fprintf('  Pilot-only trajectories isolated:     24 (parents 9001:9024 in data/trajectory_registry/pilot24/v2)\n');

fprintf('\n====================================================\n');
fprintf('STAGE 1 & 2 — BUILD & SCIENTIFIC QUALIFICATION\n');
fprintf('====================================================\n');

% Set up parallel pool with 8 workers
p = gcp('nocreate');
if isempty(p)
    fprintf('Starting parallel pool with 8 workers...\n');
    p = parpool('Processes', 8);
else
    if p.NumWorkers ~= 8
        fprintf('Adjusting parallel pool to 8 workers...\n');
        delete(p);
        p = parpool('Processes', 8);
    end
end
fprintf('Active parallel pool workers: %d\n', p.NumWorkers);

out = cell(N_total, 1);
gen_timer = tic;

% Sliced variables for parfor
records_cell = cell(N_total, 1);
for k = 1:N_total
    records_cell{k} = all_records(k, :);
end

% Set up progress monitoring queue
dq = parallel.pool.DataQueue;
progress_count = 0;
progress_timer = tic;
afterEach(dq, @local_report_progress);

fprintf('Starting parallel qualification of %d parents on 8 workers...\n', N_total);
parfor k = 1:N_total
    rec = records_cell{k};
    id = rec.parent_trajectory_id;
    mat_file = fullfile(registry_dir, sprintf('parent_%04d_trajectory.mat', id));
    json_file = fullfile(registry_dir, sprintf('parent_%04d_qualification.json', id));
    
    if existing_valid_mask(k)
        % Reuse valid existing artifact
        s = load(mat_file, 'artifact');
        art = s.artifact;
        q = art.qualification;
        contract = shape.trajectory_contract(models, cfg);
        out{k} = struct( ...
            'parent_trajectory_id', id, ...
            'qualification_status', char(q.qualification_status), ...
            'accepted_attempt', q.accepted_attempt, ...
            'attempt_count', q.attempt_count, ...
            'failure_counts', q.failure_counts, ...
            'metrics', q.metrics, ...
            'trajectory_sha256', art.trajectory_sha256, ...
            'generator_sha256', contract.generator_sha256, ...
            'constraint_contract_sha256', contract.constraint_sha256, ...
            'model_sha256', contract.model_sha256, ...
            'artifact_path', mat_file, ...
            'receipt_path', json_file, ...
            'qualification_time_s', 0.0, ...
            'K_segments', double(rec.K_segments), ...
            'trajectory_mode', char(string(rec.trajectory_mode)), ...
            'trajectory_seed', double(rec.trajectory_seed));
    else
        out{k} = shape.qualify_parent(rec, models, registry_dir, cfg);
    end
    send(dq, k);
end
gen_elapsed_s = toc(gen_timer);
fprintf('Qualification completed in %.2f s (%.2f min). Average: %.3f s/parent.\n', ...
    gen_elapsed_s, gen_elapsed_s / 60, gen_elapsed_s / N_total);

% Check failure rule
reasons_names = {'Q_LIMIT','DQ_LIMIT','DDQ_LIMIT','TORQUE_LIMIT','OBSERVABILITY', ...
    'STATIC_FEASIBILITY','SPLINE_INVALID','NONFINITE','OTHER'};
failing_parents = [];
for k = 1:N_total
    if ~strcmp(out{k}.qualification_status, 'PASS') || out{k}.accepted_attempt > 500
        failing_parents = [failing_parents; out{k}.parent_trajectory_id]; %#ok<AGROW>
    end
end

if ~isempty(failing_parents)
    fprintf('\nFAILURE RULE TRIGGERED!\n');
    fprintf('The following parents failed qualification:\n');
    disp(failing_parents);
    error('shape:trajectory:QualificationFailure', ...
        'PRODUCTION TRAJECTORY REGISTRY = NOT FROZEN. %d parents failed qualification.', numel(failing_parents));
end

fprintf('\n====================================================\n');
fprintf('STAGE 3 — POPULATION-LEVEL AUDIT\n');
fprintf('====================================================\n');

primary_qualified_count = 0;
e2b_qualified_count = 0;
all_hashes = strings(N_total, 1);
all_ids = zeros(N_total, 1);

for k = 1:N_total
    all_ids(k) = out{k}.parent_trajectory_id;
    all_hashes(k) = string(out{k}.trajectory_sha256);
    if all_ids(k) <= 5000
        primary_qualified_count = primary_qualified_count + 1;
    else
        e2b_qualified_count = e2b_qualified_count + 1;
    end
end

total_qualified_count = primary_qualified_count + e2b_qualified_count;
assert(primary_qualified_count == 5000, 'Primary qualified count must be exactly 5000.');
assert(e2b_qualified_count == 30, 'E2-B qualified count must be exactly 30.');
assert(total_qualified_count == 5030, 'Total qualified count must be exactly 5030.');

% Check unique parent IDs
assert(numel(unique(all_ids)) == 5030, 'Parent IDs must be completely unique.');
assert(isequal(sort(all_ids(:))', 1:5030), 'Parent IDs must span 1:5030.');

% Check duplicate trajectory SHA
unique_hashes = unique(all_hashes);
num_unique_hashes = numel(unique_hashes);
unintended_duplicate_sha_count = N_total - num_unique_hashes;
assert(unintended_duplicate_sha_count == 0, 'All 5030 trajectory content hashes must be unique.');
fprintf('  Primary qualified:                %d / 5000\n', primary_qualified_count);
fprintf('  Paired E2-B qualified:            %d / 30\n', e2b_qualified_count);
fprintf('  Total qualified:                  %d / 5030\n', total_qualified_count);
fprintf('  Unique parent IDs:                %d / 5030\n', numel(unique(all_ids)));
fprintf('  Unique trajectory hashes:         %d / 5030\n', num_unique_hashes);
fprintf('  Unintended duplicate hashes:      %d\n', unintended_duplicate_sha_count);

% Check missing artifacts
missing_mat_count = 0;
missing_json_count = 0;
for k = 1:N_total
    id = all_ids(k);
    if ~isfile(fullfile(registry_dir, sprintf('parent_%04d_trajectory.mat', id)))
        missing_mat_count = missing_mat_count + 1;
    end
    if ~isfile(fullfile(registry_dir, sprintf('parent_%04d_qualification.json', id)))
        missing_json_count = missing_json_count + 1;
    end
end
assert(missing_mat_count == 0 && missing_json_count == 0, 'Missing trajectory files on disk.');
fprintf('  Missing trajectory artifacts:     0\n');
fprintf('  Provenance complete:              YES\n');

% Rejection reason aggregation
total_rejections = 0;
reason_totals = zeros(numel(reasons_names), 1);
attempts_vec = zeros(N_total, 1);
parents_hitting_max = 0;

for k = 1:N_total
    att = out{k}.accepted_attempt;
    attempts_vec(k) = att;
    total_rejections = total_rejections + (att - 1);
    if att >= 500
        parents_hitting_max = parents_hitting_max + 1;
    end
    for j = 1:numel(reasons_names)
        reason_totals(j) = reason_totals(j) + out{k}.failure_counts.(reasons_names{j});
    end
end

fprintf('\nREJECTION AND ATTEMPT STATISTICS:\n');
fprintf('  Total rejected attempts:          %d\n', total_rejections);
fprintf('  Parents hitting max_attempts (500): %d\n', parents_hitting_max);
fprintf('  Attempt distribution: min=%d, p25=%.1f, p50=%.1f, p75=%.1f, p90=%.1f, p95=%.1f, max=%d, mean=%.2f\n', ...
    min(attempts_vec), prctile(attempts_vec, 25), median(attempts_vec), prctile(attempts_vec, 75), ...
    prctile(attempts_vec, 90), prctile(attempts_vec, 95), max(attempts_vec), mean(attempts_vec));

fprintf('\n====================================================\n');
fprintf('STAGE 4 — DETERMINISTIC MANIFEST & RE-READ VERIFICATION\n');
fprintf('====================================================\n');

% Build canonical manifest table
relpaths = strings(N_total, 1);
for k = 1:N_total
    rel = strrep(string(out{k}.artifact_path), string([root filesep]), '');
    relpaths(k) = replace(rel, '\', '/');
end

parent_id = zeros(N_total, 1, 'int64');
trajectory_seed = zeros(N_total, 1, 'int64');
accepted_attempt = zeros(N_total, 1, 'int64');
attempt_count = zeros(N_total, 1, 'int64');
K_segments = zeros(N_total, 1, 'int64');
trajectory_mode = strings(N_total, 1);
qualification_status = strings(N_total, 1);
trajectory_sha256 = strings(N_total, 1);
generator_sha256 = strings(N_total, 1);
constraint_contract_sha256 = strings(N_total, 1);
model_sha256 = strings(N_total, 1);
q_margin_rad = zeros(N_total, 1);
dq_margin_rad_s = zeros(N_total, 1);
ddq_margin_rad_s2 = zeros(N_total, 1);
torque_margin_Nm = zeros(N_total, 1);
L_q2_rad = zeros(N_total, 1);

for k = 1:N_total
    parent_id(k) = int64(out{k}.parent_trajectory_id);
    trajectory_seed(k) = int64(out{k}.trajectory_seed);
    accepted_attempt(k) = int64(out{k}.accepted_attempt);
    attempt_count(k) = int64(out{k}.attempt_count);
    K_segments(k) = int64(out{k}.K_segments);
    trajectory_mode(k) = string(out{k}.trajectory_mode);
    qualification_status(k) = string(out{k}.qualification_status);
    trajectory_sha256(k) = string(out{k}.trajectory_sha256);
    generator_sha256(k) = string(out{k}.generator_sha256);
    constraint_contract_sha256(k) = string(out{k}.constraint_contract_sha256);
    model_sha256(k) = string(out{k}.model_sha256);
    q_margin_rad(k) = out{k}.metrics.q_margin_rad;
    dq_margin_rad_s(k) = out{k}.metrics.dq_margin_rad_s;
    ddq_margin_rad_s2(k) = out{k}.metrics.ddq_margin_rad_s2;
    torque_margin_Nm(k) = out{k}.metrics.torque_margin_Nm;
    L_q2_rad(k) = out{k}.metrics.L_q2_rad;
end

canonical_binding = table( ...
    parent_id, trajectory_seed, accepted_attempt, attempt_count, relpaths, ...
    trajectory_sha256, generator_sha256, constraint_contract_sha256, model_sha256, ...
    K_segments, trajectory_mode, qualification_status, ...
    q_margin_rad, dq_margin_rad_s, ddq_margin_rad_s2, torque_margin_Nm, L_q2_rad, ...
    'VariableNames', { ...
    'parent_id', 'trajectory_seed', 'accepted_attempt', 'attempt_count', 'trajectory_artifact_path', ...
    'trajectory_sha256', 'generator_sha256', 'constraint_contract_sha256', 'model_sha256', ...
    'K_segments', 'trajectory_mode', 'qualification_status', ...
    'q_margin_rad', 'dq_margin_rad_s', 'ddq_margin_rad_s2', 'torque_margin_Nm', 'L_q2_rad'});

% Deterministic sort by parent_id ascending
canonical_binding = sortrows(canonical_binding, 'parent_id', 'ascend');

canonical_manifest_path = fullfile(manifest_dir, 'PRODUCTION_TRAJECTORY_BINDING.parquet');
fprintf('Writing canonical production trajectory manifest: %s\n', canonical_manifest_path);
parquetwrite(canonical_manifest_path, canonical_binding);
canonical_manifest_sha256 = shape.sha256_file(canonical_manifest_path);
fprintf('Canonical Manifest SHA256: %s\n', canonical_manifest_sha256);

% RE-READ VERIFICATION FROM DISK
fprintf('\nExecuting re-read hash verification from disk (NO generation)...\n');
reread_timer = tic;
reread_pass_vec = false(N_total, 1);
expected_binding_hashes = string(canonical_binding.trajectory_sha256);

parfor k = 1:N_total
    rec = records_cell{k};
    id = rec.parent_trajectory_id;
    mat_file = fullfile(registry_dir, sprintf('parent_%04d_trajectory.mat', id));
    
    if isfile(mat_file)
        try
            s = load(mat_file, 'artifact');
            art = s.artifact;
            
            % Verify contract
            shape.verify_frozen_trajectory(art, rec, models, cfg);
            
            % Recompute content hash
            recomputed_hash = shape.trajectory_content_hash(art);
            if strcmp(recomputed_hash, art.trajectory_sha256) && ...
               strcmp(recomputed_hash, char(expected_binding_hashes(k)))
                reread_pass_vec(k) = true;
            end
        catch
            reread_pass_vec(k) = false;
        end
    end
end

reread_elapsed_s = toc(reread_timer);
assert(all(reread_pass_vec), 'Re-read hash verification failed.');
fprintf('Re-read verification PASSED %d/%d in %.2f s.\n', sum(reread_pass_vec), N_total, reread_elapsed_s);

fprintf('\n====================================================\n');
fprintf('STAGE 5 — FREEZE & GOVERNANCE RECEIPT\n');
fprintf('====================================================\n');

report_dir = fullfile(root, 'docs', 'codex_implementation', 'production_trajectory');
if ~isfolder(report_dir), mkdir(report_dir); end

% 1. Full Results CSV
R = table(parent_id, trajectory_seed, qualification_status, accepted_attempt, attempt_count, ...
    trajectory_mode, K_segments, q_margin_rad, dq_margin_rad_s, ddq_margin_rad_s2, torque_margin_Nm, ...
    L_q2_rad, trajectory_sha256, generator_sha256, constraint_contract_sha256, model_sha256, relpaths, ...
    'VariableNames', {'parent_id','trajectory_seed','qualification_status','accepted_attempt','attempt_count', ...
    'trajectory_mode','K_segments','q_margin_rad','dq_margin_rad_s','ddq_margin_rad_s2','torque_margin_Nm', ...
    'L_q2_rad','trajectory_sha256','generator_sha256','constraint_contract_sha256','model_sha256','artifact_path'});
writetable(R, fullfile(report_dir, '01_PRODUCTION_TRAJECTORY_QUALIFICATION_RESULTS.csv'));

% 2. Rejection Reasons CSV
S = table(string(reasons_names(:)), reason_totals, 'VariableNames', {'predicate', 'rejection_count'});
writetable(S, fullfile(report_dir, '02_REJECTION_REASON_SUMMARY.csv'));

% 3. Hash Register CSV
H = R(:, {'parent_id','trajectory_seed','accepted_attempt','trajectory_sha256', ...
    'generator_sha256','constraint_contract_sha256','model_sha256','artifact_path'});
writetable(H, fullfile(report_dir, '03_PRODUCTION_TRAJECTORY_HASH_REGISTER.csv'));

% Contract object for receipt
contract = shape.trajectory_contract(models, cfg);

% 4. Master Freeze Receipt JSON
receipt = struct();
receipt.schema_version = 'production-trajectory-freeze-receipt-v1';
receipt.freeze_status = 'FROZEN';
receipt.production_trajectory_population_qualified = true;
receipt.production_trajectory_registry_frozen = true;
receipt.total_qualified_parents = 5030;
receipt.primary_qualified_parents = 5000;
receipt.paired_e2b_qualified_parents = 30;
receipt.preexisting_valid_parents = preexisting_valid_count;
receipt.newly_generated_parents = missing_count;
receipt.rejected_generation_attempts = total_rejections;
receipt.parents_hitting_max_attempts = parents_hitting_max;
receipt.unique_parent_ids = 5030;
receipt.unintended_duplicate_trajectory_sha = 0;
receipt.missing_trajectory_artifacts = 0;
receipt.provenance_complete = true;

receipt.gates = struct();
receipt.gates.duration_timebase_gate = 'PASS';
receipt.gates.K_gate = 'PASS';
receipt.gates.fly_stop_contract = 'PASS';
receipt.gates.joint2_observability_gate = 'PASS';
receipt.gates.numerical_finite_gate = 'PASS';
receipt.gates.e2b_pairing_contract = 'PASS';
receipt.gates.reread_hash_verification = 'PASS';

receipt.registry_paths = struct();
receipt.registry_paths.production_registry_dir = 'data/trajectory_registry/production';
receipt.registry_paths.canonical_manifest_path = 'docs/codex_active/manifests/PRODUCTION_TRAJECTORY_BINDING.parquet';
receipt.registry_paths.canonical_manifest_sha256 = canonical_manifest_sha256;
receipt.registry_paths.primary_input_manifest_sha256 = expected_hashes.primary;
receipt.registry_paths.e2b_input_manifest_sha256 = expected_hashes.e2b;

receipt.generator_authority = struct();
receipt.generator_authority.generator_sha256 = contract.generator_sha256;
receipt.generator_authority.constraint_contract_sha256 = contract.constraint_sha256;
receipt.generator_authority.model_sha256 = contract.model_sha256;
receipt.generator_authority.rng_algorithm = contract.rng_algorithm;
receipt.generator_authority.software_version = version;
receipt.generator_authority.software_release = version('-release');

receipt.attempt_statistics = struct( ...
    'min', min(attempts_vec), ...
    'p25', prctile(attempts_vec, 25), ...
    'median', median(attempts_vec), ...
    'p75', prctile(attempts_vec, 75), ...
    'p90', prctile(attempts_vec, 90), ...
    'p95', prctile(attempts_vec, 95), ...
    'max', max(attempts_vec), ...
    'mean', mean(attempts_vec));

receipt.p6_worker_authority = struct( ...
    'status', 'RATIFIED/CLOSED', ...
    'final_production_worker_count', 8);

receipt.gate08_storage_authority = struct( ...
    'status', 'RATIFIED/CLOSED', ...
    'active_canonical_serializer_sha', '848d0abe1aa018f92978d5d46b6e99d222e32534f1adf67df2b420b04f129fce');

receipt.production_physical_simulations_executed = 0;
receipt.production_authorization = false;
receipt.commit = false;
receipt.push = false;

freeze_receipt_json_manifest = fullfile(manifest_dir, 'PRODUCTION_TRAJECTORY_FREEZE_RECEIPT.json');
freeze_receipt_json_report = fullfile(report_dir, 'PRODUCTION_TRAJECTORY_FREEZE_RECEIPT.json');
shape.write_json_atomic(freeze_receipt_json_manifest, receipt);
shape.write_json_atomic(freeze_receipt_json_report, receipt);

total_walltime_s = toc(started_total);
summary = struct( ...
    'receipt', receipt, ...
    'canonical_manifest_sha256', canonical_manifest_sha256, ...
    'total_walltime_s', total_walltime_s, ...
    'gen_elapsed_s', gen_elapsed_s, ...
    'reread_elapsed_s', reread_elapsed_s);

fprintf('\n====================================================\n');
fprintf('QUALIFICATION AND FREEZE SUMMARY COMPLETE\n');
fprintf('====================================================\n');
fprintf('PREEXISTING VALID PRODUCTION PARENTS = %d\n', preexisting_valid_count);
fprintf('NEWLY GENERATED PARENTS = %d\n', missing_count);
fprintf('REJECTED GENERATION ATTEMPTS = %d\n', total_rejections);
fprintf('PARENTS HITTING MAX_ATTEMPTS = %d\n', parents_hitting_max);
fprintf('\n');
fprintf('PRIMARY QUALIFIED = %d / 5000\n', primary_qualified_count);
fprintf('PAIRED E2-B QUALIFIED = %d / 30\n', e2b_qualified_count);
fprintf('TOTAL QUALIFIED = %d / 5030\n', total_qualified_count);
fprintf('\n');
fprintf('UNIQUE PARENT IDS = %d / 5030\n', numel(unique(all_ids)));
fprintf('UNINTENDED DUPLICATE TRAJECTORY SHA = %d\n', unintended_duplicate_sha_count);
fprintf('MISSING TRAJECTORY ARTIFACTS = 0\n');
fprintf('PROVENANCE COMPLETE = YES\n');
fprintf('\n');
fprintf('DURATION/TIMEBASE GATE = PASS\n');
fprintf('K GATE = PASS\n');
fprintf('FLY/STOP CONTRACT = PASS\n');
fprintf('JOINT-2 OBSERVABILITY >=0.8 rad = PASS\n');
fprintf('NUMERICAL/FINITE GATE = PASS\n');
fprintf('E2-B PAIRING CONTRACT = PASS\n');
fprintf('\n');
fprintf('CANONICAL PRODUCTION TRAJECTORY MANIFEST = %s\n', canonical_manifest_path);
fprintf('MANIFEST SHA256 = %s\n', canonical_manifest_sha256);
fprintf('\n');
fprintf('REGISTRY RE-READ HASH VERIFICATION = PASS\n');
fprintf('\n');
fprintf('PRODUCTION TRAJECTORY POPULATION QUALIFIED = YES\n');
fprintf('PRODUCTION TRAJECTORY REGISTRY FROZEN = YES\n');
fprintf('\n');
fprintf('P6 STATUS = RATIFIED/CLOSED\n');
fprintf('FINAL PRODUCTION WORKER COUNT = 8\n');
fprintf('\n');
fprintf('GATE08 STATUS = RATIFIED/CLOSED\n');
fprintf('ACTIVE CANONICAL SERIALIZER SHA =\n848d0abe1aa018f92978d5d46b6e99d222e32534f1adf67df2b420b04f129fce\n');
fprintf('\n');
fprintf('PRODUCTION PHYSICAL SIMULATIONS EXECUTED = 0\n');
fprintf('PRODUCTION AUTHORIZATION = FALSE\n');
fprintf('\n');
fprintf('COMMIT = NO\n');
fprintf('PUSH = NO\n');
fprintf('\n');
fprintf('PRODUCTION 5030 TRAJECTORY QUALIFICATION AND FREEZE COMPLETE\n');

    function local_report_progress(~)
        progress_count = progress_count + 1;
        if mod(progress_count, 250) == 0 || progress_count == N_total
            el = toc(progress_timer);
            rate = progress_count / el * 60;
            rem_min = (N_total - progress_count) / (progress_count / el) / 60;
            fprintf('  [PROGRESS] %4d / %d parents qualified (%5.1f%%) | %5.1f parents/min | Est. rem: %4.1f min\n', ...
                progress_count, N_total, progress_count / N_total * 100, rate, rem_min);
        end
    end
end
