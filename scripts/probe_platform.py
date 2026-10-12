"""An explicit live runtime check; never a substitute for application E2E."""

import hashlib
import json
import time
from pathlib import Path

import httpx
import numpy as np
from pgvector.psycopg import register_vector
from pyshacl import validate
from rdflib import Graph
from sentence_transformers import SentenceTransformer
from sqlalchemy import create_engine

from insurance_workbench.config import settings

s = settings()
engine = create_engine(s.database_url)
with engine.begin() as connection:
    connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
with engine.raw_connection() as connection:
    register_vector(connection.driver_connection)
    with connection.cursor() as cursor:
        cursor.execute("SELECT version(), %s::vector <=> %s::vector", (np.ones(384), np.ones(384)))
        version, distance = cursor.fetchone()
        assert abs(distance) < 0.00001

trig = '@prefix x: <https://example.org/isw/probe/> . x:record x:status "ready" .'
graphs = {}
for country in ["AT", "CZ"]:
    uri = "https://example.org/isw/probe/platform"
    response = httpx.put(
        s.endpoint(country) + "/data",
        params={"graph": uri},
        content=trig,
        headers={"Content-Type": "text/turtle"},
    )
    response.raise_for_status()
    response = httpx.get(
        s.endpoint(country) + "/query",
        params={"query": f"ASK {{ GRAPH <{uri}> {{ ?s ?p ?o }} }}"},
        headers={"Accept": "application/sparql-results+json"},
    )
    response.raise_for_status()
    assert response.json()["boolean"]
    graphs[country] = "write/query passed"

shape = Graph().parse(
    data="""@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix x: <https://example.org/isw/probe/> . x:Shape a sh:NodeShape; sh:targetNode x:record;
sh:property [ sh:path x:required; sh:minCount 1; sh:message "Required source value missing" ].""",
    format="turtle",
)
conforms, _, report = validate(Graph().parse(data=trig, format="turtle"), shacl_graph=shape, meta_shacl=True)
assert not conforms and "Required source value missing" in report
started = time.perf_counter()
model = SentenceTransformer(str(s.model_dir), device="cpu", local_files_only=True, trust_remote_code=False)
vectors = model.encode(
    ["query: pipe leakage", "query: Rohrbruch", "query: únik vody z potrubí"], normalize_embeddings=True
)
assert vectors.shape == (3, 384) and np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-5)
assert model.max_seq_length == 512
result = {
    "postgres": version,
    "vector_roundtrip": "passed",
    "fuseki": graphs,
    "shacl_negative_fixture": "passed",
    "embedding_device": str(model.device),
    "dimension": 384,
    "max_tokens": 512,
    "cold_encode_seconds": round(time.perf_counter() - started, 3),
    "model_sha256": hashlib.file_digest((s.model_dir / "model.safetensors").open("rb"), "sha256").hexdigest(),
}
Path("docs/verification").mkdir(exist_ok=True)
Path("docs/verification/platform.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
