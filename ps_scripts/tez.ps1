$token_file = "./data/cred/user_token.json"
# Get the current date and time
$currentTime = Get-Date

# Set the desired time threshold (8:30 AM)
$desiredTime = Get-Date -Year $currentTime.Year -Month $currentTime.Month -Day $currentTime.Day -Hour 8 -Minute 30 -Second 0

# Get the last write time of the file
$fileLastWriteTime = (Get-Item $token_file).LastWriteTime

# Compare the last write time with the desired time
if ($fileLastWriteTime -lt $desiredTime) {
    # Open the JSON file and update the susertoken value
    $jsonContent = Get-Content $token_file | ConvertFrom-Json
    $jsonContent.susertoken = ""
    $jsonContent | ConvertTo-Json | Set-Content $token_file
    
    Write-Host "susertoken updated successfully."
} else {
    Write-Host "File timestamp is not less than 8:30 AM today."
}
# Activate virtual environment (Windows)
Write-Host "Activating Virtual Environment.."
.\venv\Scripts\Activate.ps1

# Run the Python script within the virtual environment
Write-Host "Executing TeZ app in the virtual Environment.."
& ".\venv\Scripts\python.exe" tez_main.py
