function hex = sha256_file(path)
%SHA256_FILE Portable streaming SHA-256 for immutable inputs and outputs.
fid = fopen(path,'rb');
if fid < 0, error('shape:sha256:OpenFailed','Cannot open %s.',path); end
cleanup = onCleanup(@() fclose(fid));
md = java.security.MessageDigest.getInstance('SHA-256');
while ~feof(fid)
    bytes = fread(fid,1024*1024,'*uint8');
    if ~isempty(bytes), md.update(bytes); end
end
d = typecast(md.digest(),'uint8');
hex = lower(reshape(dec2hex(d,2).',1,[]));
end
