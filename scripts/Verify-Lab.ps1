param([switch]$LiveCodex)
$ErrorActionPreference='Stop'
. "$PSScriptRoot\Common.ps1" -Namespace isw-e2e
& (Join-Path $ProjectRoot '.venv\Scripts\ruff.exe') check src tests fixtures semantic scripts
if ($LASTEXITCODE -ne 0) { throw 'Lint failed' }
& (Join-Path $ProjectRoot '.venv\Scripts\ruff.exe') format --check src tests fixtures semantic scripts
if ($LASTEXITCODE -ne 0) { throw 'Formatting check failed' }
& $ProjectPython -m compileall -q src
if ($LASTEXITCODE -ne 0) { throw 'Import compilation failed' }
foreach ($target in @('isw-e2e-restore','isw-e2e')) {
    . "$PSScriptRoot\Common.ps1" -Namespace $target
    Push-Location $ProjectRoot
    try { $containers=@(& docker compose -p $target ps -aq) } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw 'Could not inspect the isolated test namespace' }
    if ($containers.Count -gt 0) {
        Invoke-Compose up -d --wait
        & "$PSScriptRoot\Reset-Lab.ps1" -Namespace $target -AllowDataLoss
    }
}
& "$PSScriptRoot\Setup-Lab.ps1" -Namespace isw-e2e
& "$PSScriptRoot\Start-Lab.ps1" -Namespace isw-e2e
& "$PSScriptRoot\Seed-Lab.ps1" -Namespace isw-e2e
. "$PSScriptRoot\Common.ps1" -Namespace isw-e2e
New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot 'output\playwright') | Out-Null
& $ProjectPython -m pytest tests/e2e/test_workflows.py -q --tracing retain-on-failure --output output/playwright/e2e --junitxml output/playwright/e2e-results.xml
if ($LASTEXITCODE -ne 0) { throw 'Deterministic E2E failed; retained browser traces are under output/playwright' }
& $ProjectPython -m pytest tests/integration/test_mcp_scope.py -q --junitxml output/playwright/mcp-results.xml
if ($LASTEXITCODE -ne 0) { throw 'Live MCP scope boundary failed' }
if ($LiveCodex) {
    & $ProjectPython -m pytest tests/e2e/test_live_codex.py --live-codex -q --tracing retain-on-failure --output output/playwright/live-codex --junitxml output/playwright/live-results.xml
    if ($LASTEXITCODE -ne 0) { throw 'Live Codex verification failed; inspect saved run errors' }
}
Invoke-Isw semantic-check
& $ProjectPython (Join-Path $PSScriptRoot 'verification_report.py')
if ($LASTEXITCODE -ne 0) { throw 'Verification report could not be written' }
Write-Host 'Verified. Test services remain available for evaluation; Stop-Lab can stop each test namespace while retaining data.'
