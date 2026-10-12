# Measured verification

Checks run on Windows 11 x64 with Python 3.12.10, PostgreSQL 17.11 / pgvector 0.8.7, Fuseki 6.2.0, Chromium, and the locked Python environment. The application uses real local services. Live assistant checks use the paired Codex SDK/runtime 0.162.1 and the account-backed `gpt-6.1-sol` model.

The reports record separate execution times and projection IDs. They are evidence from several runs, not a claim that every measurement came from one uninterrupted test invocation. Raw browser traces, service logs, authentication and database dumps remain local and ignored.

## Acceptance evidence

| Boundary | Evidence |
|---|---|
| Installed platform | [SQL/vector round-trip, RDF write/query, SHACL negative case and CPU model](verification/platform.json) |
| Ten browser workflows | [Per-workflow results and durations](verification/workflows.json), [executable scenarios](../tests/e2e/test_workflows.py) |
| Three opt-in live assistant workflows | [Workflow results](verification/workflows.json), [seven completed briefs and original cited text](verification/live-codex.json) |
| Actual MCP protocol | [One live integration check, with seven assertions](verification/mcp-scope.json) |
| Ontology and fixed queries | [Shape meta-validation, consumer references and 18 competency checks](verification/semantic.json) |
| Retrieval comparison | [28 questions across three modes](evaluation.md), [frozen evidence-level report](evaluation/retrieval.json) |
| Final retrieval reproduction | [All 84 runs with unchanged scope/category/text/freshness outcomes](evaluation/reproduction.json) |
| Ontology-review assistant | [Actual read-only candidate review](verification/ontology-review.json) |
| Backup and fresh restore | [Artifact hashes, graph round-trips, saved reviews and briefs](verification/restore.json) |
| Failure states | [Signed-out refusal and observed invalid-result rejection](verification/failure-boundaries.json) |
| Storage, access and timings | [Measured operations and database-role checks](verification/operations.json) |
| Final interactive state | [Healthy services, full corpus, connected sign-in, reviewable candidate and final file sizes](verification/final-demo.json) |
| Git checkout reproducibility | [All 40 frozen inputs preserved under both line-ending configurations](verification/git-checkout.json) |
| Public repository | [HTTP 200, rendered README/diagram/screenshots and GitHub metadata](verification/publication.json) |

The ten-workflow run passed in **703.8 seconds**. After the cold-start correction, the actual MCP probe passed from a freshly started web process (**12.6 seconds including pytest setup**) and E09's release/restore/startup workflow passed again (**330.1 seconds**). All 18 competency checks passed. The three live Codex workflows passed earlier in **228.8 seconds**; their results and timestamps remain separate. The outcome report is generated from actual pytest XML, with each suite's start time and per-test duration.

## Browser and protocol coverage

The deterministic suite covers ingestion and original-source provenance; structural quarantine and correction, including malformed amounts; evidence-backed mapping review; country scope independent of document language; effective-date boundaries and overlapping versions; duplicate/conflicting event IDs and tombstones; out-of-order delivery and an interrupted two-store publication; late endorsements and immutable old citations; release approval, activation, rollback and fresh restore; and strict/partial federation during a real CZ outage.

The release workflow also attempts to use rollback to activate an unapproved candidate. Only an audit-backed, previously active snapshot can be restored. It checks the active release state after rollback and inspects a saved human review in the restored browser. The suite creates and rebuilds only the dedicated test namespaces, backing up prior review/audit data before a reset.

The single extra integration check closes a browser blind spot: the UI cannot express adversarial STDIO MCP requests. It starts the real MCP server, checks its six-tool inventory, requests a bound case, rejects cross-country/unissued evidence and a nonexistent write tool, performs hybrid retrieval and reads an issued excerpt, rejects a scope-changing HTTP parameter, and verifies immediate token revocation. It makes no model requests. The startup suite repeats E09 after the readiness change; it is not an additional integration scenario. There are no unit tests, mocks standing in for these services, CI workflows or coverage targets.

## Model results and their limits

Three opt-in workflows produced seven completed claim briefs: six representative cases and a continuation after a hostile source update. The normal historical case selected the original policy version; conflict and missing-date cases retained their expected categories; the CZ example used German source text under the CZ profile; the broad release-2 cause remained incomplete. The continuation used a new thread/projection, retained the old result, and stayed within its issued case evidence. A separate running turn was cancelled and produced no brief.

The implementation agent inspected all **41 factual observations** against the actual cited passages, finding no unsupported observation in this small set. This is not independent human or domain adjudication. The CZ brief suggested another mitigation assessment despite a recorded assessment, so advisory next steps still need review. A broad-cause example can satisfy the deliberately weaker release-1 readiness profile while explicitly retaining uncertainty. Schema and citation-membership checks do not prove entailment.

The ontology role completed an actual four-tool review of release differences, validation and impact. It supplied suggestions only; approval and activation remained explicit application actions. Signed-out access was tested using an empty isolated profile and failed before inference. Earlier actual invalid-scope model results were rejected without saving a brief. Subscription exhaustion was not deliberately induced; the report distinguishes that untested failure from observed failures.

## Restore and reproducibility

The interactive restore drill verified **302 file hashes and 17 graph round-trips**, preserved **six review/approval records and two completed briefs**, and loaded the original EUR 120 source passage in a browser. The restored claim result matched the original JSON. E09 separately tests a saved-review restore after its release lifecycle. Restored tokens are expired; account credentials and model weights are outside the backup.

`Verify-Lab.ps1` runs formatting/lint checks, import compilation, a fresh database/graph setup and seed, the ten browser workflows, the actual MCP check, and semantic validation. `-LiveCodex` explicitly adds subscription-backed inference. `Evaluate-Lab.ps1` reuses the frozen labels/settings and writes a local reproduction report; it preserves the original published benchmark.

A resource-pressure run exposed a cold graph-request timeout when several workbench/restore copies were left running. Separating tokenizer loading from embedding weights reduced that work, but a fresh-process MCP check still exceeded the 20-second budget during library initialization; the same probe passed once warm. Web startup now prepares both tokenizer and encoder before reporting readiness. The cold-process protocol check and restore-start workflow are repeated after that change. The browser suite stops its completed restore services. Run one verification stack at a time. Reported timings are observations on this machine, not service-level guarantees.

The initial corpus is synthetic and small, the roles are simulated, and the workbench makes no coverage/payment decisions. The reports support the demonstrated boundaries and workflows; they do not establish production authorization, actuarial validity or general model reliability.
