# Source mapping catalog

| Source | Adapter / fields | Projection meaning | Evidence locator |
|---|---|---|---|
| Policy administration | Relational policy/version rows and full JSONB snapshots | Contract identity, valid period, offered/purchased coverages, insured role, property/operating countries | SQL snapshot table, row and field |
| Claims simulation | Validated JSON envelope, full aggregate snapshots | Claim, loss event, reporter, amount/currency, attributed assertions, mitigation reference | JSON Pointer in an immutable snapshot |
| Document repository | Authored UTF-8 text with immutable document version and clause spans | Applicable clauses, language, original text/hash | Document version, clause ID, Unicode start/end |

Transport contracts reject malformed structures and dates. Semantic defects such as an unsupported currency, malformed decimal or overlapping policy periods survive as inspectable input and are quarantined by SHACL. A correction creates a new source version; it does not mutate the old one.

[`1.0.0/mappings.json`](../semantic/1.0.0/mappings.json) maps `AT:WD` and `CZ:VODA` exactly to broad water damage. These are invented source codes. [`2.0.0/mappings.json`](../semantic/2.0.0/mappings.json) permits source-supported narrowing; it does not reinterpret a broad code as a narrow cause. Unknown codes remain unresolved and require stewardship. Mapping nodes are also materialized for shape validation.

[`identity-crosswalks.json`](../semantic/identity-crosswalks.json) explicitly maps policy and claim party source IDs to canonical parties. Approval is authored for these invented IDs. The similar-name candidate in claim 014 is not an approved join; its two identities remain separate.

Mapping proposals record their rationale, target, supporting case/source and simulated human decision. Approval records evidence for a proposal; it does not let a model rewrite mappings. The release's reviewed files and explicit activation govern applied meaning. The supplied migration narrows only unambiguous source causes and leaves legacy/contradictory records broad.

Each projection pins all relevant mapping, vocabulary, shape, query and consumer-file hashes. [Consumer dependencies](../semantic/consumers.json) are explicit declared contracts, not a claim that static dependency extraction proves semantic equivalence. Impact compares actual case results, evidence text and representative CQ16 bindings alongside the structural RDF diff.
