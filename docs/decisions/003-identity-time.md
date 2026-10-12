# 003 — Source identity, contextual roles and half-open time

Use source-namespaced stable IDs and an explicit approved source-ID crosswalk. Never merge by a person's displayed name. A party can hold reporter and insured roles in separate claim/policy contexts. Separate claims can reference one loss event without becoming one claim.

Select policy versions by `from <= loss < to`. Missing dates, absent terms and overlaps remain visible gaps. No latest-version fallback is permitted. Effective dates and recorded times are independent so later-arriving endorsements can alter current context without rewriting an older bundle. Products offered and coverages purchased are separate relationships.

Clause locators point into immutable authored UTF-8 versions. Arbitrary PDF/OCR extraction is deferred; deterministic spans make provenance reviewable in this vertical slice.
