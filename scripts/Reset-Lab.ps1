param([string]$Namespace='isw',[switch]$AllowDataLoss)
. "$PSScriptRoot\Common.ps1" -Namespace $Namespace
Invoke-Isw storage
Invoke-Compose ps -a
if (-not $AllowDataLoss) { Write-Host 'Dry run only. An explicit -AllowDataLoss flag is required; a backup is created before reset.'; exit 0 }
Invoke-Isw backup
& "$PSScriptRoot\Stop-Lab.ps1" -Namespace $Namespace
Invoke-Compose down --volumes
Write-Host 'Project containers and named volumes removed. Local immutable files and backups retained. Model/environment remain reusable.'
