function Show-Help {
    Write-Host "Usage: script.ps1 [-noDeleteFiles]"
    Write-Host "Deletes log files in the specified folder if their modified timestamp is earlier than 8:30 AM."
    Write-Host "Optional arguments:"
    Write-Host "  -noDeleteFiles    : Prevents deletion of log files (default behavior is to delete files)."
}

# Check if -h or -help argument is provided
if ($args -contains "-help" -or $args -contains "-h") {
    Show-Help
    exit
}

# Define the default value for the deleteFiles switch
$deleteFiles = !$args.Contains("-noDeleteFiles")

# Define the path to the sys_cfg.yml file
$sysCfgFilePath = "./data/sys_cfg.yml"

# Read the sys_cfg.yml file as text
$sysCfgContent = Get-Content -Path $sysCfgFilePath

# Extract the LOG_FILE key from the sys_cfg.yml
$logFilePath = $sysCfgContent | Select-String -Pattern 'LOG_FILE:' | ForEach-Object { $_ -replace 'LOG_FILE:', '' }

# Remove any leading or trailing whitespace
$logFilePath = $logFilePath.Trim()

# Remove single quotes from the file path
$logFilePath = $logFilePath -replace "'", ""

# Extract the folder path from the LOG_FILE value
$logFolderPath = Split-Path -Path $logFilePath -Parent

Write-Host "logFilePath: $logFilePath"
Write-Host "logFolderPath: $logFolderPath"

# Get the current date
$currentDate = Get-Date

# Set the time threshold to 8:30 AM
$timeThreshold = Get-Date -Year $currentDate.Year -Month $currentDate.Month -Day $currentDate.Day -Hour 8 -Minute 30 -Second 0

# Get the files in the log folder with extensions .log, .txt, and .csv
$files = Get-ChildItem -Path $logFolderPath

# Loop through each file
foreach ($file in $files) {
    # Check if the file is a .log, .txt, or .csv file
    if ($file.Extension -match '\.log$|\.txt$|\.csv$') {
        # Check if the last modified time is less than 8:30 AM
        if ($file.LastWriteTime -lt $timeThreshold) {
            # Check if the deleteFiles switch is set to $true
            if ($deleteFiles) {
                # Delete the file
                Remove-Item $file.FullName -Force
                Write-Host "Deleted $($file.FullName)"
            } else {
                Write-Host "Would delete $($file.FullName)"
            }
        }
    }
}

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