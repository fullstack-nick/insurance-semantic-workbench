# Retrieval and citation evaluation

The [frozen report](evaluation/retrieval.json) contains 28 authored questions, each run through vector, graph and hybrid retrieval: 84 retrievals. Twenty questions form the development split and eight are withheld from that pass. The settings and labels were frozen before scoring; no tuning occurred between splits. These are known synthetic business scenarios, not an independently sourced benchmark.

All modes share deterministic case, policy, operating-country, effective-date and projection eligibility, plus a 12-item / 6,000-token budget. Vector uses exact pgvector cosine ranking over eligible clauses and structured fact cards. Graph uses bounded fixed SPARQL membership and direct-context ordering. Hybrid ranks graph candidates semantically and preserves mandatory context. An unavailable graph does not silently turn hybrid into vector retrieval.

| Split / mode | Required-group coverage | Useful precision | Forbidden items | Warm median |
|---|---:|---:|---:|---:|
| Development · vector | 100% | 23.2% | 0 | 34.6 ms |
| Development · graph | 100% | 23.2% | 0 | 189.5 ms |
| Development · hybrid | 100% | 23.2% | 0 | 201.7 ms |
| Held out · vector | 100% | 25.0% | 0 | 39.4 ms |
| Held out · graph | 100% | 25.0% | 0 | 185.9 ms |
| Held out · hybrid | 100% | 25.0% | 0 | 204.8 ms |

Required groups are authored source relationships/passages, deduplicated by group. Useful precision counts question-required groups among returned groups; contextual but non-required evidence lowers it. Forbidden checks include wrong case, policy/source, operating country, projection and inapplicable contract evidence. Every category and expected text check matched in the recorded pass.

R27 stops the actual CZ service. All three composite workflows report federation unavailable; vector can still retrieve its locally stored case evidence while graph and hybrid report their endpoint failure. R27 has no evidence-coverage denominator and is excluded from the coverage/precision means. The report retains both local retrieval completeness and federation completeness.

## Interpretation

Most eligible case contexts fit within the budget, so coverage reaches a ceiling and the three modes return similar memberships. Low useful precision shows the cost of returning broad context for narrow questions. The measurements support the scope safeguards and the faster vector baseline on this machine; they do **not** establish a hybrid-quality advantage, insurance accuracy, or production latency. Graph context contributes explicit relationships and endpoint completeness at an observed local cost.

Warm times are one pass per question/mode, with the CPU model loaded first. The report records cold loading separately, package versions, source watermarks, projection IDs, manifest hashes, required/retrieved groups, full returned synthetic text and locators. Deliberate outage latency is separate from healthy service behavior. [Additional machine/performance measurements](verification/operations.json) record their own conditions.

## Final reproduction

A [second full report](evaluation/reproduction.json), recorded at 21:08 UTC, reproduces the frozen protocol after the final browser/protocol checks. All 84 retrievals preserved the scope gate, expected categories, expected text and freshness checks. Required coverage and useful precision were unchanged. The source history includes the later E2E tombstone and its retained projections; this was not a new independent holdout.

| Mode | Development warm median | Held-out warm median |
|---|---:|---:|
| Vector | 192.8 ms | 219.6 ms |
| Graph | 938.5 ms | 1,020.0 ms |
| Hybrid | 1,125.6 ms | 1,134.4 ms |

This later pass was substantially slower than the first. Host load and accumulated test history were not controlled between passes, so the cause was not isolated. Retaining both reports avoids presenting the earlier favorable timings as stable performance. No parameters or labels were tuned to the repeated holdout.

## Live citation inspection

Six representative questions reuse the opt-in live workflows: historical terms, contradictions, missing date, a German CZ document, unresolved broad cause under release 2, and a hostile source passage. A seventh brief continues the historical case after a hostile source update. [Structured outputs and cited source text](verification/live-codex.json) preserve the actual model results and usage fields.

The implementation agent inspected all **41 factual observations** against their cited source text; no unsupported observation was found in these seven briefs. This was not independent human/domain adjudication. The CZ brief suggested a further mitigation assessment despite a recorded assessment; that advisory next step is redundant and should be reviewed. The broad-cause hostile example preserved uncertainty even though the deliberately weaker release-1 readiness profile returned sufficient context.

Schema/scope validation checks citation IDs and context, not entailment. Synthetic results and this small inspection cannot establish general factual reliability. Human decisions remain separate, and no coverage or payment outcome is produced.

## Reproduce

Run `Verify-Lab.ps1`, then `Evaluate-Lab.ps1`. Evaluation uses the isolated test history and builds a current candidate if necessary. It makes no Codex requests. The original published result is retained; subsequent runs create `.runtime/isw-e2e/reports/retrieval-reproduction-*.json`. A changed label set or retrieval configuration requires a new explicit protocol; do not describe reused holdout results as fresh independent validation.
