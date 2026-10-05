function ledger = postgate_lifecycle_ledger(action, arg)
%POSTGATE_LIFECYCLE_LEDGER Truthful physical simulation lifecycle accounting.
% Tracks:
%   - physical_runs_attempted
%   - physical_sims_started (strictly incremented immediately before sim())
%   - physical_sims_completed (recorded immediately after sim() returns)
%   - physical_runs_postprocessed (recorded after postprocessing pipeline)
%
% Enforces hard cap: maximum 4 physical simulations started.
% Persists state in persistent memory and on disk: POSTGATE_LIFECYCLE_LEDGER.json.
%
% Actions:
%   'init'           - Initialize/reset counters to 0, write ledger file.
%   'run_attempted'  - Record physical run attempt for given run_label.
%   'sim_started'    - Immediately before sim(in), enforces cap, increments started.
%   'sim_completed'  - Immediately after sim(in) returns, increments completed.
%   'postprocessed'  - After postprocessing completes, increments postprocessed.
%   'get'            - Return current lifecycle accounting struct.

persistent state;

if nargin < 1 || isempty(action)
    action = 'get';
end
if nargin < 2
    arg = '';
end

ledger_dir = fileparts(mfilename('fullpath'));
ledger_file = fullfile(ledger_dir, 'POSTGATE_LIFECYCLE_LEDGER.json');

% Direct handling for 'init' to guarantee clean state without stale disk read
if strcmpi(char(string(action)), 'init')
    next_state = local_default_state();
    if ~isempty(arg) && isnumeric(arg) && isscalar(arg) && arg > 0
        next_state.max_authorized_simulations = double(arg);
    end
    next_state.last_action = 'init';
    next_state.last_updated_utc = local_now_str();
    local_write_disk(ledger_file, next_state);
    state = next_state;
    ledger = state;
    return;
end

% Recover state from disk if persistent memory was cleared. Only explicit
% 'init' may create a fresh state; every other action fails closed when the
% durable ledger cannot be recovered and completely validated.
if isempty(state)
    if ~isfile(ledger_file)
        error('postgate:ledger_not_initialized', ...
            'Lifecycle ledger is not initialized or is missing: %s. Explicit init is required.', ...
            ledger_file);
    end

    try
        raw = fileread(ledger_file);
    catch ME
        error('postgate:ledger_read_failed', ...
            'Failed to read lifecycle ledger %s: %s', ledger_file, ME.message);
    end

    try
        recovered_state = jsondecode(raw);
    catch ME
        error('postgate:ledger_json_invalid', ...
            'Lifecycle ledger contains invalid JSON (%s): %s', ledger_file, ME.message);
    end

    % Validate and normalize into a local candidate. Persistent state is not
    % assigned until every schema and relationship check has passed.
    recovered_state = local_validate_recovered_state(recovered_state, ledger_file);
    state = recovered_state;
end

switch lower(char(string(action)))
    case 'run_attempted'
        next_state = state;
        next_state.physical_runs_attempted = next_state.physical_runs_attempted + 1;
        next_state.last_action = 'run_attempted';
        next_state.last_updated_utc = local_now_str();
        next_state.run_log{end+1} = struct('action', 'run_attempted', 'label', char(string(arg)), 'timestamp_utc', local_now_str());
        local_write_disk(ledger_file, next_state);
        state = next_state;

    case 'sim_started'
        % Hard cap enforcement: maximum 4 physical simulations
        if state.physical_sims_started >= state.max_authorized_simulations
            error('postgate:max_simulations_exceeded', ...
                'Physical simulation hard cap (%d) exceeded! Refusing to start simulation %s.', ...
                state.max_authorized_simulations, char(string(arg)));
        end
        next_state = state;
        next_state.physical_sims_started = next_state.physical_sims_started + 1;
        next_state.last_action = 'sim_started';
        next_state.last_updated_utc = local_now_str();
        next_state.run_log{end+1} = struct('action', 'sim_started', 'label', char(string(arg)), ...
            'sim_number', next_state.physical_sims_started, 'timestamp_utc', local_now_str());
        local_write_disk(ledger_file, next_state);
        state = next_state;

    case 'sim_completed'
        next_state = state;
        next_state.physical_sims_completed = next_state.physical_sims_completed + 1;
        next_state.last_action = 'sim_completed';
        next_state.last_updated_utc = local_now_str();
        next_state.run_log{end+1} = struct('action', 'sim_completed', 'label', char(string(arg)), ...
            'completed_count', next_state.physical_sims_completed, 'timestamp_utc', local_now_str());
        local_write_disk(ledger_file, next_state);
        state = next_state;

    case 'postprocessed'
        next_state = state;
        next_state.physical_runs_postprocessed = next_state.physical_runs_postprocessed + 1;
        next_state.last_action = 'postprocessed';
        next_state.last_updated_utc = local_now_str();
        next_state.run_log{end+1} = struct('action', 'postprocessed', 'label', char(string(arg)), ...
            'postprocessed_count', next_state.physical_runs_postprocessed, 'timestamp_utc', local_now_str());
        local_write_disk(ledger_file, next_state);
        state = next_state;

    case 'get'
        % Return current state

    otherwise
        error('postgate:unknown_ledger_action', 'Unknown ledger action: %s', action);
end

ledger = state;

end

function s = local_default_state()
s = struct( ...
    'physical_runs_attempted', 0, ...
    'physical_sims_started', 0, ...
    'physical_sims_completed', 0, ...
    'physical_runs_postprocessed', 0, ...
    'max_authorized_simulations', 12, ...
    'last_action', 'init', ...
    'last_updated_utc', local_now_str(), ...
    'run_log', {{}});
end

function s = local_now_str()
s = char(datetime('now', ...
    'TimeZone', 'UTC', ...
    'Format', 'yyyy-MM-dd HH:mm:ss.SSS'));
end

function s = local_validate_recovered_state(candidate, ledger_file)
if ~(isstruct(candidate) && isscalar(candidate))
    local_schema_error(ledger_file, 'top-level JSON value must decode to a scalar structure');
end

required = { ...
    'physical_runs_attempted', ...
    'physical_sims_started', ...
    'physical_sims_completed', ...
    'physical_runs_postprocessed', ...
    'max_authorized_simulations', ...
    'run_log'};
missing = required(~isfield(candidate, required));
if ~isempty(missing)
    local_schema_error(ledger_file, sprintf('missing required field(s): %s', strjoin(missing, ', ')));
end

counter_fields = { ...
    'physical_runs_attempted', ...
    'physical_sims_started', ...
    'physical_sims_completed', ...
    'physical_runs_postprocessed', ...
    'max_authorized_simulations'};
for k = 1:numel(counter_fields)
    name = counter_fields{k};
    value = candidate.(name);
    if ~(isnumeric(value) && isreal(value) && isscalar(value) && ...
            isfinite(double(value)) && double(value) >= 0 && ...
            double(value) == fix(double(value)))
        local_schema_error(ledger_file, sprintf( ...
            'field %s must be a finite, nonnegative, integer-valued numeric scalar', name));
    end
end

if double(candidate.max_authorized_simulations) < 1
    local_schema_error(ledger_file, ...
        'max_authorized_simulations must be at least 1');
end
if double(candidate.physical_sims_completed) > double(candidate.physical_sims_started)
    local_schema_error(ledger_file, ...
        'physical_sims_completed exceeds physical_sims_started');
end
if double(candidate.physical_runs_postprocessed) > double(candidate.physical_sims_completed)
    local_schema_error(ledger_file, ...
        'physical_runs_postprocessed exceeds physical_sims_completed');
end
if double(candidate.physical_sims_started) > double(candidate.max_authorized_simulations)
    local_schema_error(ledger_file, ...
        'physical_sims_started exceeds max_authorized_simulations');
end
if double(candidate.physical_sims_started) > double(candidate.physical_runs_attempted)
    local_schema_error(ledger_file, ...
        'physical_sims_started exceeds physical_runs_attempted');
end

candidate.run_log = local_normalize_run_log(candidate.run_log, ledger_file, double(candidate.max_authorized_simulations));

% The log is part of the accounting evidence, not optional decoration.
% Its event counts must agree with the committed counters.
actions = cellfun(@(entry) char(string(entry.action)), candidate.run_log, ...
    'UniformOutput', false);
expected_counts = [ ...
    double(candidate.physical_runs_attempted), ...
    double(candidate.physical_sims_started), ...
    double(candidate.physical_sims_completed), ...
    double(candidate.physical_runs_postprocessed)];
actual_counts = [ ...
    sum(strcmp(actions, 'run_attempted')), ...
    sum(strcmp(actions, 'sim_started')), ...
    sum(strcmp(actions, 'sim_completed')), ...
    sum(strcmp(actions, 'postprocessed'))];
if ~isequal(actual_counts, expected_counts)
    local_schema_error(ledger_file, ...
        'run_log event counts do not match lifecycle counters');
end

s = candidate;
end

function log_entries = local_normalize_run_log(raw_log, ledger_file, max_sims)
if nargin < 3 || isempty(max_sims)
    max_sims = inf;
end
if iscell(raw_log)
    log_entries = raw_log(:).';
elseif isstruct(raw_log)
    log_entries = cell(1, numel(raw_log));
    for entry_index = 1:numel(raw_log)
        log_entries{entry_index} = raw_log(entry_index);
    end
elseif isempty(raw_log) && (isnumeric(raw_log) || islogical(raw_log))
    % jsondecode represents an empty JSON array as an empty numeric array.
    log_entries = {};
else
    local_schema_error(ledger_file, ...
        'run_log must decode from a JSON array of lifecycle event objects');
end

allowed_actions = {'run_attempted', 'sim_started', 'sim_completed', 'postprocessed'};
seen_attempted = 0;
seen_started = 0;
seen_completed = 0;
seen_postprocessed = 0;
for k = 1:numel(log_entries)
    entry = log_entries{k};
    if ~(isstruct(entry) && isscalar(entry))
        local_schema_error(ledger_file, sprintf('run_log entry %d is not a scalar object', k));
    end
    required_entry_fields = {'action', 'label', 'timestamp_utc'};
    if ~all(isfield(entry, required_entry_fields))
        local_schema_error(ledger_file, sprintf('run_log entry %d is missing required fields', k));
    end
    if ~local_is_text_scalar(entry.action) || ...
            ~local_is_text_scalar(entry.label) || ...
            ~local_is_text_scalar(entry.timestamp_utc)
        local_schema_error(ledger_file, sprintf( ...
            'run_log entry %d action, label, and timestamp_utc must be text scalars', k));
    end
    action = char(string(entry.action));
    if ~any(strcmp(action, allowed_actions))
        local_schema_error(ledger_file, sprintf( ...
            'run_log entry %d has unknown action %s', k, action));
    end

    if strcmp(action, 'run_attempted')
        seen_attempted = seen_attempted + 1;
    elseif strcmp(action, 'sim_started')
        seen_started = seen_started + 1;
        sequence_value = local_validate_log_count(entry, 'sim_number', k, ledger_file);
        if sequence_value ~= seen_started || seen_started > seen_attempted || seen_started > max_sims
            local_schema_error(ledger_file, sprintf( ...
                'run_log entry %d has an invalid sim_started sequence', k));
        end
    elseif strcmp(action, 'sim_completed')
        seen_completed = seen_completed + 1;
        sequence_value = local_validate_log_count(entry, 'completed_count', k, ledger_file);
        if sequence_value ~= seen_completed || seen_completed > seen_started
            local_schema_error(ledger_file, sprintf( ...
                'run_log entry %d has an invalid sim_completed sequence', k));
        end
    elseif strcmp(action, 'postprocessed')
        seen_postprocessed = seen_postprocessed + 1;
        sequence_value = local_validate_log_count(entry, 'postprocessed_count', k, ledger_file);
        if sequence_value ~= seen_postprocessed || seen_postprocessed > seen_completed
            local_schema_error(ledger_file, sprintf( ...
                'run_log entry %d has an invalid postprocessed sequence', k));
        end
    end
end
end

function count = local_validate_log_count(entry, field_name, entry_index, ledger_file)
if ~isfield(entry, field_name)
    local_schema_error(ledger_file, sprintf( ...
        'run_log entry %d is missing %s', entry_index, field_name));
end
value = entry.(field_name);
if ~(isnumeric(value) && isreal(value) && isscalar(value) && ...
        isfinite(double(value)) && double(value) >= 1 && ...
        double(value) == fix(double(value)))
    local_schema_error(ledger_file, sprintf( ...
        'run_log entry %d field %s must be a positive integer-valued numeric scalar', ...
        entry_index, field_name));
end
count = double(value);
end

function tf = local_is_text_scalar(value)
tf = (ischar(value) && isrow(value) && ~isempty(value)) || ...
    (isstring(value) && isscalar(value) && ~ismissing(value) && strlength(value) > 0);
end

function local_schema_error(ledger_file, detail)
error('postgate:ledger_schema_invalid', ...
    'Lifecycle ledger schema is invalid (%s): %s', ledger_file, detail);
end

function local_write_disk(path, data)
tmp_path = [path, '.tmp'];
fid = fopen(tmp_path, 'w');
if fid < 0
    error('postgate:ledger_open_failed', 'Failed to open ledger temporary file for writing: %s', tmp_path);
end
try
    count = fprintf(fid, '%s', jsonencode(data, 'PrettyPrint', true));
    if count < 0
        fclose(fid);
        error('postgate:ledger_write_failed', 'Failed to write JSON payload to ledger temporary file: %s', tmp_path);
    end
    status_close = fclose(fid);
    if status_close ~= 0
        error('postgate:ledger_close_failed', 'Failed to close ledger temporary file: %s', tmp_path);
    end
catch ME
    try fclose(fid); catch; end
    if isfile(tmp_path), delete(tmp_path); end
    rethrow(ME);
end

[move_ok, move_msg] = movefile(tmp_path, path, 'f');
if ~move_ok
    if isfile(tmp_path), delete(tmp_path); end
    error('postgate:ledger_persist_failed', 'Failed to atomic-rename ledger file to %s: %s', path, move_msg);
end
end
