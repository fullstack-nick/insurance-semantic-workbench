# Implementation status

Implemented on 12 October 2026. The original [implementation plan](../IMPLEMENTATION_PLAN.md) remains the historical acceptance contract; this file records installed behavior and measured evidence.

## Delivered workflows

- **Claim review:** the seeded corpus contains 100 policies, 122 policy versions, 50 claims and 32 immutable document versions. Historical effective dates select purchased coverage and applicable clauses. Missing facts, overlapping terms, contradictory assertions and structurally quarantined records remain distinct. Source viewers show original passages, hashes, locators and mapping lineage.
- **Semantic stewardship:** 30 classes and 55 properties form layered enterprise, domain, country and review models. Multilingual SKOS, approved identity crosswalks, source-code mappings, RDFS inference, SHACL and 18 fixed queries support the case views. Proposed reuse, a fictional CZ extension and rejected globalization have separate review records.
- **Reliable publication:** full source snapshots, transactional outbox events, duplicate/version checks and tombstones feed a single worker. It stages immutable graph/vector/evidence artifacts before switching one pointer. An interrupted country upload retains the previous coherent snapshot; retries converge and activation epochs fence obsolete jobs.
- **Retrieval:** exact vector, fixed graph and hybrid modes share eligibility, mandatory context and item/token budgets. The 28-question evaluation preserves the frozen 20/8 split, source evidence and timings. Coverage reached a small-corpus ceiling; the report does not claim a hybrid advantage.
- **Bounded assistant:** the official paired Codex SDK/runtime uses the owner's isolated ChatGPT sign-in. Claim and ontology-review roles have distinct read-only MCP inventories and server-bound scope. Cited results, progress, cancellation, old-context warnings and saved history work through the browser. Explicit review dispositions are separate from generated suggestions.
- **Semantic lifecycle:** a real 2.0.0 candidate adds evidenced narrower causes and stricter readiness. Its page shows record/evidence changes, actual CQ16 comparisons, declared consumers and unresolved cases. Approval precedes activation; rollback accepts only previously active snapshots and preserves saved evidence.
- **Local operations:** pinned dependency/model/image inputs, generated local secrets, scoped process ownership, setup/seed/stop scripts, consistent backups, fresh restores and storage inspection are implemented. The interactive restore preserved six review/approval records, two completed briefs, 302 hashed files and 17 graphs.

## Verification

Platform checks, real browser workflows, actual MCP protocol checks, live model results, competency queries, retrieval measurements and restore evidence are linked from [verification](verification.md). Seven completed claim briefs were inspected against 41 cited factual observations by the implementation agent; this is explicitly not independent human/domain validation. An additional ontology-review turn completed with read-only report tools.

The ten deterministic browser workflows passed. The MCP probe and E09's restore/startup workflow passed again after the cold-start readiness correction; all 18 competency checks passed. The public [MIT repository](https://github.com/fullstack-nick/insurance-semantic-workbench) is published on `main`; its README, diagram and screenshots were verified in a real browser. GitHub Actions is disabled and GitHub Pages is not enabled. No cloud deployment, CI/CD, unit tests or API-key fallback has been added.

## Runtime decisions

The planned Python/FastAPI/Jinja, PostgreSQL/pgvector, Fuseki, RDFLib/pySHACL, local E5 and scoped Codex/MCP architecture is retained. The implementation uses a flat set of cohesive Python modules and JSONB aggregate snapshots alongside relational operational indexes; RDF carries the richer class relationships. This avoids unnecessary package/table machinery for the small corpus. See [architecture](architecture.md) and the [decision records](decisions/001-topology.md).

Host Fuseki ports are 13030/13031 because Windows reserves the original candidates. RDF integrity comparison canonicalizes decimal lexical forms, and materialized RDFS omits generalized triples with literal subjects. The Codex tool-dispatch host remains enabled because the installed runtime uses it for MCP; unrelated capabilities are disabled. Scoped tools declare their read-only behavior. Web startup prepares the pinned tokenizer and encoder before reporting readiness, keeping cold initialization outside MCP deadlines. Completed restore services are stopped to avoid running several memory-heavy copies unnecessarily.

The application is local except for signed-in model inference. All insurance organizations, products, people, contracts and operating rules are invented. Simulated roles are not multi-user authorization, and review readiness is not a coverage or payment decision. The [runbook](runbook.md) describes reproduction, failure recovery, backup and project-scoped cleanup; [storage measurements](LOCAL_ENVIRONMENT.md) distinguish project resources from shared caches and Docker allocation.
