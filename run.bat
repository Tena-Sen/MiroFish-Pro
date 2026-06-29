@echo off
cd /d "%~dp0"
where powershell >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: PowerShell not found.
    pause
    exit /b 1
)
echo Starting MiroFish...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1"
pause
