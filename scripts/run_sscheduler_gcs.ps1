# run_sscheduler_gcs.ps1
# Usage (PowerShell as user): .\scripts\run_sscheduler_gcs.ps1
# Prompts for 'r' to continue, elevates to add firewall rule if needed, then starts sscheduler\sgcs.py
param()

function Prompt-Confirm {
    param([string]$msg = "Press 'r' to continue, anything else to cancel:")
    $k = Read-Host -Prompt $msg
    if ($k -ne 'r') { Write-Host 'Cancelled.'; exit 1 }
}

Prompt-Confirm

# Ensure script runs from repo root
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $scriptDir '..')

# Optionally add firewall rules (elevated)
# Required for end-to-end operation when the GCS is Windows with firewall enabled:
# - TCP 46000: PQC handshake server
# - UDP 46011: encrypted UDP receive socket on GCS
# - TCP 48080: sscheduler control server (drone connects here)

function Ensure-FirewallRule {
    param(
        [Parameter(Mandatory=$true)][string]$DisplayName,
        [Parameter(Mandatory=$true)][ValidateSet('TCP','UDP')][string]$Protocol,
        [Parameter(Mandatory=$true)][int]$LocalPort
    )

    $existing = Get-NetFirewallRule -DisplayName $DisplayName -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "Firewall rule exists: $DisplayName"
        return
    }

    Write-Host "Firewall rule '$DisplayName' not found. Requesting elevation to add inbound $Protocol port $LocalPort..."
    $cmd = "New-NetFirewallRule -DisplayName '$DisplayName' -Direction Inbound -LocalPort $LocalPort -Protocol $Protocol -Action Allow -Profile Any"
    Start-Process -Verb RunAs -FilePath powershell -ArgumentList "-NoProfile -Command \"$cmd\""
    Start-Sleep -Seconds 1
}

Ensure-FirewallRule -DisplayName 'secure-tunnel-gcs-handshake-46000-tcp' -Protocol TCP -LocalPort 46000
Ensure-FirewallRule -DisplayName 'secure-tunnel-gcs-encrypted-46011-udp' -Protocol UDP -LocalPort 46011
Ensure-FirewallRule -DisplayName 'secure-tunnel-gcs-sscheduler-48080-tcp' -Protocol TCP -LocalPort 48080

# Start sscheduler sgcs in this user session and write to log
$logDir = Join-Path (Get-Location) 'logs\sscheduler\gcs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$logFile = Join-Path $logDir "sgcs_$(Get-Date -Format 'yyyyMMdd-HHmmss').log"

Write-Host "Starting sscheduler.sgcs (log: $logFile)"
$py = "C:\Users\burak\miniconda3\envs\oqs-dev\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
& $py sscheduler\sgcs.py *> $logFile 2>&1 &
Write-Host "Started. Tail the log with: Get-Content -Wait $logFile"
