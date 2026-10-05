function write_json_atomic(path,value)
%WRITE_JSON_ATOMIC Durable same-directory JSON replacement.
folder=fileparts(path); if ~isfolder(folder), mkdir(folder); end
tmp=[path '.tmp']; fid=fopen(tmp,'w'); assert(fid>=0,'Unable to create JSON temp file: %s',tmp);
cleanup=onCleanup(@() fclose(fid)); fprintf(fid,'%s',jsonencode(value,'PrettyPrint',true)); clear cleanup
movefile(tmp,path,'f');
end
