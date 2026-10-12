param([string]$Namespace='isw')
. "$PSScriptRoot\Common.ps1" -Namespace $Namespace
Invoke-Isw backup
