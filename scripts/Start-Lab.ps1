param([string]$Namespace='isw')
. "$PSScriptRoot\Common.ps1" -Namespace $Namespace
Invoke-Compose up -d --wait
$registry=Join-Path $ProjectRuntime 'processes.json'
$old=@()
if (Test-Path -LiteralPath $registry) { $old=@(Get-Content -LiteralPath $registry -Raw | ConvertFrom-Json) }
$processes=@()
foreach ($role in @('serve','worker','agent-runner')) {
    $saved=$old | Where-Object { $_.role -eq $role -and $_.namespace -eq $Namespace } | Select-Object -First 1
    if ($saved) {
        $existing=Get-Process -Id $saved.pid -ErrorAction SilentlyContinue
        if ($existing -and $existing.Path -eq $ProjectPython -and $existing.StartTime.ToUniversalTime().Ticks -eq ([datetime]$saved.started).ToUniversalTime().Ticks) {
            $processes+=$saved
            continue
        }
    }
    $process=Start-Process -FilePath $ProjectPython -ArgumentList @('-m','insurance_workbench.cli',$role) -WorkingDirectory $ProjectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $ProjectRuntime "logs\$role.out.log") -RedirectStandardError (Join-Path $ProjectRuntime "logs\$role.err.log")
    $processes+=@{pid=$process.Id;started=$process.StartTime.ToUniversalTime().ToString('o');role=$role;executable=$ProjectPython;namespace=$Namespace}
}
$processes | ConvertTo-Json | Set-Content -LiteralPath $registry -Encoding utf8
$deadline=(Get-Date).AddSeconds(180)
do {
    try { $health=Invoke-RestMethod "http://127.0.0.1:$env:ISW_WEB_PORT/api/v1/health"; if ($health.complete) { Write-Host "Workbench ready at http://127.0.0.1:$env:ISW_WEB_PORT"; exit 0 } } catch { }
    Start-Sleep -Milliseconds 500
} while ((Get-Date) -lt $deadline)
throw 'Workbench did not become healthy; inspect this namespace logs.'
