# ============================================================
# MiroFish - Windows 一键启动脚本 (PowerShell)
# 双击即可运行，固定端口 5001(后端) / 3000(前端)
# ============================================================

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ScriptDir = $PSScriptRoot
$BackendDir = Join-Path $ScriptDir "backend"
$FrontendDir = Join-Path $ScriptDir "frontend"
$EnvFile = Join-Path $ScriptDir ".env"

$BACKEND_PORT = 5001
$FRONTEND_PORT = 3000

# ---------- 辅助函数 ----------

function Write-Info($msg) { Write-Host "  [INFO] $msg" -ForegroundColor Gray }
function Write-Ok($msg) { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  [WARN] $msg" -ForegroundColor DarkYellow }
function Write-Err($msg) { Write-Host "  [ERROR] $msg" -ForegroundColor Red }

function Kill-ProcessesOnPort($port) {
    # 杀掉占用指定端口的 Windows 进程
    $lines = netstat -ano | Select-String ":$port\s"
    if ($lines) {
        foreach ($line in $lines) {
            $parts = $line.Line -split '\s+'
            $targetPid = $parts[$parts.Length - 1]
            if ($targetPid -match '^\d+$') {
                try {
                    $proc = Get-Process -Id ([int]$targetPid) -ErrorAction SilentlyContinue
                    if ($proc) {
                        Stop-Process -Id ([int]$targetPid) -Force -ErrorAction Stop
                        Write-Warn "Killed process (PID $targetPid) on port $port"
                    }
                } catch {
                    Write-Warn "Failed to kill PID $targetPid on port $port"
                }
            }
        }
    }
}

function Find-ProcessOnPort($port) {
    # 使用 Windows 原生 API 检测，避免 WSL2 netstat 干扰
    try {
        $socket = [System.Net.Sockets.TcpClient]::new()
        $socket.Connect("127.0.0.1", $port) | Out-Null
        $socket.Close()
        return $true
    } catch {
        return $false
    }
}

# ============================================================
# 主流程
# ============================================================

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  MiroFish Startup" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# 0. 检查依赖
Write-Host "[1/6] Checking dependencies..." -ForegroundColor Yellow

# Try system Python first; fall back to uv-managed Python.
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $uvForPython = Get-Command uv -ErrorAction SilentlyContinue
    if ($uvForPython) {
        $uvPython = & uv python find 2>$null
        if ($uvPython -and (Test-Path $uvPython)) {
            $python = Get-Command $uvPython -ErrorAction SilentlyContinue
        }
    }
}
if (-not $python) {
    Write-Err "Python not found. Please install Python >=3.11 or uv (https://docs.astral.sh/uv/)."
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Ok "Python: $($python.Source)"

$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    Write-Err "uv not found. Install with: pip install uv"
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Ok "uv: $($uv.Source)"

$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) {
    Write-Err "Node.js not found. Please install Node.js >=18."
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Ok "Node: $($node.Source)"
Write-Host ""

# 0.5 杀掉所有旧 MiroFish 进程
Write-Host "[0.5] Cleaning old processes..." -ForegroundColor Yellow
# 杀掉包含 MiroFish 的 Python 和 Node 进程
Get-Process | Where-Object {
    -not [string]::IsNullOrEmpty($_.Path) -and
    ($_.ProcessName -eq 'python' -or $_.ProcessName -eq 'node' -or $_.ProcessName -eq 'node.exe') -and
    ($_.Path -like '*MiroFish*')
} | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Write-Ok "Old processes cleaned."
Write-Host ""

# 1. 检查 .env
Write-Host "[2/6] Checking .env..." -ForegroundColor Yellow

if (-not (Test-Path $EnvFile)) {
    $exampleEnv = Join-Path $ScriptDir ".env.example"
    if (Test-Path $exampleEnv) {
        Copy-Item $exampleEnv $EnvFile
        Write-Info "Created .env - please edit it with your API keys."
        Read-Host "Press Enter to exit"
        exit 1
    } else {
        Write-Err ".env not found. Please create one."
        Read-Host "Press Enter to exit"
        exit 1
    }
}
Write-Ok ".env exists."
Write-Host ""

# 2. 检查是否已有服务在运行（防止重复启动）
Write-Host "[3/6] Checking running services..." -ForegroundColor Yellow

$pidsOnPort = Find-ProcessOnPort $BACKEND_PORT
if ($pidsOnPort) {
    Write-Err "Backend is already running on port $BACKEND_PORT!"
    Read-Host "Press Enter to exit"
    exit 1
}

$pidsOnPort = Find-ProcessOnPort $FRONTEND_PORT
if ($pidsOnPort) {
    Write-Err "Frontend is already running on port $FRONTEND_PORT!"
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Ok "No other services running."
Write-Host ""

# 3. 安装前端依赖
Write-Host "[4/6] Checking frontend dependencies..." -ForegroundColor Yellow

$frontNM = Join-Path $FrontendDir "node_modules"
if (Test-Path $frontNM) {
    Write-Info "Frontend dependencies already installed, skipping."
} else {
    Write-Info "Installing frontend dependencies..."
    Set-Location $FrontendDir
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Err "npm install failed with exit code $LASTEXITCODE"
        Set-Location $ScriptDir
        Read-Host "Press Enter to exit"
        exit 1
    }
    Set-Location $ScriptDir
}
Write-Host ""

# 4. 安装后端依赖
Write-Host "[5/6] Checking backend dependencies..." -ForegroundColor Yellow

$backVenv = Join-Path $BackendDir ".venv"
if (Test-Path $backVenv) {
    Write-Info "Backend dependencies already installed, skipping."
} else {
    Write-Info "Installing backend dependencies..."
    Set-Location $BackendDir
    uv sync
    if ($LASTEXITCODE -ne 0) {
        Write-Err "uv sync failed with exit code $LASTEXITCODE"
        Set-Location $ScriptDir
        Read-Host "Press Enter to exit"
        exit 1
    }
    Set-Location $ScriptDir
}
Write-Host ""

# 6. 确保端口干净（杀旧进程）
Write-Host "[6/6] Ensuring ports are clean..." -ForegroundColor Yellow

if (Find-ProcessOnPort $BACKEND_PORT) {
    Write-Info "Killing process on port $BACKEND_PORT..."
    Kill-ProcessesOnPort $BACKEND_PORT
    Start-Sleep -Seconds 1
}
if (Find-ProcessOnPort $FRONTEND_PORT) {
    Write-Info "Killing process on port $FRONTEND_PORT..."
    Kill-ProcessesOnPort $FRONTEND_PORT
    Start-Sleep -Seconds 1
}

# 再次确认端口可用
if (Find-ProcessOnPort $BACKEND_PORT) {
    Write-Err "Port $BACKEND_PORT is still occupied after cleanup!"
    Read-Host "Press Enter to exit"
    exit 1
}
if (Find-ProcessOnPort $FRONTEND_PORT) {
    Write-Err "Port $FRONTEND_PORT is still occupied after cleanup!"
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Ok "Ports $BACKEND_PORT and $FRONTEND_PORT are clean."
Write-Host ""

# ============================================================
# 启动服务
# ============================================================

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  Starting MiroFish" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Backend:  http://localhost:$BACKEND_PORT" -ForegroundColor Green
Write-Host "  Frontend: http://localhost:$FRONTEND_PORT" -ForegroundColor Green
Write-Host ""
Write-Host "  Press Ctrl+C to stop all services." -ForegroundColor Gray
Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# 使用 concurrently 并行启动
Set-Location $ScriptDir
npm run dev

Write-Host ""
Write-Host "Services stopped." -ForegroundColor Gray
Read-Host "Press Enter to exit"
