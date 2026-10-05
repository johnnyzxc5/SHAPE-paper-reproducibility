function out=mpc_runtime_context(action,varargin)
%MPC_RUNTIME_CONTEXT Host-owned MPC preparation for the extrinsic controller.
% No structure crosses the Stateflow/MATLAB Function run-time boundary.
persistent state generation
if isempty(generation), generation=uint64(0); end
switch lower(char(action))
    case 'set'
        prep=varargin{1};
        required={'Ts','N','nu','ny','nq','Adseq','Bdseq','Cdseq', ...
            'xop','yop','uop','y_ref','t','P0InstrumentationEnabled', ...
            'P2ExactCacheEnabled','P2ExactCacheVersion', ...
            'P3SharedRNEAEnabled','P3SharedRNEAVersion','P4BMassBackend'};
        if ~all(isfield(prep,required))
            error('shape:mpc:RuntimeContextFields', ...
                'MPC runtime context is missing one or more required fields.');
        end
        numeric_fields=required(1:13);
        for k=1:numel(numeric_fields)
            if ~(isnumeric(prep.(numeric_fields{k})) && ...
                    all(isfinite(double(prep.(numeric_fields{k})(:)))))
                error('shape:mpc:RuntimeContextNumeric', ...
                    'MPC runtime context field %s must be finite numeric data.',numeric_fields{k});
            end
        end
        if ~(islogical(prep.P0InstrumentationEnabled) && isscalar(prep.P0InstrumentationEnabled))
            error('shape:mpc:RuntimeContextLogical', ...
                'P0InstrumentationEnabled must be a scalar logical.');
        end
        if ~(islogical(prep.P2ExactCacheEnabled) && isscalar(prep.P2ExactCacheEnabled))
            error('shape:mpc:RuntimeContextLogical', ...
                'P2ExactCacheEnabled must be a scalar logical.');
        end
        if ~(islogical(prep.P3SharedRNEAEnabled) && isscalar(prep.P3SharedRNEAEnabled))
            error('shape:mpc:RuntimeContextLogical', ...
                'P3SharedRNEAEnabled must be a scalar logical.');
        end
        if ~(isnumeric(prep.P4BMassBackend) && isscalar(prep.P4BMassBackend) && ...
                any(double(prep.P4BMassBackend)==[0 1]))
            error('shape:mpc:RuntimeContextBackend', ...
                'P4BMassBackend must be the numeric scalar 0 or 1.');
        end
        if ~strcmp(prep.P2ExactCacheVersion,'p2-exact-invariants-v1')
            error('shape:mpc:RuntimeContextVersion', ...
                'P2 exact-cache runtime-context version is invalid.');
        end
        if ~strcmp(prep.P3SharedRNEAVersion,'p3-shared-rnea-v1')
            error('shape:mpc:RuntimeContextVersion', ...
                'P3 shared-RNEA runtime-context version is invalid.');
        end
        generation=generation+1; state=prep;
        out=struct('initialized',true,'generation',generation, ...
            'cache_version',state.P2ExactCacheVersion);
    case 'get'
        assert(~isempty(state),'shape:mpc:RuntimeContextUnset', ...
            'MPC runtime context must be initialized before controller execution.');
        out=state;
    case 'clear'
        state=[];
        out=struct('initialized',false,'generation',generation, ...
            'cache_version','p2-exact-invariants-v1');
    case 'snapshot'
        out=struct('initialized',~isempty(state),'generation',generation, ...
            'cache_version','p2-exact-invariants-v1');
    otherwise
        error('shape:mpc:RuntimeContextAction','Unknown action %s.',action);
end
end
