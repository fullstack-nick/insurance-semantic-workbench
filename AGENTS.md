# Project instructions

Read `IMPLEMENTATION_PLAN.md` before implementing this project. Preserve these owner requirements across future work:

- Build an independent Insurance Semantic Workbench using only invented insurance organizations, products, contracts, people, data, and country operating rules. Do not reference real insurers or their products, imply affiliation, or include employer/recruitment context in names, fixtures, documentation, screenshots, or repository metadata.
- Local deployment only. Codex model inference may use the owner's ChatGPT sign-in as documented; keep the distinction clear.
- No cloud deployment, CI/CD, GitHub Actions, unit tests, or API-key fallback. Prefer a compact real-service E2E suite. Add only genuinely necessary live integration checks, with seven as a ceiling rather than a quota.
- Keep the planned Python/FastAPI/Jinja, PostgreSQL/pgvector, Fuseki, RDFLib/pySHACL, local embedding, and scoped Codex/MCP architecture unless evidence requires an explained change.
- The confirmed future public repository is `fullstack-nick/insurance-semantic-workbench`. The license is MIT; copyright holder is Nick Petrushin.
- The final README must be portfolio-ready, accurately explain implemented behavior and practiced architecture, include an architecture diagram and real screenshots, and link measured verification/evaluation results.
- Do not commit credentials, personal Codex configuration, model weights, database contents, caches, logs, raw test traces, or backups. Keep human decisions and original evidence distinct from generated suggestions.
- Scope lifecycle and cleanup operations to this project's resources. Preserve unrelated Docker/WSL workloads and user files. Back up non-rebuildable review/audit data before an explicit data reset.
- Do not claim a live integration, installation, test, benchmark, backup restore, repository publication, or application feature has succeeded until it has actually been verified.

IMPLEMENTATION_PLAN.md preserves the original build baseline. Current installed behavior and measured checks are documented in docs/IMPLEMENTATION_STATUS.md and docs/verification.md. Preserve the distinction between historical planning claims and verified runtime evidence.
