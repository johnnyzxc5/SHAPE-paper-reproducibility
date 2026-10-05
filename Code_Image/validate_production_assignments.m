function receipt=validate_production_assignments(varargin)
%VALIDATE_PRODUCTION_ASSIGNMENTS Prove planned shards are disjoint and complete.
p=inputParser; p.addParameter('Cohort',"",@(x)ischar(x)||isstring(x));
p.addParameter('TargetParentRange',[],@(x)isnumeric(x)&&numel(x)==2);
p.addParameter('TargetParentIDs',[],@isnumeric); p.addParameter('AssignmentParentSets',{},@iscell);
p.addParameter('ShardIDs',string.empty,@(x)isstring(x)||iscellstr(x)||ischar(x));
p.addParameter('ReceiptPath',"",@(x)ischar(x)||isstring(x)); p.parse(varargin{:}); o=p.Results;
assert(xor(isempty(o.TargetParentRange),isempty(o.TargetParentIDs)),'Specify one target parent selection.');
if isempty(o.TargetParentIDs), target=double(o.TargetParentRange(1):o.TargetParentRange(2)); else, target=double(o.TargetParentIDs(:)'); end
sets=o.AssignmentParentSets; shard_ids=string(o.ShardIDs); assert(numel(sets)==numel(shard_ids)&&~isempty(sets));
all_ids=[]; within=true; details=repmat(struct('shard_id','','parent_ids',[],'count',0),numel(sets),1);
for k=1:numel(sets)
    ids=double(sets{k}(:)'); assert(numel(unique(ids))==numel(ids),'Duplicate parent inside shard %s.',shard_ids(k));
    within=within&&all(ismember(ids,target)); all_ids=[all_ids ids]; %#ok<AGROW>
    details(k)=struct('shard_id',char(shard_ids(k)),'parent_ids',ids,'count',numel(ids));
end
duplicates=numel(all_ids)-numel(unique(all_ids)); missing=setdiff(target,all_ids); extras=setdiff(all_ids,target);
code_dir=fileparts(mfilename('fullpath')); addpath(code_dir); spec=shape.production_spec();
cohort=upper(string(o.Cohort));
if cohort=="PRIMARY"
    [T,~]=shape.validate_manifest(spec.primary_manifest);
elseif cohort=="E2B"
    [T,~]=shape.validate_manifest(spec.e2b_manifest);
else
    error('shape:production:InvalidCohort','Cohort must be PRIMARY or E2B.');
end
manifest_coverage=all(ismember(target,double(unique(T.parent_trajectory_id))'));
pass=within&&duplicates==0&&isempty(missing)&&isempty(extras)&&manifest_coverage;
receipt=struct('schema_version','production-assignment-plan-v1','status','ASSIGNMENT_PLAN_FAIL','pass',pass, ...
    'cohort',char(cohort),'target_parent_ids',target,'target_parent_count',numel(target), ...
    'assignments',details,'union_parent_count',numel(unique(all_ids)),'duplicate_parent_count',duplicates, ...
    'missing_parent_ids',missing,'extra_parent_ids',extras,'manifest_coverage',manifest_coverage, ...
    'physical_simulations_executed',0,'production_authorized',false,'created_utc',local_now());
if pass, receipt.status='ASSIGNMENT_PLAN_PASS'; end
if strlength(string(o.ReceiptPath))>0, shape.write_json_atomic(char(string(o.ReceiptPath)),receipt); end
assert(pass,'Planned production assignments are not an exact disjoint partition.');
end
function v=local_now(), v=char(datetime('now','TimeZone','UTC','Format','yyyy-MM-dd''T''HH:mm:ss.SSSXXX')); end
