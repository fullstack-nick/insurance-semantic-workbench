param([string]$Namespace='isw')
. "$PSScriptRoot\Common.ps1" -Namespace $Namespace
Invoke-Isw storage
Invoke-Compose images
& docker volume ls --filter "label=com.docker.compose.project=$Namespace"
if ($LASTEXITCODE -ne 0) { throw 'Could not inspect project volumes' }
