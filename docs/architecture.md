# Architecture

The workbench is a modular Python application with server-rendered pages. Source adapters, projection publication, retrieval, governance, agent execution, and operations are separate modules under `src/insurance_workbench`. They share typed settings and SQLAlchemy table definitions; the small corpus does not justify a plugin framework or extra service broker.

## Local topology

| Namespace | Purpose | Web | PostgreSQL | AT / CZ Fuseki |
|---|---|---:|---:|---:|
| `isw` | Interactive workbench | 8000 | 54320 | 13030 / 13031 |
| `isw-e2e` | Browser verification and evaluation | 8001 | 54321 | 14030 / 14031 |
| `isw-restore` | Fresh restore drill | 8002 | 54322 | 15030 / 15031 |
| `isw-e2e-restore` | E09 restore target | 8003 | 54323 | 16030 / 16031 |

All host bindings use `127.0.0.1`. Containers communicate through their namespace's Compose network. CQ17 executes at AT with the fixed `http://fuseki-cz:3030/ds/query` service target. Stopping CZ makes strict federation unavailable; partial mode runs separate fixed queries and names the failed endpoint. Failure is never converted into a zero count.

Python and the embedding model run natively. Web startup prepares the pinned tokenizer and performs one local warmup encoding before reporting readiness, keeping cold library/model initialization outside the 20-second MCP request budget. PostgreSQL/pgvector and the two Fuseki TDB2 stores use named Linux volumes. The two country services share the same verified Fuseki image. Windows reserves ports 3030/3031 on the measured machine, which is why host ports differ from the planning baseline.

## Data and publication

Source transactions save full aggregate snapshots and outbox events together. Aggregate-scoped locks serialize concurrent writers; immutable version hashes reject conflicting reuse. Older full snapshots are retained as superseded and never move the source head backwards. Tombstones remove an aggregate from the next accepted projection while retaining original history.

The worker freezes source membership, applies the release's mappings, constructs evidence and RDF, materializes RDFS, runs SHACL, and stages vectors plus four named graphs. Graph content is checked by a canonical RDF digest after round-trip through Fuseki. Only then does one PostgreSQL pointer select the complete tuple. An interrupted AT/CZ upload cannot expose a mixed snapshot. An activation epoch prevents a late worker from undoing a human rollback.

Source payloads and smaller domain structures use immutable JSONB snapshots. Operational policy versions and claim/document indexes are relational. Projection membership, evidence, embeddings, jobs, proposals, decisions, run events and audit history have dedicated tables. A separate physical table for every ontology class would add little value here; RDF supplies those relationships.

Semantic inputs are copied into content-addressed local release directories. A projection records the exact manifest, source cut, graphs, evidence membership, model settings and watermark. Briefs, bundles and document spans point to immutable evidence. Original source values remain distinct from generated fact cards and model suggestions.

## Assistant boundary

A durable runner starts the pinned official Codex SDK/runtime using an isolated ChatGPT profile. Six claim tools—or three tools for a bound ontology candidate—communicate over STDIO MCP and a token-authenticated local HTTP endpoint. The server derives scope from the token. The model cannot supply another case, graph URL, filesystem path or arbitrary query.

The runtime disables shell, web, unrelated apps/plugins/skills and other capabilities. The MCP inventory is checked before each run; read-only annotations permit those specific tools under approval policy `never`. Each run has a 180-second total budget, 20-second tools, 20 tool calls, one validation-repair attempt, and a revocable token. Only schema-valid, correctly scoped completed turns become briefs. The SDK's tool-dispatch host remains enabled because MCP calls depend on it.

Model inference uses OpenAI remotely. Databases, embeddings, validation, retrieval and tools remain local. The app does not create API keys, purchase credits, or send account notifications.

## Ownership and operations

Database identities separate migrations, source writes, workbench writes, worker publication and read operations. MCP receives only its short-lived token and local API URL. Browser mutations use POST, session-bound CSRF, same-origin checks, escaped templates and a local content security policy. Roles are simulated perspectives, not enterprise authorization.

Backup pauses mutations, fences transactions and publication, uses the matched PostgreSQL container's `pg_dump`, and captures immutable graph/source/release files with hashes. Restore accepts only a fresh restore namespace, checks file hashes, reloads graphs through supported APIs, expires copied run tokens, and verifies the active pointer and review/brief counts. Secrets and model weights are excluded.

See [decisions](decisions/001-topology.md), [modeling](modeling-standard.md), [mapping catalog](mapping-catalog.md), and [runbook](runbook.md).
