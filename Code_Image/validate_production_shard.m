function receipt=validate_production_shard(varargin)
%VALIDATE_PRODUCTION_SHARD One-command read-only shard validator.
p=inputParser; p.addParameter('ShardRoot',"",@(x)ischar(x)||isstring(x));
p.addParameter('RequireComplete',true,@(x)islogical(x)&&isscalar(x));
p.addParameter('ReceiptPath',"",@(x)ischar(x)||isstring(x)); p.parse(varargin{:}); o=p.Results;
assert(strlength(string(o.ShardRoot))>0,'ShardRoot is required.'); code_dir=fileparts(mfilename('fullpath')); addpath(code_dir);
receipt=shape.validate_production_shard(char(string(o.ShardRoot)),'RequireComplete',o.RequireComplete);
path=string(o.ReceiptPath); if strlength(path)==0, path=fullfile(string(o.ShardRoot),'validation_receipt.json'); end
shape.write_json_atomic(char(path),receipt);
end
