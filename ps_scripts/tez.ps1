$Base_path = ""
$Base_folder = $Base_path+""

# Set the virtual environment path
$venvPath = $Base_path+"venv"

# Activate the virtual environment
$activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
. $activateScript

# Run the Python script within the virtual environment
& "$venvPath\Scripts\python.exe" "$Base_folder\tez_main.py"
