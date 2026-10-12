# Local operations runbook

Run PowerShell commands from the repository root. Scripts resolve their resources relative to their own location and check exit codes. If Windows blocks local scripts, use the process-scoped invocation `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Setup-Lab.ps1`; do not change the machine's global execution policy.

## Start and inspect

```powershell
.\scripts\Setup-Lab.ps1
.\scripts\Start-Lab.ps1
.\scripts\Seed-Lab.ps1
.\scripts\Inspect-LabStorage.ps1
```

Prerequisites: Windows x64, Python 3.12, uv, Git, Docker Desktop with Linux containers and its Compose plugin. Setup uses the committed lock, CPU PyTorch index, pinned image/archive inputs, and pinned multilingual E5 revision. It installs Chromium for local browser checks. There is no separate Java, database server or Node build dependency on the host.

Frozen semantic inputs, fixture JSON, the lock and container build definitions retain their exact bytes through Git attributes. Do not normalize their line endings in an existing published release: manifests and the evaluation freeze intentionally verify exact content hashes.

`.env` contains generated database passwords and stays ignored. Four non-owner database identities separate source writes, workbench/worker writes and reads. Migrations use the database owner. The service/process registry is `.runtime/<namespace>/processes.json` (interactive uses `.runtime/processes.json`). Start recognizes owned live processes by PID, creation time, executable and namespace. Stop verifies those fields before terminating their descendant trees.

Startup prepares local retrieval before reporting the web process ready; its bounded wait allows up to three minutes for a cold model/library load. This warmup makes no Codex requests. Use `/status` for database/graph health, snapshot freshness, failed jobs, retry, assistant runs and the last backup. Logs stay under each namespace's `logs` directory. Publication is asynchronous; wait for a current snapshot or a visible failed job rather than repeatedly submitting refreshes. A failed cross-store job retains its source cut and can be retried from the status page.

## Sources and review history

Correction accepts changed fields on `/validation` or through the JSON source API after acquiring a local session/CSRF token. It creates a full new aggregate version. Reusing an event ID with identical contents has no effect; different contents are rejected. Historical source IDs and saved evidence remain readable through the source viewer.

Source changes automatically queue a new projection. Semantic changes require a candidate and explicit approval/activation. Rollback restores one complete graph/vector/source tuple and increments the epoch. If source heads have moved, the rollback is visibly stale until refreshed under the restored release. Old briefs keep their original evidence and do not become new answers.

## Codex

```powershell
.\scripts\SignIn-Codex.ps1
```

Finish the browser-managed ChatGPT flow while this command is running. The isolated `%USERPROFILE%\.isw-codex` profile contains the runtime's own authentication. Do not copy personal Codex configuration or credentials into the repository, app data root, tests or backups. Account status is shown without displaying the identity or token. No API-key fallback exists.

One assistant run is active at a time. Closing the browser preserves it; Cancel revokes its token and interrupts the owned turn. Completed briefs must pass schema, policy-version, release, projection, bundle, citation and category checks. A single bounded repair is allowed within the 180-second total deadline. A rate limit creates a visible failure state for a later explicit retry; the app neither purchases credits nor loops on inference.

## Verification and evaluation

```powershell
.\scripts\Verify-Lab.ps1
.\scripts\Evaluate-Lab.ps1
# Only when you want real subscription-backed inference:
.\scripts\Verify-Lab.ps1 -LiveCodex
```

For repeatable timings, stop completed interactive/restore namespaces before running a full verification. E09 stops its restore services after browser inspection.

The default verification uses actual PostgreSQL, both country Fuseki services, the worker, Chromium and one actual STDIO MCP probe. It makes no model requests. It rebuilds only the dedicated `isw-e2e` / `isw-e2e-restore` namespaces and backs up their existing review/audit data first. Do not store unique personal work there. Test failures retain traces under ignored `output/playwright`; publish only sanitized outcome reports and chosen screenshots.

The evaluator needs E2E's late-endorsement, old-source and replacement history. It runs the frozen 20/8 split, stops only the test CZ service for R27, restores that service in `finally`, and writes a local reproduction report. The committed first report remains intact. Raw test logs are not benchmark results.

## Backup and restore

```powershell
.\scripts\Backup-Lab.ps1
.\scripts\Restore-Lab.ps1 -BackupPath '<absolute path printed by backup>'
.\scripts\Start-Lab.ps1 -Namespace isw-restore
```

Finish/cancel an active assistant run before backup. Backup fences source/workbench transactions and publication, uses `pg_dump` inside the matching database container, and hashes its dump and immutable sources, graphs, reports and semantic inputs. It records the active tuple, saved review count and completed brief count. It excludes authentication, session keys and model weights.

Restore defaults to **fresh `isw-restore`**, using separate ports/volumes. It refuses occupied application schemas or the source namespace/port, validates all artifact paths and hashes, restores PostgreSQL, reconfigures local role passwords, expires tokens, reloads graph files and verifies counts/pointer. It never copies live TDB2 directories. Open the restored case, saved brief and original citation before considering a backup usable. See the [measured restore result](verification/restore.json).

## Stop and reclaim project storage

```powershell
.\scripts\Stop-Lab.ps1
.\scripts\Stop-Lab.ps1 -Namespace isw-e2e
.\scripts\Stop-Lab.ps1 -Namespace isw-e2e-restore
.\scripts\Stop-Lab.ps1 -Namespace isw-restore
.\scripts\Reset-Lab.ps1             # inventory only
```

Stopping releases process/container memory and keeps data. An explicit `Reset-Lab.ps1 -AllowDataLoss` creates a backup first, stops only that namespace and removes its containers and three named volumes. Start that namespace before a data reset so the database is reachable for backup; a failed backup prevents removal. The reset leaves immutable local files and backups for recovery. Never point it at another project's namespace.

After stopping, `.venv`, this project's `.runtime/models`, and ignored browser test output are rebuildable. Removing the model/environment requires setup/download again. Backups, manual review/audit history and cited immutable artifacts are not disposable merely because the application runs in Docker. Keep a verified backup outside a directory you intend to remove. Review resolved absolute paths before any manual recursive deletion.

The Fuseki image is shared by this project's country/verification containers; PostgreSQL layers and download/browser caches may be shared with unrelated work. Do not automatically prune them. Never use a global Docker prune, factory reset, WSL shutdown/unregister, or VHDX deletion for this project. Deleting data inside Docker can free reusable blocks without immediately shrinking the host VHDX file.

## Troubleshooting

| Symptom | Check / recovery |
|---|---|
| Docker unavailable | Start the existing Docker Desktop installation; rerun Setup |
| Port conflict | Inspect the four namespace bindings; change this project's mapped ports coherently rather than stopping unrelated services |
| Missing role passwords | Rerun Setup; never paste passwords into a command transcript |
| Frozen-release mismatch | A published release's semantic files changed. Restore its committed files or author a new release; do not relabel changed contents as the same immutable release |
| Failed publication | Inspect the stored job error; retry from Status after correcting the boundary |
| Endpoint outage | Restore the relevant project's service; federation/graph retrieval reports incomplete until it recovers |
| Disconnected assistant | Run SignIn-Codex; deterministic work stays available |
| Failed/limited model run | Inspect its bounded error; retry explicitly after addressing it. There is no API-key workaround |

The app is a local, single-user demonstration. A simulated role selector does not protect it from another user with access to the same machine.
