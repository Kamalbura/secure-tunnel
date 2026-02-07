<#
.SYNOPSIS
    Launches the PQC Forensic Dashboard - Backend (FastAPI) + Frontend (Vite React) in parallel.

.DESCRIPTION
    - Kills any existing processes on ports 8000 (backend) and 5173 (frontend)
    - Activates the conda oqs-dev environment
    - Starts uvicorn backend in a new terminal window
    - Starts Vite frontend in a new terminal window
    - Waits for both to become healthy
    - Opens the dashboard in the default browser

.USAGE
    .\start-dashboard.ps1            # normal start
    .\start-dashboard.ps1 -Kill      # kill existing dashboard processes only
#>

param(
    [switch]$Kill
)

$ErrorActionPreference = "Continue"
$ROOT      = Split-Path -Parent $MyInvocation.MyCommand.Definition
$BACKEND   = Join-Path $ROOT "dashboard\backend"
$FRONTEND  = Join-Path $ROOT "dashboard\frontend"

$BACKEND_PORT  = 8000
$FRONTEND_PORT = 5173

# ── Helpers ──────────────────────────────────────────────────────────────────

function Write-Banner($msg) {
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor Cyan
    Write-Host "  $msg" -ForegroundColor White
    Write-Host ("=" * 60) -ForegroundColor Cyan
}

function Kill-PortProcess($port) {
    $items = netstat -ano | Select-String ":$port\s" |
        ForEach-Object { ($_ -replace '.*\s(\d+)$','$1').Trim() } |
        Sort-Object -Unique |
        Where-Object { $_ -ne '0' -and $_ -ne '' }

    foreach ($procId in $items) {
        try {
            $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
            if ($p) {
                Write-Host "  Killing PID $procId ($($p.ProcessName)) on port $port" -ForegroundColor Yellow
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            }
        } catch { }
    }
}

function Wait-ForPort($port, $label, $timeoutSec = 30) {
    Write-Host "  Waiting for $label on port $port..." -ForegroundColor Gray -NoNewline
    $elapsed = 0
    while ($elapsed -lt $timeoutSec) {
        try {
            $tcp = New-Object System.Net.Sockets.TcpClient
            $tcp.Connect("127.0.0.1", $port)
            $tcp.Close()
            Write-Host " Ready!" -ForegroundColor Green
            return $true
        } catch {
            Start-Sleep -Milliseconds 500
            $elapsed += 0.5
            Write-Host "." -NoNewline -ForegroundColor Gray
        }
    }
    Write-Host " TIMEOUT" -ForegroundColor Red
    return $false
}

# ── Step 1: Kill existing processes ──────────────────────────────────────────

Write-Banner "PQC Forensic Dashboard Launcher"

Write-Host ""
Write-Host "Clearing ports $BACKEND_PORT and $FRONTEND_PORT..." -ForegroundColor Cyan
Kill-PortProcess $BACKEND_PORT
Kill-PortProcess $FRONTEND_PORT
Start-Sleep -Seconds 1

if ($Kill) {
    Write-Host ""
    Write-Host "Ports cleared. Exiting (-Kill mode)." -ForegroundColor Green
    exit 0
}

# ── Step 2: Write temp launcher scripts (avoids all quoting issues) ──────────

$tmpDir = Join-Path $env:TEMP "pqc-dashboard"
if (-not (Test-Path $tmpDir)) { New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null }

$backendScript = Join-Path $tmpDir "start-backend.ps1"
$backendContent = "Set-Location -LiteralPath '$BACKEND'" + "`r`n"
$backendContent += "conda activate oqs-dev" + "`r`n"
$backendContent += "Write-Host '--- Backend starting on port $BACKEND_PORT ---' -ForegroundColor Cyan" + "`r`n"
$backendContent += "python -m uvicorn main:app --host 0.0.0.0 --port $BACKEND_PORT" + "`r`n"
Set-Content -Path $backendScript -Value $backendContent -Encoding ASCII

$frontendScript = Join-Path $tmpDir "start-frontend.ps1"
$frontendContent = "Set-Location -LiteralPath '$FRONTEND'" + "`r`n"
$frontendContent += "Write-Host '--- Frontend dev server starting on port $FRONTEND_PORT ---' -ForegroundColor Cyan" + "`r`n"
$frontendContent += "npm run dev" + "`r`n"
Set-Content -Path $frontendScript -Value $frontendContent -Encoding ASCII

# ── Step 3: Start Backend ────────────────────────────────────────────────────

Write-Host ""
Write-Host "Starting Backend (FastAPI + uvicorn) on port $BACKEND_PORT..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-File", $backendScript -WindowStyle Normal

# ── Step 4: Start Frontend ───────────────────────────────────────────────────

Write-Host "Starting Frontend (Vite + React) on port $FRONTEND_PORT..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-File", $frontendScript -WindowStyle Normal

# ── Step 5: Wait for both servers ────────────────────────────────────────────

Write-Host ""
Write-Host "Waiting for servers to become ready..." -ForegroundColor Cyan

$backendOk  = Wait-ForPort $BACKEND_PORT  "Backend"  45
$frontendOk = Wait-ForPort $FRONTEND_PORT "Frontend" 60

# ── Step 6: Open browser ────────────────────────────────────────────────────

if ($backendOk -and $frontendOk) {
    Write-Host ""
    Write-Banner "Dashboard Ready!"
    Write-Host ""
    Write-Host "  Frontend : http://localhost:$FRONTEND_PORT" -ForegroundColor White
    Write-Host "  Backend  : http://localhost:$BACKEND_PORT" -ForegroundColor White
    Write-Host "  API Docs : http://localhost:$BACKEND_PORT/docs" -ForegroundColor White
    Write-Host ""

    Start-Sleep -Seconds 1
    Start-Process "http://localhost:$FRONTEND_PORT"

    Write-Host "  Browser opened. Both terminals are running - close them to stop." -ForegroundColor Gray
} else {
    Write-Host ""
    Write-Host "Not all servers started successfully." -ForegroundColor Yellow
    if (-not $backendOk)  { Write-Host "  Backend failed to start"  -ForegroundColor Red }
    if (-not $frontendOk) { Write-Host "  Frontend failed to start" -ForegroundColor Red }
    Write-Host "  Check the terminal windows for errors." -ForegroundColor Gray
}

Write-Host ""
