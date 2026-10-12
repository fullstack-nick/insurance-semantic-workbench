# 001 — Native Python with containerized local databases

Use one Python/FastAPI/Jinja application, one publication worker, one assistant runner, PostgreSQL/pgvector and separate AT/CZ Fuseki services. Python and CPU embeddings stay native so the official Windows Codex runtime can use its managed ChatGPT profile. Docker gives the databases repeatable versions, independent outage demonstrations and scoped volumes.

No cloud, CI/CD, Node build pipeline, message broker or orchestration cluster is needed at this scale. The tradeoff is a Windows-first setup rather than a single portable application image. Separate namespaces and process ownership protect unrelated workloads; stopping containers does not discard persistent review history.

Host Fuseki ports are 13030/13031 because Windows reserved 3030/3031 on the measured host. Internal federation continues to use Compose DNS and port 3030.
