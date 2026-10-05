function receipt=validate_production_union(varargin)
%VALIDATE_PRODUCTION_UNION Read-only logical consolidation; never copies outputs.
p=inputParser; p.addParameter('ShardRoots',string.empty,@(x)isstring(x)||iscellstr(x)||ischar(x));
p.addParameter('Cohort',"",@(x)ischar(x)||isstring(x));
p.addParameter('TargetParentRange',[],@(x)isnumeric(x)&&numel(x)==2);
p.addParameter('TargetParentIDs',[],@isnumeric); p.addParameter('ReceiptPath',"",@(x)ischar(x)||isstring(x)); p.parse(varargin{:}); o=p.Results;
roots=string(o.ShardRoots); assert(~isempty(roots),'ShardRoots are required.');
assert(xor(isempty(o.TargetParentRange),isempty(o.TargetParentIDs)),'Specify one target parent selection.');
if isempty(o.TargetParentIDs), target=double(o.TargetParentRange(1):o.TargetParentRange(2)); else, target=double(o.TargetParentIDs(:)'); end
all_parents=[]; all_uids=strings(0,1); all_shas=strings(0,1); shard_reports=cell(numel(roots),1);
for k=1:numel(roots)
    r=shape.validate_production_shard(char(roots(k)),'RequireComplete',true); shard_reports{k}=r;
    assert(strcmpi(r.cohort,char(string(o.Cohort))),'Shard cohort mismatch.');
    all_parents=[all_parents double(r.parent_ids(:)')]; %#ok<AGROW>
    inv=r.inventory; all_uids=[all_uids;string({inv.run_uid})']; all_shas=[all_shas;string({inv.sha256})']; %#ok<AGROW>
end
parent_duplicates=numel(all_parents)-numel(unique(all_parents)); uid_duplicates=numel(all_uids)-numel(unique(all_uids));
missing=setdiff(target,all_parents); extras=setdiff(all_parents,target); conflicting=0;
if uid_duplicates>0
    [u,~,g]=unique(all_uids); for k=1:numel(u), s=unique(all_shas(g==k)); if sum(g==k)>1&&numel(s)>1, conflicting=conflicting+1; end, end
end
pass=parent_duplicates==0&&uid_duplicates==0&&conflicting==0&&isempty(missing)&&isempty(extras);
receipt=struct('schema_version','production-union-validation-v1','status','PRODUCTION_UNION_FAIL','pass',pass, ...
    'cohort',upper(char(string(o.Cohort))),'target_parent_ids',target,'target_parent_count',numel(target), ...
    'shard_roots',{cellstr(roots)},'shard_reports',{shard_reports},'union_parent_count',numel(unique(all_parents)), ...
    'union_run_count',numel(all_uids),'duplicate_parent_count',parent_duplicates,'duplicate_uid_count',uid_duplicates, ...
    'conflicting_uid_sha_count',conflicting,'missing_parent_ids',missing,'extra_parent_ids',extras, ...
    'files_copied',0,'physical_simulations_executed',0,'production_authorized',false, ...
    'ready_for_checkpoint',pass,'created_utc',local_now());
if pass, receipt.status='PRODUCTION_UNION_PASS'; end
if strlength(string(o.ReceiptPath))>0, shape.write_json_atomic(char(string(o.ReceiptPath)),receipt); end
assert(pass,'Production shard union is incomplete, overlapping, or conflicting.');
end
function v=local_now(), v=char(datetime('now','TimeZone','UTC','Format','yyyy-MM-dd''T''HH:mm:ss.SSSXXX')); end
