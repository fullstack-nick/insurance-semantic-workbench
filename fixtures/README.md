# Authored fixture scenarios

`corpus.json` is the committed source of truth. `generate.py` documents its construction; ordinary setup reads the committed bytes. Do not regenerate fixtures into an existing namespace and reuse source-version IDs with changed content.

The initial corpus has 60 AT / 40 CZ policies, 30 AT / 20 CZ claims, and 18 AT / 14 CZ document versions. Twenty policies have historical terms in addition to current terms; two deliberately overlapping versions bring the policy-version total to 122. Documents use German/Czech passages and English structured facts. All operating rules and entities are invented.

| Claim suffix | Intended scenario |
|---|---|
| 001 | Loss 2024-12-31; earlier policy/document and deductible |
| 002 | Ordinary pipe claim; CZ document deliberately in German |
| 003 | Missing loss date; no guessed historical policy |
| 004 | Broad, unresolved water entry; release 2 is not ready |
| 005 | Customer reports a pipe leak; assessor reports surface flooding |
| 006 CZ | Missing mitigation assessment under the CZ profile |
| 007 | Quoted hostile instruction inside an attributed source passage |
| 008 | Exact 2025-01-01 version boundary |
| 009 | Overlapping policy periods; policy quarantined and context incomplete |
| 010 | Invalid currency; browser correction retains the original version |
| 012 / 013 | Separate claims share one loss event |
| 012 AT | Operating country AT, property country CZ |
| 014 | Unapproved similar-name identity candidate, kept separate |

Other multiples of seven retain broad causes. These are evidence-readiness examples, not real claim eligibility labels. The generator's `expected` field is descriptive seed metadata; executable truth is in the [competency expectations](competency-expectations.json), [development labels](evaluation-development.json), [held-out labels](evaluation-holdout.json), and actual E2E assertions.

E2E deliberately creates later versions for replay, invalid-decimal correction, out-of-order events, a July endorsement, document replacement, and a tombstone for the otherwise unused AT claim 030. The working test corpus therefore differs from the untouched interactive seed. The evaluation uses those immutable historical projections for late-arrival and stale-context questions. The 20/8 split and common retrieval parameters are [frozen](retrieval-freeze.json) before scoring. No model produced the evaluation answers.
