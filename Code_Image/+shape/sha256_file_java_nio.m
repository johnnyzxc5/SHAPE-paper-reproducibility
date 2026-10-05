function hex=sha256_file_java_nio(path)
%SHA256_FILE_JAVA_NIO Experimental local Java NIO streaming SHA-256.
% Digest semantics are identical to shape.sha256_file; qualification is
% required before any selection or promotion.
md=java.security.MessageDigest.getInstance('SHA-256');
stream=java.io.FileInputStream(java.io.File(path)); channel=stream.getChannel();
cleanup=onCleanup(@() local_close(channel,stream));
buffer=java.nio.ByteBuffer.allocateDirect(8*1024*1024);
while true
    count=channel.read(buffer);
    if count<0, break; end
    if count==0, continue; end
    buffer.flip(); md.update(buffer); buffer.clear();
end
d=typecast(md.digest(),'uint8'); hex=lower(reshape(dec2hex(d,2).',1,[]));
clear cleanup
end

function local_close(channel,stream)
try, channel.close(); catch, end
try, stream.close(); catch, end
end
