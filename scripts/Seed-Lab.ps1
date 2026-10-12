param([string]$Namespace='isw')
. "$PSScriptRoot\Common.ps1" -Namespace $Namespace
Invoke-Isw seed
Invoke-Isw wait-ready
