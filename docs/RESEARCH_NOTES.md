# Implementation research and decision record

Research baseline: 12 October 2026. The [implementation plan](../IMPLEMENTATION_PLAN.md) supersedes the attached draft for development. It preserves the three workflows, bounded fictional dataset, semantic standards, local architecture, subscription-backed assistant, retrieval comparison, testing preferences, and release demonstration.

The material changes are explicit temporal rules, distinct semantic/data versions, a concrete publication protocol, case-bound evidence contracts, a full question/validation/evaluation catalog, a compact acceptance sequence, and public-repository requirements. The attached text had recruitment-origin framing but no direct insurer or insurance-product brand names were found in the targeted inspection. The revised project material uses independent framing throughout.

## Research findings and implementation consequences

### Python and Codex

The current official Python SDK exists and is a stable package. Package metadata for `openai-codex` 0.162.1 requires Python 3.10 or later and pins `openai-codex-cli-bin==0.162.1`. A Windows amd64 runtime wheel is available. This supports retaining the draft's Python architecture rather than adding a TypeScript bridge. [Official SDK documentation](https://learn.chatgpt.com/docs/codex-sdk), [package metadata](https://pypi.org/pypi/openai-codex/0.162.1/json)

The installed desktop CLI is a different alpha version. The application should use its own paired SDK/runtime and record its version. Its account/MCP probe remains mandatory: metadata and the observed existing ChatGPT CLI login do not prove a standalone application turn will succeed.

The official app-server surface supports account status and thread/turn operations. Keep authentication under Codex control for this local application. Current documentation also discusses Sign in with ChatGPT for other integration arrangements; no new OAuth application, hosted authentication service, or token-sharing implementation is needed for this plan's scope. [App-server documentation](https://learn.chatgpt.com/docs/app-server)

The restricted tool set is an implementation requirement, not a claim that sandbox mode alone enforces case scope. The case-bound MCP service and application evidence checks provide that boundary. Phase 0 must demonstrate both a valid fact retrieval and rejection of an out-of-scope request.

### Runtime versions and dependency compatibility

Use Python 3.12 because it is already installed and the researched Windows dependency set resolves with binary wheels. The default `python` command currently selects 3.11, so scripts must select the intended interpreter explicitly.

The candidate resolution includes FastAPI 0.143.0, Pydantic 2.14.1, RDFLib 7.6.0, pySHACL 0.40.1, SQLAlchemy 2.1.4, psycopg 3.3.6, Sentence Transformers 6.1.0, CPU PyTorch 2.14.1, MCP 2.3.0, and Playwright 1.63.0. These are a researched baseline, not an instruction to upgrade unrelated environments. The complete resolved list has 95 packages. [Candidate inputs](research/dependency-candidates.in), [resolution output](research/dependencies-windows-py312.txt)

No source compilation was permitted in the resolver check. A compiler toolchain is therefore not a planned prerequisite. This does not rule out runtime platform issues, which the import/model/service checks must catch. The final `uv.lock` is produced after installation and verification; the research file is not the final installation contract.

### Graph and relational infrastructure

Jena's current inspected release is 6.2.0 and requires Java 21. The host already has Java 21, while the container image will carry its own pinned runtime. Build from the official distribution with artifact verification. [Apache Jena releases](https://jena.apache.org/download/)

PostgreSQL 17 is within the official supported-major lifecycle. pgvector publishes a compatible 0.8.7 image tag. Keeping this established major avoids taking a newer major solely because it exists. The actual server patch version and image digest belong in the implementation manifest. [PostgreSQL versioning](https://www.postgresql.org/support/versioning/), [pgvector Docker tags](https://github.com/pgvector/pgvector#docker)

One image can run two graph containers; separate processes and volumes make a country outage real and independently recoverable. This is preferable for the planned demonstration to exposing two URLs from one process and calling that process isolation. Do not add a third graph service or distributed transaction coordinator.

### Semantic decisions

OWL imports compose meanings rather than override them. The chosen layering uses narrower country concepts and explicitly selected validation profiles. [OWL 2 primer](https://www.w3.org/TR/owl2-primer/)

The initial inference regime is intentionally RDFS. A pySHACL inference option is not a declaration that arbitrary OWL axioms are fully supported. Supported constructs, local imports, asserted/inferred graph separation, and positive/negative examples must be explicit. SHACL handles present-data constraints and workflow readiness. [pySHACL](https://github.com/RDFLib/pySHACL), [SHACL](https://www.w3.org/TR/shacl/)

SKOS mapping strength matters to the broad water-damage scenario. Narrower classification requires new evidence; a label match or approved broad mapping cannot supply a missing cause. [SKOS mapping properties](https://www.w3.org/TR/skos-reference/#mapping)

PROV-O supplies general derivation relationships, while application-owned immutable source snapshots and locators make citations reproducible in practice. Provenance triples alone are insufficient if the cited source bytes can later be overwritten. [PROV-O](https://www.w3.org/TR/prov-o/)

### Retrieval and embeddings

The selected E5 model provides 384-dimensional multilingual embeddings and uses retrieval prefixes. Its inspected revision is pinned in the plan. CPU execution is a scope/footprint choice; no benchmark has yet established latency on this machine. The file metadata allows a concrete model-size estimate without downloading weights. [Model card](https://huggingface.co/intfloat/multilingual-e5-small/raw/main/README.md), [model file metadata](https://huggingface.co/api/models/intfloat/multilingual-e5-small?blobs=true)

Set the CPU PyTorch source explicitly in uv so this project does not install GPU packages accidentally. Download only the selected weight format and tokenizer/configuration files. [uv CPU index configuration](https://docs.astral.sh/uv/guides/integration/pytorch/)

The three retrieval modes must share source facts, eligibility, snapshot, and evidence budgets. Source-backed fact cards make the vector baseline comparable to graph access to structured records. Exact vector search is sufficient at the planned corpus size; ANN indexes and additional GraphRAG frameworks would add variables before a baseline exists. [pgvector exact search](https://github.com/pgvector/pgvector#querying)

### Federation and consistency

SPARQL `SERVICE SILENT` suppresses endpoint errors, so it cannot by itself distinguish a successful empty country result from a failed country. The plan uses strict federation plus an explicitly labeled partial view. [SPARQL service failures](https://www.w3.org/TR/sparql11-federated-query/#serviceFailure)

The cross-store publication design is a project architecture decision: immutable graph/vector artifacts, a readiness manifest, and one transactional application pointer. It does not assume atomic commit across PostgreSQL and Fuseki. Data projections and semantic releases are separate axes, and every request pins one tuple.

Full aggregate snapshots in events make out-of-order processing well-defined without building a general event-sourcing system. Source mutations and outbox insertion share a database transaction; retries and crash recovery are observable E2E behaviors.

### Storage and lifecycle

Docker Desktop, WSL, uv, Python, Java, Git, and Codex are already installed. The Docker engine was stopped during inspection, so image availability, volume contents, and live reclaimable space are unknown. The 189.35 GiB existing VHDX logical length is not a project download requirement or a reclaimable-space estimate.

Use the detailed [local assessment](LOCAL_ENVIRONMENT.md) for installed/missing components and the 6–15 GiB working / 15–25 GiB peak estimate. Deleting a container differs from deleting its persistent volume; routine Compose shutdown keeps named volumes. [Docker volumes](https://docs.docker.com/engine/storage/volumes/), [Compose shutdown](https://docs.docker.com/reference/cli/docker/compose/down/)

Playwright browser versions are tied to its package version. Existing browsers are evidence of available tooling, not proof the pinned Python test runner needs no additional browser download. Install Chromium alone. [Playwright browsers](https://playwright.dev/python/docs/browsers)

### Public portfolio delivery

The repository target and copyright name were explicitly confirmed. Publication follows implementation verification; no repository was created in this planning step. The README should demonstrate behavior through actual screenshots, an accurate local/remote diagram, a short demo, measured evaluation, and runnable instructions. Keep the long design material in linked documents. [GitHub README guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes)

Apply MIT to the project's own work and retain required notices for redistributed third-party material. Do not distribute model weights or upstream container payloads inside the Git repository. [MIT template](https://choosealicense.com/licenses/mit/)

## Evidence and limitations of this planning step

| Checked now | Still requires implementation |
|---|---|
| Attached draft and empty project directory inspected | Actual application, fixture generation and semantic files |
| Installed tools, OS, RAM, free space, selected directories and ports inspected | Running database services, persistence, startup resource use |
| GitHub account and desired repository target checked | Repository creation and public rendering verification |
| Existing CLI reports ChatGPT login | Application SDK turn, MCP call, isolated-profile access |
| Official documentation and publisher metadata reviewed | Successful imports and version-specific runtime behavior |
| 95-package Windows/Python 3.12 CPU resolution completed | Final installed lock, CPU model loading and real embeddings |
| Model/image compressed-size metadata inspected | Expanded sizes, actual database growth and reclaimable host space |
| Question, validation, evaluation and acceptance catalogs specified | Passing E2E, live-agent evaluation and restore drill |

The successful resolver check narrows an installation risk. It is not a passed integration suite. The operational gates are concentrated at the beginning of the build so the main implementation can proceed from demonstrated capabilities.
