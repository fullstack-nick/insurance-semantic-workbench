param([string]$Namespace='isw')
. "$PSScriptRoot\Common.ps1" -Namespace $Namespace
$registry=Join-Path $ProjectRuntime 'processes.json'
if (Test-Path -LiteralPath $registry) {
    $entries=Get-Content -LiteralPath $registry -Raw | ConvertFrom-Json
    $inventory=Get-CimInstance Win32_Process
    foreach ($entry in $entries) {
        $process=Get-Process -Id $entry.pid -ErrorAction SilentlyContinue
        if (-not $process) { continue }
        if ($process.StartTime.ToUniversalTime().Ticks -ne ([datetime]$entry.started).ToUniversalTime().Ticks -or $process.Path -ne $entry.executable -or $entry.namespace -ne $Namespace) { throw 'Recorded PID ownership changed; refusing to stop it' }
        $owned=@([int]$entry.pid)
        do {
            $children=@($inventory | Where-Object { $_.ParentProcessId -in $owned -and $_.ProcessId -notin $owned } | Select-Object -ExpandProperty ProcessId)
            $owned+=$children
        } while ($children.Count -gt 0)
        foreach ($ownedPid in ($owned | Sort-Object -Descending)) { Stop-Process -Id $ownedPid -ErrorAction SilentlyContinue }
    }
    Remove-Item -LiteralPath $registry
}
Invoke-Compose stop
Write-Host "Stopped only $Namespace processes and containers. Data volumes are retained."
