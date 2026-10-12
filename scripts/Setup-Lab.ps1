param([string]$Namespace='isw')
$ErrorActionPreference='Stop'
$ProjectRoot=Split-Path -Parent $PSScriptRoot
foreach ($command in @('uv','git','docker','py')) { Get-Command $command -ErrorAction Stop | Out-Null }
Push-Location $ProjectRoot
try {
    if (-not (Test-Path -LiteralPath '.env')) {
        & py -3.12 -c "from pathlib import Path; import secrets; Path('.env').write_text('ISW_DB_PASSWORD='+secrets.token_hex(24)+'\nISW_DB_PORT=54320\nISW_AT_PORT=13030\nISW_CZ_PORT=13031\nISW_WEB_PORT=8000\nISW_NAMESPACE=isw\nISW_DATA_ROOT=.runtime\n')"
        if ($LASTEXITCODE -ne 0) { throw 'Could not create project settings' }
    }
    & py -3.12 -c "from pathlib import Path; import secrets; p=Path('.env'); s=p.read_text(); s+=''.join('ISW_DB_'+r+'_PASSWORD='+secrets.token_hex(24)+'\n' for r in ['APP','SOURCE','WORKER','READER'] if 'ISW_DB_'+r+'_PASSWORD=' not in s); p.write_text(s)"
    if ($LASTEXITCODE -ne 0) { throw 'Could not configure project database roles' }
    & uv sync --frozen --no-python-downloads
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
    . "$PSScriptRoot\Common.ps1" -Namespace $Namespace
    & docker info --format '{{.ServerVersion}}' 2>$null
    if ($LASTEXITCODE -ne 0) { & docker desktop start; if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop and retry' } }
    Invoke-Compose up -d --build --wait
    Invoke-Isw init
    Invoke-Isw assets
    & $ProjectPython -m playwright install chromium
    if ($LASTEXITCODE -ne 0) { throw 'Chromium installation failed' }
    Write-Host 'Setup complete. Start and seed the lab. Optional assistant sign-in: .\scripts\SignIn-Codex.ps1'
} finally { Pop-Location }
