#!/usr/bin/env pwsh
<#
.SYNOPSIS
    3-Phase MAVProxy-to-MAVProxy End-to-End Benchmark
    ================================================
    Runs 72 PQC cipher suites through the full tunnel (sdrone_bench -> sgcs_bench)
    in 3 phases:
      Phase 1: no-ddos      - baseline, no detector
      Phase 2: ddos-xgboost - old-style XGBoost detector running on Pi
      Phase 3: ddos-txt     - old-style TST detector running on Pi

    Results are saved to logs/benchmarks/runs/{no-ddos,ddos-xgboost,ddos-txt}/
    in the format the dashboard expects.

.PARAMETER IntervalSec
    Seconds per suite (default: 10)
.PARAMETER MaxSuites
    Limit number of suites (0 = all 72)
.PARAMETER SkipBaseline
    Skip the no-ddos baseline phase
.PARAMETER SkipXgb
    Skip the XGBoost detector phase
.PARAMETER SkipTst
    Skip the TST detector phase
.PARAMETER DroneSsh
    SSH target for the drone Pi (default: dev@100.101.93.23)
.PARAMETER CondaEnv
    Conda env name for GCS Python (default: oqs-dev)
#>
param(
    [int]$IntervalSec = 10,
    [int]$MaxSuites = 0,
    [switch]$SkipBaseline,
    [switch]$SkipXgb,
    [switch]$SkipTst,
    [string]$DroneSsh = "dev@100.101.93.23",
    [string]$CondaEnv = "oqs-dev",
    [string]$RunTag = $(Get-Date -Format "yyyyMMdd")
)

$ErrorActionPreference = 'Continue'

# ── Paths ────────────────────────────────────────────────────────────────────
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $RepoRoot

$DateTag = $RunTag
$RunsDir = Join-Path $RepoRoot "logs\benchmarks\runs\$DateTag"
$Scenarios = @("no-ddos", "ddos-xgboost", "ddos-txt")

# Detector paths on the Pi
$XgbDetector = "~/secure-tunnel/ddos/xgb_old.py"
$TstDetector = "~/secure-tunnel/ddos/tst_old.py"
$DetectorPython = "/home/dev/nenv/bin/python"
$DronePython = "/home/dev/cenv/bin/python"
$DroneRepo = "~/secure-tunnel"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  3-PHASE MAV-TO-MAV BENCHMARK (Old-Style DDoS Detectors)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Date       : $DateTag"
Write-Host "  Interval   : ${IntervalSec}s per suite"
Write-Host "  Max suites : $(if ($MaxSuites -eq 0) { 'ALL (72)' } else { $MaxSuites })"
Write-Host "  Drone SSH  : $DroneSsh"
Write-Host "  Output     : $RunsDir\{no-ddos,ddos-xgboost,ddos-txt}\"
Write-Host "  Phases     : $(if (!$SkipBaseline) {'baseline '})$(if (!$SkipXgb) {'xgboost '})$(if (!$SkipTst) {'tst'})"
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ── Helpers ──────────────────────────────────────────────────────────────────

function Test-SshConnection {
    Write-Host "  Testing SSH connection to $DroneSsh..." -NoNewline
    $result = ssh -o ConnectTimeout=10 $DroneSsh "echo OK" 2>&1
    if ($result -match "OK") {
        Write-Host " Connected" -ForegroundColor Green
        return $true
    }
    Write-Host " FAILED" -ForegroundColor Red
    return $false
}

function Kill-GcsProcesses {
    Write-Host "  Killing local Python/MAVProxy processes..." -NoNewline
    Get-Process -Name "python","python3","mavproxy" -ErrorAction SilentlyContinue | ForEach-Object {
        try { Stop-Process -Id $_.Id -Force } catch {}
    }
    Write-Host " done"
}

function Kill-DroneProcesses {
    Write-Host "  Killing drone-side Python/MAVProxy processes..." -NoNewline
    ssh -o ConnectTimeout=10 $DroneSsh "sudo pkill -f 'sdrone_bench|sgcs_bench|run_proxy|mavproxy|xgb_old|tst_old' 2>/dev/null; sleep 1" 2>&1 | Out-Null
    Write-Host " done"
}

function Start-Detector([string]$DetectorScript, [string]$Label) {
    Write-Host "  Starting $Label detector on drone..." -NoNewline
    ssh -o ConnectTimeout=10 $DroneSsh "cd $DroneRepo && sudo nohup $DetectorPython -u $DetectorScript > /tmp/detector_${Label}.log 2>&1 &" 2>&1 | Out-Null
    Start-Sleep -Seconds 3
    # Verify it started
    $check = ssh -o ConnectTimeout=10 $DroneSsh "pgrep -f '$DetectorScript' | head -1" 2>&1
    if ($check -and $check.Trim().Length -gt 0) {
        Write-Host " PID $($check.Trim())" -ForegroundColor Green
        return $true
    }
    Write-Host " FAILED" -ForegroundColor Red
    return $false
}

function Stop-Detector([string]$DetectorScript, [string]$Label) {
    Write-Host "  Stopping $Label detector..." -NoNewline
    ssh -o ConnectTimeout=10 $DroneSsh "sudo pkill -f '$DetectorScript' 2>/dev/null" 2>&1 | Out-Null
    Start-Sleep -Seconds 2
    Write-Host " done"
}

function Start-GcsBench([string]$Label) {
    Write-Host "  Starting GCS bench server (sgcs_bench, $Label)..." -NoNewline
    # Use direct Python exe from conda env - conda run strips console buffers
    $pyExe = "C:\Users\burak\miniconda3\envs\${CondaEnv}\python.exe"
    if (!(Test-Path $pyExe)) {
        Write-Host " FAILED (Python not found: $pyExe)" -ForegroundColor Red
        return $null
    }
    $gcsProc = Start-Process -FilePath $pyExe -ArgumentList @("-u", "-m", "sscheduler.sgcs_bench", "--no-gui", "--mode", "MAVPROXY") -WorkingDirectory $RepoRoot -PassThru -WindowStyle Minimized
    Start-Sleep -Seconds 5
    if ($gcsProc.HasExited) {
        Write-Host " FAILED (process exited)" -ForegroundColor Red
        return $null
    }
    # Verify port is open
    $portOk = Test-NetConnection 127.0.0.1 -Port 48080 -InformationLevel Quiet -WarningAction SilentlyContinue
    if (!$portOk) {
        Write-Host " FAILED (port 48080 not open)" -ForegroundColor Red
        return $null
    }
    Write-Host " PID $($gcsProc.Id)" -ForegroundColor Green
    return $gcsProc
}

function Stop-GcsBench($Proc) {
    if ($null -eq $Proc) { return }
    Write-Host "  Stopping GCS bench server..." -NoNewline
    try {
        # Kill the main python process (this also kills MAVProxy child via Job Object)
        Stop-Process -Id $Proc.Id -Force -ErrorAction SilentlyContinue
    } catch {}
    # Also kill any lingering python/mavproxy from this GCS session
    Start-Sleep -Seconds 2
    Get-Process -Name "python","mavproxy" -ErrorAction SilentlyContinue | ForEach-Object {
        try { Stop-Process -Id $_.Id -Force } catch {}
    }
    Start-Sleep -Seconds 2
    Write-Host " done"
}

function Collect-Results([string]$OutputDir, [string]$RemoteLogDir, [string]$Label) {
    <#
    .SYNOPSIS  Copy comprehensive JSONs from both drone (Pi) and GCS (local) to the output dir.
    #>
    Write-Host ""
    Write-Host "  Collecting results for $Label..." -ForegroundColor Yellow
    
    if (!(Test-Path $OutputDir)) {
        New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
    }
    
    $totalCopied = 0
    
    # ── 1. Drone-side comprehensive JSONs (SCP from Pi) ──
    Write-Host "  [1/2] Fetching drone JSONs from Pi..." -NoNewline
    # List remote files first (Windows scp doesn't glob well)
    $remoteFiles = ssh -o ConnectTimeout=10 $DroneSsh "ls ${RemoteLogDir}/comprehensive/*_drone.json 2>/dev/null" 2>&1
    if ($remoteFiles -and $LASTEXITCODE -eq 0) {
        foreach ($rf in ($remoteFiles -split "`n")) {
            $rf = $rf.Trim()
            if ($rf -and $rf -match '\.json$') {
                scp "${DroneSsh}:${rf}" "$OutputDir\" 2>&1 | Out-Null
                if ($LASTEXITCODE -eq 0) { $totalCopied++ }
            }
        }
    }
    Write-Host " $totalCopied drone files"
    
    # ── 2. GCS-side comprehensive JSONs (local live_run_*) ──
    Write-Host "  [2/2] Collecting GCS JSONs..." -NoNewline
    $gcsCopied = 0
    $liveRunBase = Join-Path $RepoRoot "logs\benchmarks"
    # Find the most recent live_run_* folder (the GCS overwrites LOGS_DIR to live_run_{drone_run_id})
    $latestLiveRun = Get-ChildItem $liveRunBase -Directory -Filter "live_run_*" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($latestLiveRun) {
        $gcsCompDir = Join-Path $latestLiveRun.FullName "comprehensive"
        if (Test-Path $gcsCompDir) {
            Get-ChildItem $gcsCompDir -Filter "*_gcs.json" -ErrorAction SilentlyContinue | ForEach-Object {
                Copy-Item $_.FullName -Destination $OutputDir -Force
                $gcsCopied++
            }
        }
    }
    Write-Host " $gcsCopied GCS files"
    
    $totalCopied += $gcsCopied
    
    # ── 3. Clean up remote phase dir ──
    ssh -o ConnectTimeout=10 $DroneSsh "sudo rm -rf $RemoteLogDir" 2>&1 | Out-Null
    
    # Clean up local live_run_* to avoid confusion next phase
    if ($latestLiveRun) {
        # Rename to mark as processed
        $archiveName = $latestLiveRun.Name + "_${Label}"
        Rename-Item $latestLiveRun.FullName -NewName $archiveName -ErrorAction SilentlyContinue
    }
    
    return $totalCopied
}

function Run-DroneBench([string]$OutputDir, [string]$Label) {
    $suitesArg = ""
    if ($MaxSuites -gt 0) {
        $suitesArg = "--max-suites $MaxSuites"
    }
    
    Write-Host ""
    Write-Host "  -- Running drone benchmark ($Label) --" -ForegroundColor Yellow
    Write-Host "  Output: $OutputDir"
    Write-Host "  Interval: ${IntervalSec}s | Suites: $(if ($MaxSuites -eq 0) { '72' } else { $MaxSuites })"
    Write-Host ""
    
    # Run sdrone_bench on Pi with --log-dir pointing to a phase-specific dir
    $remoteLogDir = "/home/dev/secure-tunnel/logs/benchmarks/phase_${Label}"
    $remoteLogFile = "/tmp/sdrone_bench_${Label}.log"
    
    # Clean up previous phase log/dir
    ssh -o ConnectTimeout=10 $DroneSsh "sudo rm -rf $remoteLogDir $remoteLogFile 2>/dev/null" 2>&1 | Out-Null
    
    $remoteCmd = "cd $DroneRepo && LIBOQS_PYTHON_DIR=/home/dev/quantum-safe/liboqs-python sudo -E $DronePython -u -m sscheduler.sdrone_bench --interval $IntervalSec $suitesArg --mode MAVPROXY --log-dir $remoteLogDir"
    
    Write-Host "  Remote command:" -ForegroundColor DarkGray
    Write-Host "    $remoteCmd" -ForegroundColor DarkGray
    Write-Host ""
    
    # Launch via nohup so it survives SSH disconnects
    Write-Host "  [SSH] Launching drone benchmark (detached)..." -ForegroundColor DarkGray
    ssh -o ConnectTimeout=10 $DroneSsh "nohup bash -c '$remoteCmd' > $remoteLogFile 2>&1 &" 2>&1 | Out-Null
    Start-Sleep -Seconds 5
    
    # Verify it started
    # NOTE: avoid matching the polling command itself by filtering out pgrep lines.
    $dronePid = (ssh -o ConnectTimeout=10 $DroneSsh "pgrep -af 'sscheduler.sdrone_bench.*--log-dir $remoteLogDir' | grep -v 'pgrep -af' | head -1 | cut -d' ' -f1" 2>&1) | Out-String
    $dronePid = $dronePid.Trim()
    if (!$dronePid -or $dronePid.Length -eq 0) {
        Write-Host "  ERROR: Drone benchmark failed to start" -ForegroundColor Red
        return 0
    }
    Write-Host "  [SSH] Drone benchmark running (PID: $dronePid)" -ForegroundColor Green
    
    # Poll for completion (check process + tail log)
    $maxWait = if ($MaxSuites -gt 0) { $MaxSuites * ($IntervalSec + 15) + 120 } else { 72 * ($IntervalSec + 15) + 120 }
    $elapsed = 0
    $pollInterval = 30
    
    while ($elapsed -lt $maxWait) {
        Start-Sleep -Seconds $pollInterval
        $elapsed += $pollInterval
        
        # Check if process still running
        $running = (ssh -o ConnectTimeout=10 $DroneSsh "pgrep -af 'sscheduler.sdrone_bench.*--log-dir $remoteLogDir' | grep -v 'pgrep -af' | head -1 | cut -d' ' -f1" 2>&1) | Out-String
        $running = $running.Trim()
        
        # Show latest progress from log
        $lastLine = ssh -o ConnectTimeout=10 $DroneSsh "grep -oP '\[\d+\.\d+%\].*|Handshake OK.*|Benchmark complete.*|ERROR.*' $remoteLogFile 2>/dev/null | tail -3" 2>&1
        if ($lastLine) {
            foreach ($line in ($lastLine -split "`n")) {
                $line = $line.Trim()
                if ($line.Length -gt 0) {
                    Write-Host "  [DRONE ${elapsed}s] $line"
                }
            }
        }
        
        if (!$running -or $running.Length -eq 0) {
            Write-Host "  [SSH] Drone benchmark finished (${elapsed}s elapsed)" -ForegroundColor Green
            break
        }
    }
    
    if ($elapsed -ge $maxWait) {
        Write-Host "  WARNING: Drone benchmark timed out after ${maxWait}s" -ForegroundColor Red
        ssh -o ConnectTimeout=10 $DroneSsh "sudo pkill -f 'sscheduler.sdrone_bench.*--log-dir $remoteLogDir' 2>/dev/null" 2>&1 | Out-Null
    }
    
    # Show final summary
    $summary = ssh -o ConnectTimeout=10 $DroneSsh "grep -E 'Benchmark complete|Summary saved|Shutdown' $remoteLogFile 2>/dev/null | tail -5" 2>&1
    if ($summary) {
        foreach ($line in ($summary -split "`n")) {
            Write-Host "  [DRONE] $($line.Trim())"
        }
    }
    # Collect results from both drone and GCS
    $count = Collect-Results -OutputDir $OutputDir -RemoteLogDir $remoteLogDir -Label $Label
    
    $localCount = (Get-ChildItem -Path $OutputDir -Filter "*_drone.json" -ErrorAction SilentlyContinue).Count
    Write-Host ""
    Write-Host "  Suite results: $localCount drone JSONs, $count total files" -ForegroundColor $(if ($localCount -ge 72) { "Green" } elseif ($localCount -gt 0) { "Yellow" } else { "Red" })
    
    return $localCount
}

# ── Pre-flight checks ───────────────────────────────────────────────────────

Write-Host "── Pre-flight checks ──" -ForegroundColor Yellow
if (!(Test-SshConnection)) {
    Write-Host "ERROR: Cannot reach drone. Check Tailscale/SSH." -ForegroundColor Red
    exit 1
}

# Kill everything for a clean start
Kill-GcsProcesses
Kill-DroneProcesses

# Archive old run data if it exists
foreach ($scenario in $Scenarios) {
    $scenarioDir = Join-Path $RunsDir $scenario
    if ((Test-Path $scenarioDir) -and (Get-ChildItem $scenarioDir -Filter "*.json" -ErrorAction SilentlyContinue).Count -gt 0) {
        $archiveDir = Join-Path $scenarioDir "_archived_${DateTag}"
        Write-Host "  Archiving old $scenario data -> _archived_${DateTag}/"
        if (!(Test-Path $archiveDir)) {
            New-Item -ItemType Directory -Path $archiveDir -Force | Out-Null
        }
        Get-ChildItem $scenarioDir -Filter "*.json" | Move-Item -Destination $archiveDir -Force
        Get-ChildItem $scenarioDir -Filter "*.jsonl" -ErrorAction SilentlyContinue | Move-Item -Destination $archiveDir -Force
    }
}

Write-Host "  Pre-flight checks complete." -ForegroundColor Green
Write-Host ""

# ── Phase 1: Baseline (no DDoS) ─────────────────────────────────────────────

if (!$SkipBaseline) {
    $phaseStart = Get-Date
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host "  PHASE 1: BASELINE (no DDoS detector)" -ForegroundColor Cyan
    Write-Host "================================================================" -ForegroundColor Cyan
    
    $outputDir = Join-Path $RunsDir "no-ddos"
    
    $gcsProc = Start-GcsBench -Label "no-ddos"
    if ($null -ne $gcsProc) {
        $count = Run-DroneBench -OutputDir $outputDir -Label "no-ddos"
        Stop-GcsBench -Proc $gcsProc
        Kill-DroneProcesses
        
        $elapsed = ((Get-Date) - $phaseStart).TotalMinutes
        Write-Host ""
        Write-Host "  Phase 1 complete: $count suites in $([math]::Round($elapsed, 1)) min" -ForegroundColor Green
    } else {
        Write-Host "  Phase 1 SKIPPED - GCS failed to start" -ForegroundColor Red
    }
    
    # Cool-down between phases
    Write-Host "  Cooling down 30s between phases..."
    Start-Sleep -Seconds 30
}

# ── Phase 2: + XGBoost ──────────────────────────────────────────────────────

if (!$SkipXgb) {
    $phaseStart = Get-Date
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host "  PHASE 2: + XGBoost (old-style 3-thread busy-wait)" -ForegroundColor Cyan
    Write-Host "================================================================" -ForegroundColor Cyan
    
    $outputDir = Join-Path $RunsDir "ddos-xgboost"
    
    # Start XGBoost detector first
    $detectorOk = Start-Detector -DetectorScript $XgbDetector -Label "xgb"
    if ($detectorOk) {
        Write-Host "  Waiting 5s for XGBoost warm-up..."
        Start-Sleep -Seconds 5
        
        $gcsProc = Start-GcsBench -Label "ddos-xgboost"
        if ($null -ne $gcsProc) {
            $count = Run-DroneBench -OutputDir $outputDir -Label "ddos-xgboost"
            Stop-GcsBench -Proc $gcsProc
        } else {
            Write-Host "  Phase 2 SKIPPED - GCS failed to start" -ForegroundColor Red
        }
        
        Stop-Detector -DetectorScript $XgbDetector -Label "xgb"
        Kill-DroneProcesses
        
        $elapsed = ((Get-Date) - $phaseStart).TotalMinutes
        Write-Host ""
        Write-Host "  Phase 2 complete: $count suites in $([math]::Round($elapsed, 1)) min" -ForegroundColor Green
    } else {
        Write-Host "  Phase 2 SKIPPED - detector failed to start" -ForegroundColor Red
    }
    
    # Cool-down
    Write-Host "  Cooling down 30s between phases..."
    Start-Sleep -Seconds 30
}

# ── Phase 3: + TST ──────────────────────────────────────────────────────────

if (!$SkipTst) {
    $phaseStart = Get-Date
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host "  PHASE 3: + TST (old-style continuous inference loop)" -ForegroundColor Cyan
    Write-Host "================================================================" -ForegroundColor Cyan
    
    $outputDir = Join-Path $RunsDir "ddos-txt"
    
    # Start TST detector first
    $detectorOk = Start-Detector -DetectorScript $TstDetector -Label "tst"
    if ($detectorOk) {
        # TST needs longer warm-up (loading data, creating sequences)
        Write-Host "  Waiting 30s for TST warm-up (model + DataLoader init)..."
        Start-Sleep -Seconds 30
        
        $gcsProc = Start-GcsBench -Label "ddos-txt"
        if ($null -ne $gcsProc) {
            $count = Run-DroneBench -OutputDir $outputDir -Label "ddos-txt"
            Stop-GcsBench -Proc $gcsProc
        } else {
            Write-Host "  Phase 3 SKIPPED - GCS failed to start" -ForegroundColor Red
        }
        
        Stop-Detector -DetectorScript $TstDetector -Label "tst"
        Kill-DroneProcesses
        
        $elapsed = ((Get-Date) - $phaseStart).TotalMinutes
        Write-Host ""
        Write-Host "  Phase 3 complete: $count suites in $([math]::Round($elapsed, 1)) min" -ForegroundColor Green
    } else {
        Write-Host "  Phase 3 SKIPPED - detector failed to start" -ForegroundColor Red
    }
}

# ── Summary ──────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  BENCHMARK COMPLETE" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

foreach ($scenario in $Scenarios) {
    $dir = Join-Path $RunsDir $scenario
    $count = 0
    if (Test-Path $dir) {
        $count = (Get-ChildItem $dir -Filter "*.json" -ErrorAction SilentlyContinue | Where-Object { $_.Name -notlike "_archived*" }).Count
    }
    $status = $(if ($count -ge 72) { "OK" } elseif ($count -gt 0) { "PARTIAL" } else { "EMPTY" })
    $color = $(if ($count -ge 72) { "Green" } elseif ($count -gt 0) { "Yellow" } else { "Red" })
    Write-Host "  $scenario : $count files [$status]" -ForegroundColor $color
}

Write-Host ""
Write-Host "  Results: $RunsDir" -ForegroundColor Cyan
Write-Host "  Restart dashboard to see new data:" -ForegroundColor Cyan
Write-Host "    cd dashboard\backend; conda run -n $CondaEnv python serve.py" -ForegroundColor DarkGray
Write-Host ""
