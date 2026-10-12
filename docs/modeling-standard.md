# Modeling standard

The fictional namespace is `https://example.org/isw/`. Terms live under `term/`, contextual entities under `entity/`, and the country extension under `cz/`. IDs use source namespaces and stable identifiers rather than names. Semantic releases version meaning; projection IDs version source membership.

## Layers and distinctions

| Layer | Responsibility | Examples |
|---|---|---|
| Enterprise | Shared business identity and context | Party, RoleAssignment, Contract, Document, SourceRecord |
| Insurance domain | Policy and claim relationships | Policy, PolicyVersion, PurchasedCoverage, Claim, LossEvent |
| Country extension | A justified fictional operating need | CZ MitigationAssessment, subclass of shared Assessment |
| Use case | Evidence review and lifecycle | EvidenceAssertion, ReviewBrief, ValidationFinding, SemanticRelease |

A product's offered coverage is distinct from a policy version's purchased coverage. A document represents terms; it is not the policy. A claim and its loss event have separate identities. Reporter and insured roles connect a party to different contexts. An approved exact source-ID crosswalk joins source records; similar names do not.

Policy periods use `valid_from <= loss_date < valid_to`, with an absent upper bound meaning open-ended. Recorded/ingested time is separate from effective time. Zero or multiple applicable versions produce incomplete context, never a newest-version fallback. Amounts stay decimal strings in the source; RDF uses canonical decimal lexical forms. Country, property location, product and document language are independent fields.

## Assertions, provenance and inference

Customer and assessor statements remain separate attributed evidence assertions. Neither becomes an established cause merely because it appears in a source. Every evidence item carries a source version/hash, typed locator, case/country scope, semantic release, projection and transformation. Multi-source loss links retain the supporting source snapshot IDs.

Clauses use exact Unicode-character spans into immutable UTF-8 text. Structured fact cards record their SQL row/field or JSON Pointer and transformation. Clause splitting stays inside the parent clause, targeting 300 tokenizer tokens with 40-token overlap; the CPU model's maximum is 512 including prefixes and metadata.

Only local catalog entries are imported; their checksums must match. Explicit RDFS materialization is stored in a separate graph. CQ14 joins asserted and inferred graphs to demonstrate `Policy rdfs:subClassOf Contract`; no OWL DL completeness claim is made. Generalized triples with literal subjects are filtered before publication because stores accept standard RDF.

## Vocabulary and validation

Release 1 has 38 SKOS concepts. Release 2 adds pipe leakage and surface flooding beneath broad water damage. Approved English/German/Czech preferred labels, scope notes, ownership and statuses live in Turtle. Broad source codes remain broad unless the release allows narrowing and source assertions support exactly one specific cause.

Twenty baseline node shapes distinguish structural acceptance from readiness; release 2 adds a specific-cause readiness shape. Checks cover identity, references, monetary datatype/currency, temporal ordering and overlaps, clause bounds, provenance, labels, mappings, conflicting causes, and the two invented country profiles. Invalid source aggregates are quarantined and their dependent context marked incomplete. Original data and normalized findings remain visible. Engine failure is a failed publication, never an empty clean validation report.

The [18 authored expectations](../fixtures/competency-expectations.json) run against actual named graphs. [Measured results](verification/semantic.json) include query bindings and the installed engine versions.
