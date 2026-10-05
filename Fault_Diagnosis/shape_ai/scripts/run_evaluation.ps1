param(
    [string]$IndexPath = 'C:\KinovaProduction\AI\index\full_index.parquet',
    [string]$RunRoot = 'C:\KinovaProduction\AI\runs',
    [string]$OutputRoot = 'C:\KinovaProduction\AI\evaluation',
    [int[]]$Seeds = @(1729),
    [int]$Workers = 4,
    [int]$BatchSize = 32,
    [switch]$IncludeE2B,
    [switch]$IncludeE4
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$Representations = @('shape_cwt','torque_cwt','gmo_cwt','energy_cwt','shape_temporal','shape_fft')
$CwtRepresentations = @('shape_cwt','torque_cwt','gmo_cwt','energy_cwt')
if ($IncludeE4) {
    throw 'Bounded production E4 uses .\scripts\run_e4_production.ps1 -Step Evaluate after calibration; do not use -IncludeE4 with the full index.'
}

foreach ($Seed in $Seeds) {
    foreach ($Representation in $Representations) {
        $Checkpoint = Join-Path $RunRoot "$Representation\seed_$Seed\best.pt"
        if (-not (Test-Path -LiteralPath $Checkpoint)) { throw "Missing checkpoint: $Checkpoint" }
        $PrimaryOutput = Join-Path $OutputRoot "PRIMARY\$Representation\seed_$Seed"
        & $Python -m shape_ai.evaluate --checkpoint $Checkpoint --index $IndexPath `
            --output $PrimaryOutput --cohort PRIMARY --split test --batch-size $BatchSize --num-workers $Workers
        if ($LASTEXITCODE -ne 0) { throw "PRIMARY evaluation failed: $Representation seed $Seed" }
        & $Python -m shape_ai.analysis --predictions (Join-Path $PrimaryOutput 'predictions.parquet') `
            --index $IndexPath --output (Join-Path $PrimaryOutput 'analysis')
        if ($LASTEXITCODE -ne 0) { throw "PRIMARY analysis failed: $Representation seed $Seed" }

        if ($IncludeE2B -and $CwtRepresentations.Contains($Representation)) {
            $E2BOutput = Join-Path $OutputRoot "E2B\$Representation\seed_$Seed"
            & $Python -m shape_ai.evaluate --checkpoint $Checkpoint --index $IndexPath `
                --output $E2BOutput --cohort E2B --split none --batch-size $BatchSize --num-workers $Workers
            if ($LASTEXITCODE -ne 0) { throw "E2B evaluation failed: $Representation seed $Seed" }
            & $Python -m shape_ai.analysis --predictions (Join-Path $E2BOutput 'predictions.parquet') `
                --index $IndexPath --output (Join-Path $E2BOutput 'analysis')
            if ($LASTEXITCODE -ne 0) { throw "E2B analysis failed: $Representation seed $Seed" }
        }
    }
}
