# process-esd.ps1
param (
    [string]$WorkingDir = "."
)

$ErrorActionPreference = "Stop"

# Create directories
$tempDir = Join-Path $WorkingDir "temp"
$outputDir = Join-Path $WorkingDir "output"
$logDir = Join-Path $outputDir "logs"
$mountDir = Join-Path $outputDir "mount"

New-Item -ItemType Directory -Force -Path $outputDir, $logDir, $mountDir | Out-Null

$esdPath = Join-Path $tempDir "metadata.esd"
$wimPath = Join-Path $outputDir "converted.wim"
$logFile = Join-Path $logDir "dism.log"

try {
    # Convert ESD to WIM
    Write-Host "Converting ESD to WIM..."
    $convertCmd = "dism /Export-Image /SourceImageFile:`"$esdPath`" /SourceIndex:3 /DestinationImageFile:`"$wimPath`" /Compress:max /Logpath:`"$logFile`" /Loglevel:4 /CheckIntegrity"
    Invoke-Expression $convertCmd
    if ($LASTEXITCODE -ne 0) { throw "DISM conversion failed" }

    # Mount WIM
    Write-Host "Mounting WIM image..."
    $mountCmd = "dism /Mount-Image /ImageFile:`"$wimPath`" /Index:1 /MountDir:`"$mountDir`" /Logpath:`"$logFile`" /Loglevel:4"
    Invoke-Expression $mountCmd
    if ($LASTEXITCODE -ne 0) { throw "WIM mount failed" }

    # Copy driversipolicy.p7b
    Write-Host "Copying driversipolicy.p7b..."
    $sourcePath = Join-Path $mountDir "Windows\System32\CodeIntegrity\driversipolicy.p7b"
    $destPath = Join-Path $outputDir "driversipolicy.p7b"
    Copy-Item -Path $sourcePath -Destination $destPath -Force

    # Cleanup
    Write-Host "Cleaning up..."
    $unmountCmd = "dism /Unmount-Image /MountDir:`"$mountDir`" /Discard /Logpath:`"$logFile`" /Loglevel:4"
    Invoke-Expression $unmountCmd
    if ($LASTEXITCODE -ne 0) { throw "WIM unmount failed" }

    Remove-Item -Path $mountDir -Force
    Remove-Item -Path $wimPath -Force
    Remove-Item -Path $esdPath -Force
    
    Write-Host "Process completed successfully!"
}
catch {
    Write-Error "Error: $_"
    if (Test-Path $logFile) {
        Write-Host "DISM Log:"
        Get-Content $logFile
    }
    exit 1
}