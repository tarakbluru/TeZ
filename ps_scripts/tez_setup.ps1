# Set the Dropbox direct download link
$url = "https://drive.usercontent.google.com/download?id=1v0O9pD9ub9pfPSuxqwqjwhQ1yuN1kxOx&export=download&authuser=0&confirm=t&uuid=71cd7c19-5e34-4f81-b8ec-df8d69c22f9b&at=APZUnTUl8ap1WyyK3zEN6me-YKFK:1713088490345"

# Set the path where you want to save the downloaded file
$destinationPath = "log\NorenRestApiPy-0.0.22-py2.py3-none-any.whl"

# Create the log folder if it doesn't exist
New-Item -ItemType Directory -Force -Path "log"

# Download the file using Invoke-WebRequest
Invoke-WebRequest -Uri $url -OutFile $destinationPath

$originalHash = "EC7D35DD671EE919AD16BB158FDBE51322444A0FAD2ACC60A24E45DD7C1BF025"

# Check if the file was downloaded successfully
if (Test-Path $destinationPath) {
    Write-Output "File downloaded successfully to $destinationPath"
    $downloadedHash = Get-FileHash -Path $destinationPath -Algorithm SHA256
    if ($originalHash -eq $downloadedHash.Hash) {
        Write-Output "Downloaded file hash matches the original hash. The file is intact."
    }
    else {
        Write-Output "Downloaded file hash does not match the original hash. The file may be corrupted."
    }

} else {
    Write-Output "Failed to download the file"
}

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


