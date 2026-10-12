# 005 — Shared eligibility, three real retrieval paths

Use exact pgvector cosine search rather than ANN for the small 384-dimensional corpus. Vector ranking may not use graph traversal to construct its candidate set beyond shared deterministic source/time/scope eligibility. Graph uses fixed bounded SPARQL; hybrid ranks those graph candidates and prioritizes required context. All paths return the same evidence-bundle schema and 12-item / 6,000-token budget.

The model is pinned multilingual E5 small, normalized CPU embeddings, `query:`/`passage:` prefixes, local-files-only loading, and no remote code. Embeddings are reusable by text-plus-manifest hash; membership is explicit per projection.

The measured corpus reaches a coverage ceiling in all modes and has low question-specific precision. Vector is locally faster. These results justify keeping all three paths inspectable; they do not justify a blanket hybrid-wins claim. Scope and temporal violations remain a hard failure regardless of quality ranking. See the [evaluation](../evaluation.md).
