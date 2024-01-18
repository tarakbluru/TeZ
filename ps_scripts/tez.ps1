# Activate virtual environment (Windows)
Write-Host "Activating Virtual Environment.."
.\venv\Scripts\Activate.ps1

# Run the Python script within the virtual environment
Write-Host "Executing TeZ app in the virtual Environment.."
& ".\venv\Scripts\python.exe" tez_main.py
