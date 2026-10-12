# Installed application measurements (12 October 2026)

Setup installed the locked Python 3.12 environment, CPU model, pinned PostgreSQL/pgvector image, verified Fuseki image, and Chromium support. The original pre-build machine assessment is retained below as historical research. The current source of measured values is [operations.json](verification/operations.json).

| Project resource | Observed size | Meaning |
|---|---:|---|
| `.venv` | 1.43 GiB | Logical installed file lengths; uv may share hardlinks |
| Pinned model | 0.46 GiB | One safetensors weight file and required tokenizer/config files |
| `.runtime` including model, test artifacts and retained backups | 0.77 GiB | Includes the model row; do not add it twice |
| Two referenced database image sizes combined | 0.29 GiB | Engine-reported image sizes; shared layers/cache allocation differs |
| Interactive PostgreSQL / AT / CZ volumes | 68.9 / 31.5 / 15.3 MiB | Actual `du` usage inside the three project services at measurement time |
| Free workspace drive space | 93.0 GiB | A point-in-time host measurement, not attributed project growth |

These logical/project resource figures total roughly 2.6 GiB before shared download/browser/build caches and temporary allocation. Keep the original 6–15 GiB working estimate and 30 GiB free-space allowance for a new setup. Existing shared Docker VHDX/cache sizes are not installation cost attributable to this project; host free-space changes also include unrelated workloads and memory paging.

The [final demo measurement](verification/final-demo.json) records later growth from retained test snapshots and backups: `.runtime` reached **1.29 GiB**, while `.venv` remained **1.43 GiB** and the model remained **0.46 GiB within `.runtime`**. Combining those later files with the earlier image/interactive-volume measurements gives roughly **3.1 GiB**, before retained test/restore volumes and shared caches. Final drive free space was **102.8 GiB**. These are logical resource measurements, not an attribution of every changed disk block to this project.

Running four workbench/test/restore namespaces at once exhausted available RAM on the measured host and inflated cold-start times. The final workflow stops completed restore services. Token budgeting uses a separate tokenizer, and the web process prepares local retrieval before reporting readiness so a first tool request does not pay cold library/model startup costs. Prefer one verification stack at a time and stop finished namespaces. Normal runtime still keeps two country graph services.

## Historical planning assessment

# Local environment and storage assessment

Inspected on 12 October 2026. This is a planning assessment for the Insurance Semantic Workbench. No development dependencies, model weights, container images, database services, or desktop applications were installed or started during this assessment. A package dependency resolution was performed without installation.

The existing machine is suitable for the proposed local stack. Budget approximately **6–15 GiB of additional working storage**, allow **15–25 GiB during installation and rebuilding**, and keep **30 GiB available** for comfortable headroom. These are engineering estimates, not measured installation totals. The project database itself should be a small part of this footprint.

## Machine and free space

| Item | Observed result | Consequence |
|---|---|---|
| Operating system | Windows 11 Pro, x64, build 26200 | Use native Python processes and PowerShell scripts |
| Processor | Intel Core i9-13900H, 14 cores, 20 logical processors | CPU embeddings are a reasonable baseline for this small corpus |
| Memory | 31.6 GiB installed | Sufficient for the planned services; measure actual usage in Phase 0 |
| Graphics | NVIDIA RTX 3050 Laptop GPU, 4 GB model; Intel integrated graphics | GPU tooling is unnecessary for the baseline |
| Storage | C: 952.3 GiB total, 114.1 GiB free at inspection | Enough room for the estimated additional footprint |
| Project location | Local workspace directory on C: | A normal directory, not a separate drive or junction; the owner-specific path is omitted from this public report |
| Virtualization | Hypervisor present; two existing WSL 2 distributions running | WSL is already usable; do not interpret the masked CPU virtualization flags as proof it is disabled |
| Project state | Empty directory before planning; no Git repository | Initialize Git during implementation |
| Planned ports | No listeners observed on 8000, 5432, 54320, 3030, or 3031 | Recheck before startup; reserve 8000, 54320, 3030, and 3031 |

RAM and disk are separate budgets. Start with a 768 MiB maximum Java heap for each country graph server and one ingestion worker. A **rough 5–9 GiB incremental RAM allowance** for Docker, graph services, Python, model inference, and a browser is a planning estimate to measure, not a resource reservation. Do not alter global WSL limits: other local projects already use WSL.

## Already installed

| Tool | Observed version or status | Planned use |
|---|---|---|
| Git | 2.53.0.windows.2 | Source history |
| GitHub CLI | 2.88.1; authenticated account confirmed | Future public repository creation |
| Python on `python` | 3.11.9 | Do not accidentally use it for the project environment |
| Python selected by `py -3.12` | 3.12.10 | Project baseline; select explicitly |
| Other Python versions | 3.14 and uv-managed 3.13.14 also registered | No additional interpreter is needed |
| uv | 0.12.2 | Isolated environment, dependency lock, commands |
| Node.js and npm | 24.19.0 and 11.2.0 | Available, but no application frontend build is required |
| Java | Temurin 21.0.10 | Available for native Fuseki or ontology inspection; containers supply their own Java |
| Docker Desktop | 4.88.1 | Already installed |
| Docker CLI and Compose | 29.7.2 and 5.4.0 | Service lifecycle |
| Docker engine | Not reachable; `docker-desktop` WSL distribution stopped | Start it and verify service health during implementation |
| WSL | Default version 2; existing distributions registered | Docker backend; no new Linux distribution is needed |
| Codex CLI | 0.162.0-alpha.17.2; `codex login status` says ChatGPT | Existing authentication confirmed; application will pin its own stable SDK/runtime pair |
| Playwright browser cache | Chromium builds already present, about 1.35 GiB total cache file lengths | Reuse only when compatible with the pinned Python Playwright release |
| uv cache | About 1.90 GiB of file lengths | Existing shared cache; not new project storage |

The public repository target is `fullstack-nick/insurance-semantic-workbench`, with MIT copyright holder **Nick Petrushin**, as confirmed by the owner. A read-only lookup did not resolve a repository at that name. Recheck availability when creating it.

## Components to obtain or configure

| Component | Required action | Need a new machine-wide installation? |
|---|---|---|
| Python application libraries | Create `.venv` using Python 3.12 and install the final locked dependency set | No; project environment only |
| CPU PyTorch and Sentence Transformers | Install the CPU backend explicitly | No CUDA toolkit or GPU packages |
| Python Codex SDK | Install `openai-codex==0.162.1` and its paired runtime initially | No replacement of the desktop app or global CLI |
| Embedding model | Download the pinned `intfloat/multilingual-e5-small` revision once | Model cache only |
| PostgreSQL and pgvector | Obtain the selected container image and initialize a named volume | No native PostgreSQL server or host `psql` needed |
| Apache Jena Fuseki | Build one pinned image from the Apache release, run it twice with separate volumes | No host Maven or Java installation needed |
| Playwright Chromium | Obtain the exact browser revision required by the dependency lock if absent | Browser cache only; install Chromium alone |
| Protégé Desktop | Download when the ontology inspection milestone needs it | Optional for application runtime; useful authoring tool |
| Authentication | Validate SDK account access; if an isolated runtime profile is needed, complete one Codex-managed browser login | No API key or token copying |

Native PostgreSQL executables were absent from PATH and the standard installation directory. Fuseki and Protégé were not found in the inspected normal locations or installed-application registry entries. Portable copies elsewhere were not exhaustively searched. No matching application libraries were found in the default Python 3.11 environment; unrelated environments were not scanned. The project needs its own environment regardless.

## Dependency resolution evidence

The candidate package set in [dependency-candidates.in](research/dependency-candidates.in) resolved successfully to **95 packages** for **Windows x64 and Python 3.12**, with binary wheels required and the CPU PyTorch backend selected. The result is saved in [dependencies-windows-py312.txt](research/dependencies-windows-py312.txt).

The exact research command was:

```powershell
uv pip compile docs/research/dependency-candidates.in --python-version 3.12 --python-platform windows --only-binary :all: --torch-backend cpu --prerelease disallow --no-python-downloads --no-header --no-annotate --output-file docs/research/dependencies-windows-py312.txt
```

This establishes resolver compatibility and availability of wheel candidates. It does **not** establish successful imports, model loading, SDK authentication, database connectivity, or working end-to-end behavior. Phase 0 performs those checks and creates `pyproject.toml` plus `uv.lock`. Keep the explicit CPU index in that configuration; a plain installation of this research requirements file does not carry the index policy. [uv PyTorch integration](https://docs.astral.sh/uv/guides/integration/pytorch/)

## Estimated additional disk usage

Assumptions: CPU embeddings; one model weight format; two Fuseki containers sharing one image; approximately 100 policies, 50 claims, and 32 document versions; bounded logs and test traces; a few retained releases and backups. GiB means 1,073,741,824 bytes.

| Addition | Estimated working space | Rebuildable? |
|---|---:|---|
| Python environment excluding the separately listed Codex runtime | 1.5–3.0 GiB | Yes, from `uv.lock` |
| Pinned Codex SDK/runtime | 0.3–0.7 GiB | Yes; preserve authentication separately |
| Embedding weights and tokenizer | 0.46–0.60 GiB | Yes, by pinned model revision |
| PostgreSQL/pgvector image | 0.4–0.8 GiB | Yes, by image digest |
| Fuseki image, shared by both containers | 0.3–0.8 GiB | Yes, from the Dockerfile and verified Apache artifact |
| Matching Chromium/browser support files | 0.4–0.9 GiB | Yes; existing compatible cache may reduce this |
| Database volumes, source files, and projection snapshots | 0.2–1.0 GiB | Seed data can be rebuilt; manual reviews and audit records need backup |
| Logs, retained E2E traces, screenshots, and backups | 0.5–2.0 GiB | Some reproducible; preserve desired review evidence and backups |
| Additional uv download cache and Docker build cache | 0.8–3.0 GiB | Yes |
| Optional Protégé distribution | 0.2–0.6 GiB | Yes |

The table totals roughly **5–14.4 GiB**; use **6–15 GiB** as the rounded working estimate. Temporary downloads, extraction, repeated builds, and copies can raise the peak to **15–25 GiB**. Keeping **30 GiB free before starting** is a conservative allowance. With 114.1 GiB free, this project alone is not a disk-capacity blocker. Other active projects can change that conclusion.

These totals deliberately allow for copies. uv hardlinks and Docker shared layers can reduce actual allocation, so summing directory file lengths can overcount disk use. Do not add existing caches or existing Docker storage again as if they were new installation costs.

Two concrete size anchors were obtained without downloading the payloads:

- The embedding model's `model.safetensors` is 470,641,600 bytes, about 449 MiB; the tokenizer adds about 21 MiB. Download this format and the required configuration files, not every ONNX, OpenVINO, and alternative weight artifact. [Model file metadata](https://huggingface.co/api/models/intfloat/multilingual-e5-small?blobs=true)
- The selected pgvector image's Linux amd64 download is about 153.1 MiB compressed. Expanded layers and database data need additional space. [Image metadata](https://hub.docker.com/v2/repositories/pgvector/pgvector/tags/0.8.7-pg17-bookworm)

At 10,000 evidence chunks, raw 384-dimensional float32 vectors contain only about **14.6 MiB** of numeric values before database row and index overhead. The database is unlikely to be the dominant cost at the planned scale.

## Docker and a native alternative

Docker remains the draft's recommended arrangement for PostgreSQL/pgvector and two country Fuseki services. It gives reproducible versions, independent graph-service shutdown for the federation demonstration, and project-scoped storage. This assessment does not install Docker or change its settings.

| Arrangement | Expected difference | Tradeoff |
|---|---|---|
| Native Python plus Docker databases | Baseline estimate above | Reuse installed Docker and Java-independent graph containers |
| Native Python, native PostgreSQL/pgvector, native Fuseki | Possibly saves roughly 0.5–2 GiB of this project's layers/cache; highly installation-dependent | More Windows service and extension setup, less convenient reset and process isolation |

Switching this project to native services would not reclaim existing Docker storage from other projects. Containerization is useful for lifecycle management; it does not make persistent data disposable by itself. [Docker volumes](https://docs.docker.com/engine/storage/volumes/)

## Existing Docker disk and cleanup behavior

The existing Docker data VHDX has a **logical file length of about 189.35 GiB**. This is shared, pre-existing Docker storage. Logical length does not establish physical allocated size, live data size, or reclaimable space. The stopped engine prevented `docker system df` and an image/volume inventory; zero values printed in the failed `docker info` response were not treated as an empty installation.

During implementation, use the Compose project name `isw`, named volumes, and a separate `isw-e2e` project for tests. Implement cleanup with an explicit resource inventory:

| Action | Space reclaimed | Data consequence |
|---|---|---|
| Stop services | Primarily RAM | Keeps containers and volumes |
| `docker compose -p isw down` | Containers and project network | Named database volumes remain |
| Remove this project's unused image IDs/build cache | Rebuildable image/cache space | Does not remove named volumes; shared image layers may remain |
| Remove `.venv` or this project's model cache | Rebuildable local files | Future startup needs restore/download; authenticate only if runtime home was also removed |
| Explicit project reset with volume deletion | Database contents | Loses manual work unless backed up; preserve a verified backup first |

`docker compose down` does not remove named volumes by default; `--volumes` changes that behavior. [Compose down reference](https://docs.docker.com/reference/cli/docker/compose/down/)

Removing files inside Docker may make space reusable inside its virtual disk without immediately shrinking the Windows VHDX file. Inspect current Docker/WSL reclamation behavior before offering a physical-space estimate. Do not delete VHDX files, unregister WSL distributions, perform factory resets, or use global `docker system prune --volumes` for this project. Do not clean shared caches automatically.

Keep source code, ontology files, fixture definitions, lockfiles, release manifests, and chosen screenshots. Before deleting persistent application data, back up PostgreSQL, immutable source/evidence files, release artifacts, and the referenced graph snapshots; test restoration. Codex credential storage is excluded from project backups and public Git history.
