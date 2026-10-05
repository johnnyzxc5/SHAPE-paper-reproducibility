function result = execute_with_retry(operation,identity,cfg,log_path)
%EXECUTE_WITH_RETRY Bounded attempts with invariant identity and JSONL log.
for attempt=1:(cfg.max_retries+1)
    try
        result=operation(attempt);
        local_log(log_path,identity,attempt,'SUCCESS','');
        result.retry_count=attempt-1;
        return
    catch ME
        terminal=attempt==(cfg.max_retries+1);
        state='RETRYABLE_FAILURE'; if terminal, state='FINAL_FAILURE'; end
        local_log(log_path,identity,attempt,state,ME);
        if terminal, rethrow(ME); end
    end
end
end
function local_log(path,identity,attempt,state,error_value)
event=identity; event.attempt=attempt; event.state=state;
event.utc=char(datetime('now','TimeZone','UTC','Format','yyyy-MM-dd''T''HH:mm:ss.SSSXXX'));
if isempty(error_value), event.error_id=''; event.error_message='';
else, event.error_id=error_value.identifier; event.error_message=error_value.message; end
folder=fileparts(path); if ~isfolder(folder), mkdir(folder); end
fid=fopen(path,'a'); assert(fid>=0,'Unable to open retry log.'); cleanup=onCleanup(@() fclose(fid));
fprintf(fid,'%s\n',jsonencode(event));
end
