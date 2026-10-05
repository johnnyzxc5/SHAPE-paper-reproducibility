param(
    [ValidateSet('Calibrate','Verify','Evaluate')][string]$Step = 'Verify',
    [string]$IndexPath = 'C:\KinovaProduction\AI\index\full_index.parquet',
    [string]$CalibrationPath = 'C:\KinovaProduction\AI\e4\production_e4_calibration.json',
    [string]$RunRoot = 'C:\KinovaProduction\AI\runs',
    [string]$OutputRoot = 'C:\KinovaProduction\AI\evaluation\E4',
    [string]$StageRoot = 'C:\KinovaProduction\AI\e4\stage',
    [int]$ChunkRuns = 4,
    [int]$SmokeRuns = 0,
    [int]$Workers = 4,
    [ValidateRange(0,10)][int]$MatlabWorkers = 0,
    [int]$BatchSize = 32
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { throw "Python environment missing: $Python" }
$Arguments = @('-m','shape_ai.e4_production',$Step.ToLowerInvariant(),
    '--index',$IndexPath,'--calibration',$CalibrationPath,'--run-root',$RunRoot,
    '--output-root',$OutputRoot,'--stage-root',$StageRoot,'--chunk-runs',"$ChunkRuns",
    '--smoke-runs',"$SmokeRuns",'--workers',"$Workers",'--matlab-workers',"$MatlabWorkers",
    '--batch-size',"$BatchSize")
& $Python @Arguments
if ($LASTEXITCODE -ne 0) { throw "E4 $Step failed." }
