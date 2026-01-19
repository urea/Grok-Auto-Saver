@echo off
echo ========================================================
echo  Grok Organizer Build Script
echo ========================================================

echo.
echo Installing requirements...
pip install -r requirements.txt 2>nul
if %errorlevel% neq 0 (
    echo [Info] paramiko or other libs might be missing, but standard lib usually enough.
    echo Proceeding...
)

echo.
echo Building EXE...
pyinstaller --noconfirm --onefile --console --name "Grok Organizer" --clean "grok_organizer.py"

if %errorlevel% equ 0 (
    echo.
    echo Moving EXE to current folder...
    move /Y "dist\Grok Organizer.exe" .
    rmdir /S /Q dist
    rmdir /S /Q build
    del "Grok Organizer.spec"

    echo.
    echo ========================================================
    echo  Build SUCCESS!
    echo  Executable is located in this folder.
    echo ========================================================
    pause
) else (
    echo.
    echo ========================================================
    echo  Build FAILED.
    echo ========================================================
    pause
)
