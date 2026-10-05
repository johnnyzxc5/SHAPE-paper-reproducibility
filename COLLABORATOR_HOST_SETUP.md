# Kinova portable production host setup

This operational release is self-contained for the project/evidence portion of
the production workflow. It does not authorize a workstation or start
production. Every workstation must qualify itself, and its concurrency receipt
is valid only for that exact host and exact Process-worker count.

Scientific authority remains commit
`5b4d09994fae40e2992d0e118cc9b31cd6cf90a1`. The operational revision changes
file-generation isolation and production governance only.

## Supported host candidates

- Historical environment: Windows x64, MATLAB
  `26.1.0.3312084 (R2026a) Update 4`, MATLAB Coder 26.1, selected MinGW64 C++
  compiler 14.2.0.
- Candidate collaborator environment: Windows x64, MATLAB
  `26.1.0.3346908 (R2026a) Update 5`, MATLAB Coder 26.1, selected Microsoft
  Visual C++ 2022 compiler 17.0. This environment requires fresh base PHYSICAL
  qualification before its concurrency receipt can be issued.

Required products are MATLAB, Simulink, Stateflow, Optimization Toolbox,
Wavelet Toolbox, Parallel Computing Toolbox, and MATLAB Coder. Windows
PowerShell/CIM, required licenses, sufficient disk/RAM, and a supported
selected compiler are external prerequisites. The bundled frozen observer MEX
must be used unchanged; do not rebuild it.

The release contains the complete frozen trajectory registry under
`data/trajectory_registry/production`. Do not replace or regenerate it.

## Operator variables

In PowerShell, set paths and choose a candidate worker count. `<N>` is an
operator choice, not repository policy:

```powershell
$ReleaseRoot = 'D:\KinovaRelease\KINOVA_PRODUCTION_RELEASE_OPERATIONAL_HOST_CONCURRENCY_5b4d099'
$QualificationRoot = 'D:\KinovaQualification'
$ProductionRoot = 'E:\KinovaProduction'
$N = <N>
$QualificationID = "host_concurrency_${N}_YYYYMMDD_r1"
```

## 1. STATIC — NONPHYSICAL

```powershell
Set-Location $ReleaseRoot
New-Item -ItemType Directory -Force $QualificationRoot | Out-Null
& matlab -batch "addpath('Code_Image'); q=run_production_host_qualification('Mode','STATIC','QualificationRoot','$QualificationRoot');" 2>&1 | Tee-Object -FilePath "$QualificationRoot\console_static.log"
```

Expected: `HOST_STATIC_COMPATIBILITY_PASS`, zero physical simulations. STATIC
does not qualify concurrency and does not authorize production.

## 2. Worker file-generation Q1 — NONPHYSICAL

```powershell
Set-Location $ReleaseRoot
& matlab -batch "addpath('docs/codex_p6_worker_topology'); run_eof_worker_cache_isolation_qualification('Stage','Q1','Workers',$N,'QualificationRoot','$QualificationRoot','ProtectedProductionRoot','$ProductionRoot','QualificationID','$QualificationID','CleanupQualificationOwnedFilegen',false);" 2>&1 | Tee-Object -FilePath "$QualificationRoot\$QualificationID\console_q1.log"
```

Expected: exactly `$N` Process workers, unique CacheFolder and CodeGenFolder
per worker, exact fileGen read-back, repository-root `slprj` unused, zero
physical simulations.

## 3. Conditional base PHYSICAL qualification — HUMAN MUST EXECUTE/REVIEW

Run this only when STATIC reports that the current supported environment needs
a fresh base host qualification (for example the Update-5/MSVC candidate):

```powershell
Set-Location $ReleaseRoot
& matlab -batch "addpath('Code_Image'); q=run_production_host_qualification('Mode','PHYSICAL','QualificationRoot','$QualificationRoot\base_physical','Arm','I_AUTHORIZE_HOST_QUALIFICATION_SIMULATIONS');" 2>&1 | Tee-Object -FilePath "$QualificationRoot\base_physical\console_physical.log"
```

This is physical and must be started manually. Require the documented four
C1/C2 Normal/Accelerator runs, full scientific equivalence, observer provenance,
zero fallback, and `HOST_QUALIFICATION_PASS`.

## 4. Exact-concurrency Q2 — PHYSICAL, HUMAN MUST EXECUTE/REVIEW

```powershell
Set-Location $ReleaseRoot
& matlab -batch "addpath('docs/codex_p6_worker_topology'); run_eof_worker_cache_isolation_qualification('Stage','Q2','Workers',$N,'QualificationRoot','$QualificationRoot','ProtectedProductionRoot','$ProductionRoot','QualificationID','$QualificationID','CleanupQualificationOwnedFilegen',false,'Arm','I_AUTHORIZE_NONPRODUCTION_Q2_PHYSICAL_QUALIFICATION');" 2>&1 | Tee-Object -FilePath "$QualificationRoot\$QualificationID\console_q2.log"
```

Acceptance requires: requested `$N` workers observed; unique worker-local cache
and codegen directories; fileGen read-back PASS; repository-root `slprj`
unused; 96/96 frozen P6 qualification runs completed; 96 scientific validator
passes; EOF warnings, retries, quarantines, and failures all zero; protected
hashes PASS.

## 5. Issue and inspect the host-bound receipt — NONPHYSICAL

For the historical Update-4 environment:

```powershell
Set-Location $ReleaseRoot
& matlab -batch "addpath('Code_Image'); q=run_production_host_qualification('Mode','CONCURRENCY_Q2','QualificationRoot','$QualificationRoot\$QualificationID\host_authority','Workers',$N,'EvidenceReceipt','$QualificationRoot\$QualificationID\q2_controlled_physical_receipt.json','Arm','I_ADOPT_INTEGRATED_Q2_HOST_CONCURRENCY');"
```

For an environment requiring the base receipt, add:

```text
'BaseHostQualificationReceipt','$QualificationRoot\base_physical\HOST_QUALIFICATION_RECEIPT.json'
```

Inspect
`$QualificationRoot\$QualificationID\host_authority\HOST_CONCURRENCY_QUALIFICATION_W<N>.json`.
It must say `HOST_CONCURRENCY_QUALIFICATION_PASS`, bind the current host, and
qualify exactly `$N`. It must keep `production_authorized=false`.

## 6. Production PREFLIGHT — NONPHYSICAL

```powershell
$HostReceipt = "$QualificationRoot\$QualificationID\host_authority\HOST_CONCURRENCY_QUALIFICATION_W$N.json"
Set-Location $ReleaseRoot
& matlab -batch "addpath('Code_Image'); r=run_production('Mode','PREFLIGHT','Cohort','PRIMARY','ParentRange',[801 1250],'Workers',$N,'OutputRoot','$ProductionRoot','ShardID','lab_primary_0801_1250','HostQualificationReceipt','$HostReceipt');" 2>&1 | Tee-Object -FilePath "$QualificationRoot\console_production_preflight.log"
```

Expected: preflight PASS, matching host receipt accepted, zero simulations,
production unarmed. A receipt for another host or worker count must fail.

## 7. Production — HUMAN MUST EXPLICITLY ARM

```powershell
Set-Location $ReleaseRoot
& matlab -batch "addpath('Code_Image'); r=run_production('Mode','PRODUCTION','Cohort','PRIMARY','ParentRange',[801 1250],'Workers',$N,'OutputRoot','$ProductionRoot','ShardID','lab_primary_0801_1250','HostQualificationReceipt','$HostReceipt','Arm','I_AUTHORIZE_THIS_PRODUCTION_SHARD');" 2>&1 | Tee-Object -FilePath "$ProductionRoot\PRIMARY\shard_lab_primary_0801_1250\logs\console.log"
```

This final command is production and must be started manually only after the
receipt and assignment are reviewed. Resume by repeating the identical command.
Valid HDF5 UIDs are validated and skipped, never overwritten.

Qualifying `N` does not qualify `N+1`; another workstation must issue its own
receipt. Worker count is operational and host-specific, while the scientific
configuration remains invariant.
