param([Parameter(Mandatory=$true)][string]$BackupPath,[ValidateSet('isw-restore','isw-e2e-restore')][string]$Namespace='isw-restore')
. "$PSScriptRoot\Common.ps1" -Namespace $Namespace
Invoke-Compose up -d --wait
Invoke-Isw restore --path $BackupPath
Write-Host 'Restore verified. Start this namespace to inspect it in the browser.'
