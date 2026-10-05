function [ctdq,diagnostics] = evaluate_ctdq(q,dq,models,cfg)
%EVALUATE_CTDQ Selectable C(q,dq)'*dq backend with a safe GOLD fallback.
arguments
    q (6,:) double
    dq (6,:) double
    models struct
    cfg struct
end
assert(isequal(size(q),size(dq)),'shape:ctdq:SizeMismatch');
if any(~isfinite(q(:))) || any(~isfinite(dq(:)))
    error('shape:ctdq:NonFiniteInput','q and dq must contain only finite values.');
end
backend=char(cfg.observer_ctdq_backend);
switch backend
    case 'finite_difference_gold'
        ctdq=zeros(size(q));
        for k=1:size(q,2)
            ctdq(:,k)=shape.coriolis_transpose_velocity(q(:,k),dq(:,k),models);
        end
        diagnostics=struct('requested_backend',backend,'actual_backend',backend, ...
            'fallback_used',false,'mass_matrix_calls_per_sample',12, ...
            'implementation','MATLAB central finite difference GOLD', ...
            'status','GOLD_ACTIVE','backend_version',cfg.observer_ctdq_gold_version, ...
            'requested_backend_version',cfg.observer_ctdq_gold_version, ...
            'actual_backend_version',cfg.observer_ctdq_gold_version, ...
            'mex_sha256','','source_sha256',shape.sha256_file(fullfile( ...
            fileparts(fileparts(mfilename('fullpath'))),'+shape','coriolis_transpose_velocity.m')));
    case 'finite_difference_batch_mex'
        selftest=shape.ctdq_mex_selftest(models,cfg);
        if selftest.pass
            ctdq=ctdq_finite_difference_batch_mex(q,dq,models.Mlist_nom, ...
                models.Glist_nom,models.Slist_nom);
            diagnostics=struct('requested_backend',backend,'actual_backend',backend, ...
                'fallback_used',false,'mass_matrix_calls_per_sample',12, ...
                'implementation','code-generated batched GOLD algorithm', ...
                'status','MEX_ACTIVE','backend_version',cfg.observer_ctdq_backend_version, ...
                'requested_backend_version',cfg.observer_ctdq_backend_version, ...
                'actual_backend_version',cfg.observer_ctdq_backend_version, ...
                'mex_sha256',selftest.mex_sha256,'source_sha256',selftest.source_sha256, ...
                'selftest',selftest);
        else
            fallback_cfg=cfg; fallback_cfg.observer_ctdq_backend='finite_difference_gold';
            [ctdq,diagnostics]=shape.evaluate_ctdq(q,dq,models,fallback_cfg);
            diagnostics.requested_backend=backend;
            diagnostics.requested_backend_version=cfg.observer_ctdq_backend_version;
            diagnostics.actual_backend_version=cfg.observer_ctdq_gold_version;
            diagnostics.fallback_used=true;
            diagnostics.status=selftest.fallback_status;
            diagnostics.fallback_reason=selftest.reason;
            diagnostics.selftest=selftest;
            diagnostics.mex_sha256=selftest.mex_sha256;
            diagnostics.source_sha256=selftest.source_sha256;
            warning('shape:ctdq:GoldFallback','%s: %s',selftest.fallback_status,selftest.reason);
        end
    otherwise
        error('shape:ctdq:UnknownBackend','Unknown observer Ctdq backend: %s',backend);
end
end
