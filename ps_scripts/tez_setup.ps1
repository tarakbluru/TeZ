$pythonVersion = python --version 2>&1 | Select-String -Pattern 'Python (\d+\.\d+\.\d+)' | ForEach-Object { $_.Matches.Groups[1].Value }

if ([version]$pythonVersion -ge [version]"3.10.5") {
    Write-Host "Python version is 3.10.5 or more recent."

    # Create virtual environment
    Write-Host "Creating Virtual Environment.."
    python -m venv venv

    # Activate virtual environment (Windows)
    Write-Host "Activating Virtual Environment.."
    .\venv\Scripts\Activate.ps1

    # Check if pip is from the virtual environment
    $pipSource = (Get-Command pip).Source
    if ($pipSource -like "*venv*") {
        Write-Host "Pip is from the virtual environment."
    } else {
        Write-Host "Pip is not from the virtual environment. Please activate the virtual environment."
        exit 1
    }

    Write-Host "Installing dependencies for TeZ App in the virtual environment.."
    # Install dependencies
    & ".\venv\scripts\pip.exe" install -r .\requirements.txt

} else {
    Write-Host "Python version $pythonVersion is less than 3.10.5."
}


