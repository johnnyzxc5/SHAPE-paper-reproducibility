function identity=production_host_identity()
%PRODUCTION_HOST_IDENTITY Stable host binding for concurrency qualification.
hostname=getenv('COMPUTERNAME');
if isempty(hostname), [~,hostname]=system('hostname'); hostname=strtrim(hostname); end
machine_guid=''; cpu_model='';
if ispc
    try machine_guid=char(winqueryreg('HKEY_LOCAL_MACHINE', ...
            'SOFTWARE\Microsoft\Cryptography','MachineGuid')); catch, end
    try cpu_model=char(winqueryreg('HKEY_LOCAL_MACHINE', ...
            'HARDWARE\DESCRIPTION\System\CentralProcessor\0','ProcessorNameString')); catch, end
end
assert(~isempty(hostname) && ~isempty(machine_guid), ...
    'shape:production:HostIdentityUnavailable', ...
    'Stable Windows hostname/MachineGuid identity is unavailable.');
material=strjoin({lower(strtrim(hostname)),lower(strtrim(machine_guid)), ...
    lower(computer('arch')),lower(strtrim(cpu_model))},'|');
md=java.security.MessageDigest.getInstance('SHA-256');
md.update(uint8(unicode2native(material,'UTF-8')));
fingerprint=lower(reshape(dec2hex(typecast(md.digest(),'uint8'),2).',1,[]));
identity=struct('hostname',strtrim(hostname),'architecture',computer('arch'), ...
    'cpu_model',strtrim(cpu_model),'machine_guid_sha256',local_hash(machine_guid), ...
    'fingerprint_sha256',fingerprint);
end

function value=local_hash(text)
md=java.security.MessageDigest.getInstance('SHA-256');
md.update(uint8(unicode2native(lower(strtrim(text)),'UTF-8')));
value=lower(reshape(dec2hex(typecast(md.digest(),'uint8'),2).',1,[]));
end
