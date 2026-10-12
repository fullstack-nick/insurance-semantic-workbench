# Third-party notices

Project source, authored fictional fixtures, documentation and application screenshots are MIT © 2026 Nick Petrushin. Upstream software and model licenses remain their own; the project license does not replace them.

No model weights, browser binaries, Python environment, database files or container layers are redistributed in this repository. Setup downloads them from their upstream sources. The lockfile records Python versions and distributions; Compose/Dockerfile record image/archive inputs.

| Component | Upstream reference / terms |
|---|---|
| Python | [Python Software Foundation license](https://docs.python.org/3/license.html) |
| FastAPI, SQLAlchemy, Alembic | MIT; see the respective upstream repositories |
| Jinja2 / MarkupSafe | BSD terms in the installed distributions |
| PostgreSQL / pgvector | [PostgreSQL license](https://www.postgresql.org/about/licence/) / [pgvector](https://github.com/pgvector/pgvector) |
| Apache Jena Fuseki | [Apache License 2.0 and upstream notices](https://github.com/apache/jena); downloaded archive verified by SHA512 |
| RDFLib / owlrl / pySHACL | BSD-3-Clause / upstream OWL-RL terms / Apache-2.0; consult the pinned distributions |
| Sentence Transformers / Transformers | Apache-2.0 and bundled upstream notices |
| PyTorch CPU | The installed wheel has a composite license expression and bundled third-party notices; consult its distribution rather than assuming one license covers all included components |
| Multilingual E5 small | [Pinned model card and license](https://huggingface.co/intfloat/multilingual-e5-small/tree/614241f622f53c4eeff9890bdc4f31cfecc418b3); weights downloaded during setup |
| OpenAI Codex Python SDK / runtime | Apache-2.0 for the installed SDK/runtime; account services have separate service terms |
| Python MCP SDK | MIT |
| Playwright / Chromium | Playwright Apache-2.0; Chromium and bundled components retain their upstream licenses |
| uv / Docker Desktop / Eclipse Temurin | Separately installed/downloaded tools and runtime distributions retain their upstream terms |

The semantic model uses standard RDF/RDFS, OWL, SKOS, SHACL and PROV-O identifiers. No real insurance materials or third-party product branding are included. UI styling and icons are authored locally, with system fonts and no CDN assets.
