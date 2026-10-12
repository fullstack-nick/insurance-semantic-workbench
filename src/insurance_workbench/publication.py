"""Immutable cross-store staging followed by one PostgreSQL pointer switch."""

import time
from datetime import timedelta

import httpx
from rdflib import Graph
from rdflib.compare import to_isomorphic
from sqlalchemy import insert, select, text, update
from sqlalchemy.dialects.postgresql import insert as upsert

from . import artifacts, db, embedding, semantics, sources
from .config import ROOT, settings
from .util import digest, new_id

LOCK = 91422071


def release_manifest(release):
    files = {}
    for path in sorted((ROOT / "semantic").rglob("*")):
        if not path.is_file() or path.suffix not in {".ttl", ".json", ".rq"}:
            continue
        relative = path.relative_to(ROOT / "semantic")
        if relative.parts[0] in {"1.0.0", "2.0.0"} and relative.parts[0] != release:
            continue
        files[str(relative).replace("\\", "/")] = digest(path.read_bytes())
    return {
        "schema_version": 1,
        "release_id": release,
        "files": files,
        "inference": "RDFS",
        "embedding": embedding.MANIFEST,
        "retrieval": {"items": 12, "tokens": 6000, "hops": 3},
        "application": "0.1.0",
        "dependency_lock_sha256": digest((ROOT / "uv.lock").read_bytes()),
        "compose_sha256": digest((ROOT / "compose.yaml").read_bytes()),
        "container_build_sha256": digest((ROOT / "infra/fuseki/Dockerfile").read_bytes()),
        "source_schema": 1,
        "fact_card_template": 2,
        "breaking_change": release == "2.0.0",
        "changes": [
            "Add source-supported pipe leakage and surface flooding concepts",
            "Require a supported specific cause for readiness",
        ]
        if release == "2.0.0"
        else ["Broad water-damage baseline"],
    }


def initialize():
    with db.engine("worker").begin() as c:
        for release in ["1.0.0", "2.0.0"]:
            manifest = release_manifest(release)
            artifacts.freeze(manifest)
            existing = db.one(c, select(db.releases).where(db.releases.c.id == release))
            if existing and existing["manifest"].get("fact_card_template") == 2:
                if existing["manifest"] != manifest:
                    raise ValueError(
                        "Frozen semantic release changed. Create a new release instead of mutating it."
                    )
            elif existing:
                # One-time transition from the unpublished platform-probe manifest.
                c.execute(update(db.releases).where(db.releases.c.id == release).values(manifest=manifest))
            c.execute(
                upsert(db.releases)
                .values(
                    id=release,
                    predecessor="1.0.0" if release == "2.0.0" else None,
                    state="approved" if release == "1.0.0" else "draft",
                    manifest=manifest,
                )
                .on_conflict_do_nothing()
            )
        c.execute(upsert(db.active).values(id=1, release_id="1.0.0", epoch=0).on_conflict_do_nothing())
        for pid, payload in [
            (
                "PROP-REUSE",
                {
                    "title": "Reuse shared water-damage meaning",
                    "decision_kind": "reuse",
                    "target": "water-damage",
                    "rationale": "The CZ source code has the same broad scope. Language is not a country rule.",
                },
            ),
            (
                "PROP-LOCAL",
                {
                    "title": "CZ mitigation assessment",
                    "decision_kind": "local-extension",
                    "target": "MitigationAssessment",
                    "rationale": "The invented CZ workflow needs a separately identified assessment. It is a subtype of shared Assessment.",
                },
            ),
            (
                "PROP-GLOBAL",
                {
                    "title": "Globalize the CZ document checklist",
                    "decision_kind": "reject-global",
                    "target": "Assessment",
                    "rationale": "The country checklist has insufficient shared value and must not redefine the enterprise term.",
                },
            ),
        ]:
            c.execute(
                upsert(db.proposals)
                .values(id=pid, country="CZ", state="proposed", payload=payload)
                .on_conflict_do_nothing()
            )


def enqueue(kind="refresh", release=None, fail_after=None):
    with db.engine("worker").begin() as c:
        pointer = db.one(c, select(db.active).where(db.active.c.id == 1))
        if not pointer:
            raise ValueError("Initialize the project first")
        existing = db.one(
            c, select(db.jobs).where(db.jobs.c.state.in_(["queued", "building"]), db.jobs.c.kind == kind)
        )
        if existing:
            return existing["id"]
        jid = new_id("job")
        c.execute(
            insert(db.jobs).values(
                id=jid,
                kind=kind,
                state="queued",
                payload={
                    "release_id": release or pointer["release_id"],
                    "epoch": pointer["epoch"],
                    "activate": kind == "refresh",
                    "fail_after": fail_after,
                },
            )
        )
        return jid


def sparql(country, query, timeout=5):
    response = httpx.post(
        settings().endpoint(country) + "/query",
        data={"query": query},
        headers={"Accept": "application/sparql-results+json"},
        timeout=timeout,
    )
    response.raise_for_status()
    result = response.json()
    return result.get("results", {}).get("bindings", result)


def upload(country, uri, graph):
    body = graph.serialize(format="nt")
    path = settings().data_root / "graphs" / (digest(uri)[:24] + ".nt")
    path.write_text(body, encoding="utf-8")
    with httpx.Client(timeout=40) as client:
        response = client.put(
            settings().endpoint(country) + "/data",
            params={"graph": uri},
            content=body.encode("utf-8"),
            headers={"Content-Type": "application/n-triples"},
        )
        response.raise_for_status()
        response = client.get(
            settings().endpoint(country) + "/data",
            params={"graph": uri},
            headers={"Accept": "application/n-triples"},
        )
        response.raise_for_status()
    roundtrip = Graph().parse(data=response.text, format="nt")
    expected = str(to_isomorphic(graph).graph_digest())
    if str(to_isomorphic(roundtrip).graph_digest()) != expected:
        raise RuntimeError("RDF graph round-trip digest mismatch")
    return {
        "uri": uri,
        "triples": len(graph),
        "graph_digest": expected,
        "file": path.name,
        "sha256": digest(path.read_bytes()),
        "country": country,
    }


def run_one():
    with db.engine("worker").connect() as lock:
        if not lock.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK}).scalar():
            return False
        lock.commit()
        try:
            with db.engine("worker").begin() as c:
                if db.one(c, select(db.state).where(db.state.c.id == "maintenance")):
                    return False
                job = db.one(
                    c,
                    select(db.jobs)
                    .where(db.jobs.c.state.in_(["queued", "building"]))
                    .order_by(db.jobs.c.created_at)
                    .limit(1)
                    .with_for_update(),
                )
                if not job:
                    pending = db.one(c, select(db.outbox).where(db.outbox.c.state == "queued").limit(1))
                    failed = db.many(c, select(db.jobs).where(db.jobs.c.state == "failed"))
                    blocked = pending and any(
                        pending["event_id"] in row["payload"].get("event_ids", []) for row in failed
                    )
                    if pending and not blocked:
                        enqueue()
                    return False
                c.execute(
                    update(db.jobs)
                    .where(db.jobs.c.id == job["id"])
                    .values(
                        state="building",
                        attempts=job["attempts"] + 1,
                        lease_until=db.now() + timedelta(minutes=10),
                        error=None,
                    )
                )
            try:
                _build_job(job)
            except Exception as exc:  # noqa: BLE001 - persist a bounded failure at the process boundary
                message = f"{type(exc).__name__}: {str(exc)[:500]}"
                with db.engine("worker").begin() as c:
                    c.execute(
                        update(db.jobs).where(db.jobs.c.id == job["id"]).values(state="failed", error=message)
                    )
                    if job["payload"].get("projection_id"):
                        c.execute(
                            update(db.projections)
                            .where(db.projections.c.id == job["payload"]["projection_id"])
                            .values(state="failed", error=message)
                        )
            return True
        finally:
            lock.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK})
            lock.commit()


def _build_job(job):
    payload = job["payload"]
    release = payload["release_id"]
    with db.engine("worker").begin() as c:
        pointer = db.one(c, select(db.active).where(db.active.c.id == 1))
        if pointer["epoch"] != payload["epoch"]:
            c.execute(update(db.jobs).where(db.jobs.c.id == job["id"]).values(state="superseded"))
            return
        pid = payload.get("projection_id")
        projection = db.one(c, select(db.projections).where(db.projections.c.id == pid)) if pid else None
        if projection:
            cut = projection["source_cut"]
        else:
            cut = sources.source_cut(c)
            pid = new_id("prj")
            payload["projection_id"] = pid
            payload["event_ids"] = [
                r["event_id"] for r in db.many(c, select(db.outbox).where(db.outbox.c.state == "queued"))
            ]
            c.execute(
                insert(db.projections).values(
                    id=pid,
                    release_id=release,
                    state="building",
                    source_cut=cut,
                    cases={},
                    validation=[],
                    manifest={},
                    watermark=digest(cut),
                    epoch=payload["epoch"],
                )
            )
            c.execute(update(db.jobs).where(db.jobs.c.id == job["id"]).values(payload=payload))
        records = sources.load_cut(c, cut)
        semantic_inputs = db.one(c, select(db.releases).where(db.releases.c.id == release))["manifest"]
    root = artifacts.resolve(semantic_inputs)
    started = time.perf_counter()
    cases, items, asserted, inferred, findings, reports = semantics.build(records, release, pid, root)
    for country, report in reports.items():
        (settings().data_root / "reports" / f"{pid}-{country}.ttl").write_text(report, encoding="utf-8")
    expanded = []
    for item in items:
        for index, (start, end, passage) in enumerate(embedding.chunks(item["text_or_value"])):
            part = dict(item)
            part["text_or_value"] = passage
            if index or len(passage) != len(item["text_or_value"]):
                part["evidence_id"] = "ev-" + digest([item["evidence_id"], index])[:24]
                if item["kind"] == "clause":
                    part["locator"] = {
                        **item["locator"],
                        "start": item["locator"]["start"] + start,
                        "end": item["locator"]["start"] + end,
                    }
            expanded.append(part)
    # Fixed fixtures fit one chunk. Rebuild graph memberships for any oversized clause chunks.
    if expanded != items:
        items = expanded
        asserted, _ = semantics._graphs(
            records,
            cases,
            items,
            release,
            pid,
            {f["source_id"] for f in findings if f["category"] == "structural" and f["source_id"]},
            root,
        )
        from owlrl import DeductiveClosure, RDFS_Semantics
        from rdflib import Literal

        for country, g in asserted.items():
            whole = Graph() + g
            DeductiveClosure(RDFS_Semantics).expand(whole)
            inferred[country] = Graph()
            for triple in whole - g:
                if not isinstance(triple[0], Literal):
                    inferred[country].add(triple)
    with db.engine("worker").begin() as c:
        c.execute(
            update(db.projections)
            .where(db.projections.c.id == pid)
            .values(state="indexing", cases=cases, validation=findings)
        )
        known = set(c.execute(select(db.embeddings.c.id)).scalars())
    unique = {embedding.cache_key(item["text_or_value"]): item["text_or_value"] for item in items}
    missing = {key: value for key, value in unique.items() if key not in known}
    if missing:
        vectors = embedding.encode(list(missing.values()))
        with db.engine("worker").begin() as c:
            for key, vector in zip(missing, vectors):
                c.execute(
                    upsert(db.embeddings)
                    .values(id=key, manifest_hash=embedding.MANIFEST_HASH, vector=vector)
                    .on_conflict_do_nothing()
                )
    with db.engine("worker").begin() as c:
        for item in items:
            c.execute(
                upsert(db.evidence)
                .values(
                    id=item["evidence_id"],
                    projection_id=pid,
                    case_id=item["case_scope"],
                    country=item["country_scope"],
                    group_id=item["group_id"],
                    kind=item["kind"],
                    text=item["text_or_value"],
                    embedding_id=embedding.cache_key(item["text_or_value"]),
                    payload=item,
                )
                .on_conflict_do_nothing()
            )
    graph_manifest = {}
    for country in ["AT", "CZ"]:
        graph_manifest[country] = {}
        for kind, g in [("asserted", asserted[country]), ("inferred", inferred[country])]:
            uri = f"https://example.org/isw/graph/{pid}/{country}/{kind}"
            graph_manifest[country][kind] = upload(country, uri, g)
        if payload.get("fail_after") == country:
            raise RuntimeError(
                f"Deliberate publication interruption after {country}; previous pointer remains intact"
            )
    manifest = {
        "graphs": graph_manifest,
        "embedding": embedding.MANIFEST,
        "embedding_manifest_hash": embedding.MANIFEST_HASH,
        "evidence_count": len(items),
        "release_manifest_hash": digest(semantic_inputs),
        "semantic_inputs": semantic_inputs,
        "source_watermark": digest(cut),
        "build_seconds": round(time.perf_counter() - started, 3),
        "ready_at": str(db.now()),
    }
    with db.engine("worker").begin() as c:
        current = db.one(c, select(db.active).where(db.active.c.id == 1).with_for_update())
        state = "ready"
        if current["epoch"] != payload["epoch"]:
            state = "superseded"
        elif payload["activate"] and current["release_id"] == release:
            state = "active"
            c.execute(update(db.projections).where(db.projections.c.state == "active").values(state="ready"))
            c.execute(update(db.active).where(db.active.c.id == 1).values(projection_id=pid))
        c.execute(
            update(db.projections)
            .where(db.projections.c.id == pid)
            .values(state=state, manifest=manifest, error=None)
        )
        c.execute(
            update(db.jobs)
            .where(db.jobs.c.id == job["id"])
            .values(state="superseded" if state == "superseded" else "completed", error=None)
        )
        if job["kind"] == "candidate" and state == "ready":
            c.execute(
                update(db.releases)
                .where(db.releases.c.id == release)
                .values(candidate_id=pid, state="reviewable")
            )
        if state == "active":
            for event_id in payload["event_ids"]:
                c.execute(update(db.outbox).where(db.outbox.c.event_id == event_id).values(state="published"))
                c.execute(
                    upsert(db.receipts)
                    .values(event_id=event_id, outcome="published", projection_id=pid)
                    .on_conflict_do_nothing()
                )
        c.execute(
            insert(db.audits).values(
                id=new_id("audit"),
                action="projection." + state,
                payload={"projection_id": pid, "release_id": release, "watermark": digest(cut)},
            )
        )


def current(projection_id=None):
    with db.engine("worker").connect() as c:
        pointer = db.one(c, select(db.active).where(db.active.c.id == 1))
        pid = projection_id or (pointer or {}).get("projection_id")
        projection = db.one(c, select(db.projections).where(db.projections.c.id == pid)) if pid else None
        if projection:
            projection["freshness"] = (
                "current"
                if digest(sources.source_cut(c)) == projection["watermark"]
                and pointer["projection_id"] == pid
                else "stale"
            )
            projection["active_epoch"] = pointer["epoch"]
        return projection


def retry(job_id):
    with db.engine("worker").begin() as c:
        job = db.one(c, select(db.jobs).where(db.jobs.c.id == job_id))
        if not job or job["state"] != "failed":
            raise ValueError("Only a failed job can be retried")
        payload = {**job["payload"], "fail_after": None}
        c.execute(
            update(db.jobs).where(db.jobs.c.id == job_id).values(state="queued", payload=payload, error=None)
        )


def worker():
    while True:
        try:
            worked = run_one()
        except Exception as exc:  # noqa: BLE001 - persist a bounded failure at the process boundary
            print(f"Worker boundary failure: {type(exc).__name__}", flush=True)
            worked = False
        if not worked:
            time.sleep(0.75)
