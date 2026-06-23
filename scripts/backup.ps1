# Backup script for Open WebUI memory layer data
# Run this script to snapshot the Open WebUI data directory

$DataDir = "$env:USERPROFILE\.open-webui"
$BackupDir = "$env:USERPROFILE\.open-webui\backups"
$MaxBackups = 10

if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Force $BackupDir | Out-Null
}

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupFile = "$BackupDir\openwebui_backup_$Timestamp.zip"

if (Test-Path $DataDir) {
    Compress-Archive -Path "$DataDir\*" -DestinationPath $BackupFile -Force
    Write-Host "Backup created: $BackupFile"

    # Rotation: keep only the last $MaxBackups backups
    $Backups = Get-ChildItem $BackupDir -Filter "openwebui_backup_*.zip" | Sort-Object CreationTime -Descending
    if ($Backups.Count -gt $MaxBackups) {
        $Backups | Select-Object -Skip $MaxBackups | ForEach-Object {
            Remove-Item $_.FullName -Force
            Write-Host "Removed old backup: $($_.FullName)"
        }
    }
} else {
    Write-Warning "Data directory not found: $DataDir"
}
