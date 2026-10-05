param(
    [string]$PrimaryRoot = 'C:\KinovaProduction\PRIMARY',
    [string]$E2BRoot = 'C:\KinovaProduction\E2B',
    [string]$E4Root = '',
    [string]$AiRoot = 'C:\KinovaProduction\AI'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$IndexDir = Join-Path $AiRoot 'index'
$IndexPath = Join-Path $IndexDir 'full_index.parquet'
$ReportPath = Join-Path $IndexDir 'full_preflight.json'
New-Item -ItemType Directory -Force -Path $IndexDir | Out-Null

$Arguments = @(
    '-m', 'shape_ai.indexing',
    '--root', "PRIMARY=$PrimaryRoot",
    '--root', "E2B=$E2BRoot",
    '--output', $IndexPath,
    '--mode', 'full',
    '--verify-core',
    '--derive-dq2'
)
if ($E4Root) {
    $Arguments += @('--root', "E4=$E4Root")
}
& $Python @Arguments
if ($LASTEXITCODE -ne 0) { throw 'Index construction failed.' }

& $Python -m shape_ai.preflight --index $IndexPath --mode full --samples 24 --report $ReportPath
if ($LASTEXITCODE -ne 0) { throw 'Scientific preflight failed.' }
Write-Host "Preflight complete: $ReportPath"
