param([ValidateSet('isw','isw-e2e','isw-restore','isw-e2e-restore')][string]$Namespace = 'isw')
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ProjectPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$ProjectEnv = Join-Path $ProjectRoot '.env'
if (Test-Path -LiteralPath $ProjectEnv) {
    foreach ($line in Get-Content -LiteralPath $ProjectEnv) {
        if ($line -match '^(ISW_[A-Z_]+)=(.*)$') { [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], 'Process') }
    }
}
$ports = switch ($Namespace) {
    'isw' { @(54320,13030,13031,8000) }
    'isw-e2e' { @(54321,14030,14031,8001) }
    'isw-restore' { @(54322,15030,15031,8002) }
    'isw-e2e-restore' { @(54323,16030,16031,8003) }
}
$env:ISW_NAMESPACE = $Namespace
$env:ISW_DB_PORT = [string]$ports[0]
$env:ISW_AT_PORT = [string]$ports[1]
$env:ISW_CZ_PORT = [string]$ports[2]
$env:ISW_WEB_PORT = [string]$ports[3]
$ProjectRuntime = if ($Namespace -eq 'isw') { Join-Path $ProjectRoot '.runtime' } else { Join-Path $ProjectRoot ".runtime\$Namespace" }
$env:ISW_DATA_ROOT = $ProjectRuntime
$env:ISW_MODEL_DIR = Join-Path $ProjectRoot '.runtime\models\multilingual-e5-small'
New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRuntime 'logs') | Out-Null
function Invoke-Isw {
    & $ProjectPython -m insurance_workbench.cli @args
    if ($LASTEXITCODE -ne 0) { throw "Workbench command failed with exit code $LASTEXITCODE" }
}
function Invoke-Compose {
    Push-Location $ProjectRoot
    try {
        & docker compose -p $Namespace @args
        if ($LASTEXITCODE -ne 0) { throw "Project Compose command failed with exit code $LASTEXITCODE" }
    } finally { Pop-Location }
}
