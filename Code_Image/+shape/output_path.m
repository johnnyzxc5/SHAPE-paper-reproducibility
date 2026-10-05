function path = output_path(output_dir,record)
%OUTPUT_PATH Stable UID-based shard path used by generation and resume.
uid=char(string(record.run_uid)); parent=double(record.parent_trajectory_id);
shard=sprintf('parent_%04d_%04d',100*floor((parent-1)/100)+1,100*floor((parent-1)/100)+100);
path=fullfile(output_dir,shard,['run_' uid '.h5']);
end
