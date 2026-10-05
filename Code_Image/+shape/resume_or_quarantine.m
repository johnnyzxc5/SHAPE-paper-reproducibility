function [resume,recovery] = resume_or_quarantine(path,uid,cfg,record)
%RESUME_OR_QUARANTINE Preserve invalid final artifacts before regeneration.
resume=false; recovery=struct('state','NO_EXISTING_OUTPUT','quarantine_path','', ...
    'validation_error','');
if ~isfile(path), return; end
try
    if nargin<4, record=[]; end
    shape.validate_output(path,uid,cfg,record);
    resume=true; recovery.state='VALID_OUTPUT_SKIPPED';
catch ME
    index=1;
    while true
        quarantine=sprintf('%s.corrupt.%03d',path,index);
        if ~isfile(quarantine), break; end
        index=index+1;
    end
    movefile(path,quarantine);
    recovery.state='CORRUPT_OUTPUT_QUARANTINED';
    recovery.quarantine_path=quarantine;
    recovery.validation_error=ME.message;
end
end
