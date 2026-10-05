param(
    [Parameter(Mandatory=$true)]
    [string]$CsvPath,
    [Parameter(Mandatory=$true)]
    [string]$StopFilePath,
    [int]$IntervalSec = 2,
    [int]$ParentPid = 0
)

# Ensure output directory exists
$csvDir = Split-Path -Path $CsvPath -Parent
if ($csvDir -and -not (Test-Path $csvDir)) {
    New-Item -ItemType Directory -Path $csvDir -Force | Out-Null
}

# Clean existing CSV if present
if (Test-Path $CsvPath) {
    Remove-Item $CsvPath -Force -ErrorAction SilentlyContinue
}

$sw = [System.Diagnostics.Stopwatch]::StartNew()

while (-not (Test-Path $StopFilePath)) {
    # Orphan prevention: exit if parent process died
    if ($ParentPid -gt 0) {
        $parent = Get-Process -Id $ParentPid -ErrorAction SilentlyContinue
        if (-not $parent) {
            break
        }
    }

    $nowUtc = [DateTime]::UtcNow.ToString('yyyy-MM-dd HH:mm:ss.fff')
    $elapsed = [Math]::Round($sw.Elapsed.TotalSeconds, 2)
    
    # OS Memory
    $os = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue
    $totalRamMb = 0
    $freeRamMb  = 0
    $usedRamMb  = 0
    $ramPct     = 0
    if ($os) {
        $totalRamMb = [Math]::Round($os.TotalVisibleMemorySize / 1024, 1)
        $freeRamMb  = [Math]::Round($os.FreePhysicalMemory / 1024, 1)
        $usedRamMb  = [Math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / 1024, 1)
        $ramPct     = [Math]::Round(($usedRamMb / $totalRamMb) * 100, 1)
    }
    
    # Pagefile
    $pf = Get-CimInstance Win32_PageFileUsage -ErrorAction SilentlyContinue
    $pfAllocMb = 0
    $pfUsedMb  = 0
    $pfPeakMb  = 0
    if ($pf) {
        $pfAllocMb = ($pf | Measure-Object -Property AllocatedBaseSize -Sum).Sum
        $pfUsedMb  = ($pf | Measure-Object -Property CurrentUsage -Sum).Sum
        $pfPeakMb  = ($pf | Measure-Object -Property PeakUsage -Sum).Sum
    }
    
    # Processor CPU %
    $cpuPerf = Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor -Filter "Name='_Total'" -ErrorAction SilentlyContinue
    $cpuPct = 0
    if ($cpuPerf) {
        $cpuPct = [Math]::Round($cpuPerf.PercentProcessorTime, 1)
    }
    
    # MATLAB processes
    $matlabProcs = Get-Process -Name matlab -ErrorAction SilentlyContinue
    $procCount = 0
    $totalMatlabRssMb = 0
    $workerRssMb = 0
    $workerPeakRssMb = 0
    $workerMaxSingleRssMb = 0
    $workerPrivateMb = 0
    $parentRssMb = 0
    
    if ($matlabProcs) {
        $procCount = $matlabProcs.Count
        foreach ($p in $matlabProcs) {
            $wsMb = [Math]::Round($p.WorkingSet64 / 1MB, 1)
            $pwsMb = [Math]::Round($p.PeakWorkingSet64 / 1MB, 1)
            $privMb = [Math]::Round($p.PrivateMemorySize64 / 1MB, 1)
            $totalMatlabRssMb += $wsMb
            
            if ($ParentPid -gt 0 -and $p.Id -eq $ParentPid) {
                $parentRssMb = $wsMb
            } else {
                $workerRssMb += $wsMb
                $workerPeakRssMb += $pwsMb
                $workerPrivateMb += $privMb
                if ($wsMb -gt $workerMaxSingleRssMb) {
                    $workerMaxSingleRssMb = $wsMb
                }
            }
        }
        $totalMatlabRssMb = [Math]::Round($totalMatlabRssMb, 1)
        $workerRssMb = [Math]::Round($workerRssMb, 1)
        $workerPeakRssMb = [Math]::Round($workerPeakRssMb, 1)
        $workerMaxSingleRssMb = [Math]::Round($workerMaxSingleRssMb, 1)
        $workerPrivateMb = [Math]::Round($workerPrivateMb, 1)
    }
    
    $row = [PSCustomObject]@{
        timestamp_utc               = $nowUtc
        elapsed_s                   = $elapsed
        system_total_ram_mb         = $totalRamMb
        system_free_ram_mb          = $freeRamMb
        system_used_ram_mb          = $usedRamMb
        system_ram_pct              = $ramPct
        pagefile_allocated_mb       = $pfAllocMb
        pagefile_used_mb            = $pfUsedMb
        pagefile_peak_mb            = $pfPeakMb
        system_cpu_pct              = $cpuPct
        matlab_proc_count           = $procCount
        matlab_total_rss_mb         = $totalMatlabRssMb
        matlab_worker_rss_mb        = $workerRssMb
        matlab_worker_peak_rss_mb   = $workerPeakRssMb
        matlab_worker_max_single_rss_mb = $workerMaxSingleRssMb
        matlab_worker_private_mb    = $workerPrivateMb
        matlab_parent_rss_mb        = $parentRssMb
    }
    
    try {
        $row | Export-Csv -Path $CsvPath -NoTypeInformation -Append
    } catch {
        # Retry once after a brief yield if file is momentarily locked
        Start-Sleep -Milliseconds 100
        try { $row | Export-Csv -Path $CsvPath -NoTypeInformation -Append } catch {}
    }
    
    Start-Sleep -Seconds $IntervalSec
}
