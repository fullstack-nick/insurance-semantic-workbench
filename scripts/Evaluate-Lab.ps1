param([ValidateSet('isw-e2e')][string]$Namespace='isw-e2e')
. "$PSScriptRoot\Common.ps1" -Namespace $Namespace
Invoke-Isw evaluate
