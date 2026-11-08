@echo off
echo =======================================================
echo   ChronoScheduler - One-Click Launcher
echo =======================================================
echo.

if exist "ChronoScheduler.exe" (
    echo [+] Launching ChronoScheduler.exe...
    ChronoScheduler.exe
    goto end
)

if exist "dist\ChronoScheduler.exe" (
    echo [+] Launching dist\ChronoScheduler.exe...
    dist\ChronoScheduler.exe
    goto end
)

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python or ChronoScheduler.exe not found!
    pause
    exit /b 1
)

echo [+] Starting ChronoScheduler via Python...
python src\cli.py demo

:end
pause
