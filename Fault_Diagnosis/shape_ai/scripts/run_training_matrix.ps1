param(
    [string]$IndexPath = 'C:\KinovaProduction\AI\index\full_index.parquet',
    [string]$OutputRoot = 'C:\KinovaProduction\AI\runs',
    [int[]]$Seeds = @(1729),
    [int]$Workers = 4,
    [int]$BatchCwt = 16,
    [int]$BatchEnergy = 64,
    [int]$BatchTemporal = 32,
    [int]$BatchFft = 64,
    [ValidateSet('off','fp16','bf16')][string]$Amp = 'fp16',
    [switch]$Execute
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$Configs = Join-Path $ProjectRoot 'configs'
$Matrix = @(
    @{ Name='shape_cwt'; Batch=$BatchCwt },
    @{ Name='torque_cwt'; Batch=$BatchCwt },
    @{ Name='gmo_cwt'; Batch=$BatchCwt },
    @{ Name='energy_cwt'; Batch=$BatchEnergy },
    @{ Name='shape_temporal'; Batch=$BatchTemporal },
    @{ Name='shape_fft'; Batch=$BatchFft }
)

foreach ($Seed in $Seeds) {
    foreach ($Experiment in $Matrix) {
        $Config = Join-Path $Configs ($Experiment.Name + '.json')
        $Command = @(
            '-m', 'shape_ai.train', '--config', $Config, '--index', $IndexPath,
            '--output-root', $OutputRoot, '--seed', [string]$Seed,
            '--batch-size', [string]$Experiment.Batch, '--num-workers', [string]$Workers,
            '--amp', $Amp
        )
        Write-Host "$Python $($Command -join ' ')"
        if ($Execute) {
            & $Python @Command
            if ($LASTEXITCODE -ne 0) { throw "Training failed: $($Experiment.Name), seed=$Seed" }
        }
    }
}
if (-not $Execute) {
    Write-Host 'Dry run only. Re-run with -Execute after checking the printed matrix.'
}
