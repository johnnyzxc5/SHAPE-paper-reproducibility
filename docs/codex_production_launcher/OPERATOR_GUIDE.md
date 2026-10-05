# Kinova production operator guide

Start with the root-level `COLLABORATOR_HOST_SETUP.md`. Production uses
host-specific exact concurrency authority. There is no universal W6, W8, W10,
or other worker-count authority.

## Safety and authority

- Complete parents are the assignment unit; siblings are never split.
- Production uses Process workers only.
- Every worker receives a unique session-owned CacheFolder and CodeGenFolder
  before model loading. Repository-root `slprj` is rejected.
- A receipt for `Workers=N` authorizes exactly `N`, only on the bound host and
  runtime environment.
- Capacity is required but is not authorization.
- STATIC, Q1, and production PREFLIGHT execute no physical simulation.
- Q2 and conditional base PHYSICAL qualification require deliberate human
  arming.
- Production requires its own separate arming token.
- Canonical resume validates and skips existing valid UIDs without overwrite.

## Portable inputs

The release contains:

- all 5,030 frozen trajectory MAT files and 5,030 qualification JSON files;
- frozen production binding and Primary/E2-B manifests;
- frozen observer MEX and source provenance;
- canonical C1/C2 host-qualification evidence;
- the production runtime and canonical validators.

No trajectory may be generated, substituted, or fetched from another project
tree. Host receipts and production outputs belong outside the release.

## Required host workflow

The exact commands are maintained in `COLLABORATOR_HOST_SETUP.md`:

1. Extract release and choose candidate `N`.
2. Run STATIC (nonphysical).
3. Run Q1 file-generation concurrency check at `N` (nonphysical).
4. If required by environment policy, manually run base PHYSICAL qualification.
5. Manually run the 24-parent/96-run Q2 at exactly `N`.
6. Issue and inspect the machine-readable concurrency receipt.
7. Run production PREFLIGHT with the exact receipt (nonphysical).
8. Manually arm production only after review.

The current host's receipt is intentionally not part of the portable release.
Historical evidence cannot be auto-discovered as current host authority.

## Multi-host assignment validation

Before execution, prove disjoint complete-parent coverage. Example:

```powershell
Set-Location $ReleaseRoot
& matlab -batch "addpath('Code_Image'); r=validate_production_assignments('Cohort','PRIMARY','TargetParentRange',[1 1250],'AssignmentParentSets',{1:800,801:1250},'ShardIDs',{'hostA_primary_0001_0800','hostB_primary_0801_1250'},'ReceiptPath','D:\KinovaCheckpoint\checkpoint_0001_1250_plan.json');"
```

Validate completed shards independently:

```powershell
& matlab -batch "addpath('Code_Image'); r=validate_production_shard('ShardRoot','D:\KinovaProduction\PRIMARY\shard_hostA_primary_0001_0800');"
& matlab -batch "addpath('Code_Image'); r=validate_production_shard('ShardRoot','E:\KinovaProduction\PRIMARY\shard_hostB_primary_0801_1250');"
```

Logically validate the union without copying HDF5 files:

```powershell
& matlab -batch "addpath('Code_Image'); r=validate_production_union('ShardRoots',{'D:\KinovaProduction\PRIMARY\shard_hostA_primary_0001_0800','E:\KinovaProduction\PRIMARY\shard_hostB_primary_0801_1250'},'Cohort','PRIMARY','TargetParentRange',[1 1250],'ReceiptPath','D:\KinovaCheckpoint\PRIMARY_CHECKPOINT_0001_1250.json');"
```

Conflicting duplicate UIDs, missing assignments, differing file hashes, or
invalid canonical outputs are hard failures. Consolidation never overwrites or
copies scientific HDF5 files.

The generic launcher supports all Primary tranches and E2-B without separate
scientific code paths.
