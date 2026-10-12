# 004 — Immutable staging and one activation pointer

PostgreSQL and Fuseki do not share a distributed transaction. Freeze source membership, stage complete AT/CZ asserted/inferred graphs and evidence/vector membership, verify graph round trips, then atomically switch one PostgreSQL pointer. Every request/run pins that tuple. Source changes produce new projections without inventing new ontology releases.

Full-snapshot outbox events simplify ordering: duplicate IDs have no repeated effect; conflicting ID reuse is rejected; older aggregate versions are retained as superseded. The worker reuses a failed job's frozen cut and artifact IDs. A failure after AT upload leaves the old pointer active.

Human activation/rollback increments an epoch and invalidates incompatible queued/building jobs and assistant contexts. Rollback retains source transactions and historical evidence. Semantic files are archived by manifest hash and included in backups. The tradeoff is rebuilding small graphs and retaining history rather than attempting fragile incremental distributed edits.

The E2E suite actually interrupts publication, checks the old pointer, retries, activates a candidate and rolls back. Backup fences application transactions and publication while taking the matched PostgreSQL dump and immutable artifacts; restore is tested in a fresh namespace.
