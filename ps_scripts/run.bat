@echo off
echo Starting batch file...

REM Check if the "venv" directory exists
if not exist "venv" (
    echo "venv folder not found. Running tez_setup.ps1 PowerShell script..."
    powershell -ExecutionPolicy Bypass -File .\ps_scripts\tez_setup.ps1
) else (
    echo "venv folder found. Skipping tez_setup.ps1 PowerShell script."
)

echo Prompting user for input...

REM Prompt the user to run tez.ps1 PowerShell script
set /p runTez="Do you want to run tez.ps1 PowerShell script? (y/n): "

echo User input: %runTez%

REM Check the user's response
if /i "%runTez%"=="y" (
    echo "Running tez.ps1 PowerShell script..."
    powershell -ExecutionPolicy Bypass -File .\ps_scripts\tez.ps1
) else (
    echo "Skipped running tez.ps1 PowerShell script."
)
