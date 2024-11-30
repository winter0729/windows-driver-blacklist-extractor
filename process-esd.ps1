# process-esd.ps1
param (
    [string]$WorkingDir = "."
)

$ErrorActionPreference = "Stop"

# Create directories
$outputDir = Join-Path $WorkingDir "output"
$tempDir = Join-Path $WorkingDir "temp"
New-Item -ItemType Directory -Force -Path $outputDir, $tempDir | Out-Null

$esdPath = Join-Path $tempDir "metadata.esd"
$targetFile = "3\Windows\System32\CodeIntegrity\driversipolicy.p7b"
$sevenZipPath = Join-Path $tempDir "7zr.exe"

try {
    Write-Host "Downloading 7zr.exe..."
    $7zrUrl = "https://7-zip.org/a/7zr.exe"
    Invoke-WebRequest -Uri $7zrUrl -OutFile $sevenZipPath

    Write-Host "Extracting driversipolicy.p7b using 7zr..."
    $extractCmd = "& `"$sevenZipPath`" e `"$esdPath`" `"$targetFile`" -o`"$outputDir`" -y"
    Invoke-Expression $extractCmd
    if ($LASTEXITCODE -ne 0) { throw "7-Zip extraction failed" }

    # Cleanup
    Write-Host "Cleaning up..."
    Remove-Item -Path $esdPath -Force
    Remove-Item -Path $sevenZipPath -Force
    
    Write-Host "Process completed successfully!"
}
catch {
    Write-Error "Error: $_"
    exit 1
}