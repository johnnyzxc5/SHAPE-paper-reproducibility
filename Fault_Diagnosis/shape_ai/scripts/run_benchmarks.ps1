param(
    [string]$IndexPath = 'C:\KinovaProduction\AI\index\full_index.parquet',
    [string]$OutputRoot = 'C:\KinovaProduction\AI\benchmarks',
    [string]$BatchSizes = '8,16,32,64',
    [string]$Workers = '0,2,4,8',
    [ValidateSet('off','fp16','bf16')][string]$Amp = 'fp16'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null

# SHAPE represents all three six-joint CWT methods. EO and both 1D shapes are benchmarked separately.
$Representations = @('shape_cwt', 'energy_cwt', 'shape_temporal', 'shape_fft')
foreach ($Representation in $Representations) {
    $Output = Join-Path $OutputRoot "$Representation.json"
    & $Python -m shape_ai.benchmark --index $IndexPath --representation $Representation `
        --batch-sizes $BatchSizes --workers $Workers --amp $Amp --output $Output
    if ($LASTEXITCODE -ne 0) { throw "Benchmark failed for $Representation" }
}
