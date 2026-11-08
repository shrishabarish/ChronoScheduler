@echo off
echo =======================================================
echo   ChronoScheduler - Windows 2-File Release Builder
echo =======================================================
echo.

:: 1. Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in system PATH!
    echo Please install Python 3.9+ from https://python.org
    pause
    exit /b 1
)

echo [+] Step 1/3: Installing PyInstaller and dependencies...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo [+] Step 2/3: Compiling code into a single standalone .exe (no source code required)...
pyinstaller --onefile --noconfirm ^
    --name ChronoScheduler ^
    --add-data "data;data" ^
    --add-data "frontend;frontend" ^
    --hidden-import "psutil" ^
    --hidden-import "sqlite3" ^
    --hidden-import "asyncio" ^
    src/cli.py

echo.
if exist "dist\ChronoScheduler.exe" (
    echo [+] Step 3/3: Creating clean 2-file Release Package...
    if exist "release" rmdir /s /q "release"
    mkdir "release"
    
    :: Copy ONLY the 2 necessary files:
    copy "dist\ChronoScheduler.exe" "release\ChronoScheduler.exe" >nul
    copy "frontend\index.html" "release\Dashboard.html" >nul
    
    :: Create clean zip containing ONLY the 2 files using PowerShell
    powershell -Command "Compress-Archive -Path 'release\*' -DestinationPath 'ChronoScheduler_Release.zip' -Force"
    
    echo.
    echo =======================================================
    echo  [SUCCESS] 2-File Release Created Successfully!
    echo =======================================================
    echo.
    echo  Folder : release\
    echo           ├── ChronoScheduler.exe   (Compiled Standalone Binary)
    echo           └── Dashboard.html        (Web Control Dashboard)
    echo.
    echo  Zip    : ChronoScheduler_Release.zip (Contains ONLY the 2 files)
    echo.
    echo  NO source code files are included. You can send this
    echo  directly to testers!
    echo =======================================================
) else (
    echo [ERROR] PyInstaller compilation failed.
)

pause
