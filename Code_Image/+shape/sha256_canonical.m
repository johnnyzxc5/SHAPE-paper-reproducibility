function hex = sha256_canonical(varargin)
%SHA256_CANONICAL Hash typed values using UTF-8 labels and little-endian bytes.
md=java.security.MessageDigest.getInstance('SHA-256');
for k=1:nargin
    value=varargin{k};
    if isstring(value) || ischar(value)
        bytes=unicode2native(char(string(value)),'UTF-8');
        local_update(md,uint8('TEXT|')); local_update(md,typecast(uint64(numel(bytes)),'uint8'));
        local_update(md,bytes);
    elseif isnumeric(value) || islogical(value)
        if islogical(value), value=uint8(value); end
        header=sprintf('NUM|%s|%s|',class(value),sprintf('%dx',size(value)));
        local_update(md,unicode2native(header,'UTF-8'));
        [~,~,endian]=computer;
        if endian=='B' && ~isa(value,'uint8') && ~isa(value,'int8'), value=swapbytes(value); end
        local_update(md,typecast(value(:),'uint8'));
    else
        error('shape:hash:UnsupportedType','Unsupported canonical hash type %s.',class(value));
    end
end
d=typecast(md.digest(),'uint8');
hex=lower(reshape(dec2hex(d,2).',1,[]));
end
function local_update(md,bytes)
md.update(uint8(bytes(:)));
end
