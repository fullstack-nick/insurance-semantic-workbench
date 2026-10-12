"""Three real retrieval paths share only deterministic scope and time eligibility."""

import time

import httpx
from sqlalchemy import insert, select

from . import artifacts, db, embedding, publication
from .util import new_id, serializable

MODES = ("vector", "graph", "hybrid")


def get_case(case_id, projection=None):
    snapshot = projection or publication.current()
    if not snapshot or case_id not in snapshot["cases"]:
        raise ValueError("Case is unavailable in this snapshot")
    return snapshot, snapshot["cases"][case_id]


def query_cq(number, case_id, snapshot):
    if number not in range(1, 19):
        raise ValueError("Unknown competency query")
    case = snapshot["cases"].get(case_id)
    if not case:
        raise ValueError("Case is outside the snapshot")
    country = case["country"]
    query = (artifacts.for_snapshot(snapshot) / f"queries/CQ{number:02d}.rq").read_text(encoding="utf-8")
    query = query.replace("$CASE", "https://example.org/isw/entity/" + case_id)
    graph_uri = snapshot["manifest"]["graphs"]["AT" if number == 17 else country]["asserted"]["uri"]
    if number == 18:
        with db.engine("reader").connect() as c:
            run = db.one(
                c,
                select(db.runs)
                .where(
                    db.runs.c.case_id == case_id,
                    db.runs.c.projection_id == snapshot["id"],
                    db.runs.c.state == "completed",
                )
                .order_by(db.runs.c.created_at.desc())
                .limit(1),
            )
        if not run:
            return []
        graph_uri = "https://example.org/isw/brief/" + run["id"]
    query = query.replace("$GRAPH", graph_uri)
    query = query.replace("$OTHER_GRAPH", snapshot["manifest"]["graphs"]["CZ"]["asserted"]["uri"])
    query = query.replace("$INFERRED_GRAPH", snapshot["manifest"]["graphs"][country]["inferred"]["uri"])
    return publication.sparql("AT" if number == 17 else country, query)


def _graph_ids(case, snapshot):
    uri = snapshot["manifest"]["graphs"][case["country"]]["asserted"]["uri"]
    query = f"""PREFIX isw: <https://example.org/isw/term/>
    SELECT DISTINCT ?evidence WHERE {{ GRAPH <{uri}> {{
    <https://example.org/isw/entity/{case["id"]}> isw:evidence ?evidence .
    ?evidence isw:groupId ?group . }} }} LIMIT 200"""
    return [row["evidence"]["value"].rsplit("/", 1)[-1] for row in publication.sparql(case["country"], query)]


def retrieve(case_id, question, mode="hybrid", projection_id=None, persist=True):
    if mode not in MODES:
        raise ValueError("Choose vector, graph or hybrid")
    if not question.strip() or len(question) > 1500:
        raise ValueError("Question must contain 1–1500 characters")
    started = time.perf_counter()
    snapshot, case = get_case(case_id, publication.current(projection_id))
    completeness = "complete"
    errors = []
    ids = None
    if mode in {"graph", "hybrid"}:
        try:
            ids = _graph_ids(case, snapshot)
        except (httpx.HTTPError, ValueError) as exc:
            ids = []
            completeness = "unavailable"
            errors = [f"{case['country']} graph endpoint unavailable ({type(exc).__name__})"]
    with db.engine("reader").connect() as c:
        statement = select(db.evidence).where(
            db.evidence.c.case_id == case_id,
            db.evidence.c.country == case["country"],
            db.evidence.c.projection_id == snapshot["id"],
        )
        if ids is not None:
            statement = statement.where(db.evidence.c.id.in_(ids))
        if mode in {"vector", "hybrid"} and completeness == "complete":
            vector = embedding.encode([question], query=True)[0]
            distance = db.embeddings.c.vector.cosine_distance(vector)
            statement = (
                statement.add_columns(distance.label("distance"))
                .join(db.embeddings, db.evidence.c.embedding_id == db.embeddings.c.id)
                .order_by(distance, db.evidence.c.id)
            )
        else:
            statement = statement.order_by(db.evidence.c.id)
        rows = db.many(c, statement)
    mandatory = {"claim", "policy", "coverage"}
    if case["conflicts"]:
        mandatory.update("assertion-" + o["id"] for o in case["conflicts"])
    if mode == "graph":
        words = question.casefold()

        def graph_order(row):
            group = row["group_id"].split("/", 1)[1]
            relevant = any(word in words for word in group.replace("clause-", "").split("-"))
            return (group not in mandatory, not relevant, group)

        rows.sort(key=graph_order)
    elif mode == "hybrid":
        rows.sort(
            key=lambda r: (r["group_id"].split("/", 1)[1] not in mandatory, r.get("distance", 2), r["id"])
        )
    chosen = []
    tokens = 0
    for row in rows:
        count = len(embedding.tokenizer().encode(row["text"], add_special_tokens=False))
        if len(chosen) >= 12 or tokens + count > 6000:
            continue
        tokens += count
        chosen.append({**row["payload"], "cosine_distance": row.get("distance")})
    required = {f"{case_id}/{g}" for g in mandatory}
    included = {i["group_id"] for i in chosen}
    bundle = {
        "bundle_id": new_id("bundle"),
        "schema_version": 1,
        "case_id": case_id,
        "country": case["country"],
        "query": question,
        "mode": mode,
        "projection_id": snapshot["id"],
        "semantic_release_id": snapshot["release_id"],
        "source_watermark": snapshot["watermark"],
        "freshness": snapshot["freshness"],
        "evidence": chosen,
        "evidence_status": "incomplete"
        if completeness != "complete"
        else "incomplete"
        if case["status"] == "quarantined"
        else case["status"],
        "missing": case["missing"],
        "conflicts": case["conflicts"],
        "completeness": completeness,
        "endpoint_errors": errors,
        "budget": {
            "items": 12,
            "tokens": 6000,
            "used_tokens": tokens,
            "truncated": len(chosen) < len(rows),
            "omitted_required_groups": sorted(required - included),
        },
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
    }
    if persist:
        with db.engine().begin() as c:
            c.execute(
                insert(db.bundles).values(
                    id=bundle["bundle_id"],
                    case_id=case_id,
                    projection_id=snapshot["id"],
                    payload=serializable(bundle),
                )
            )
    return bundle


def federation(partial=False, projection_id=None):
    snapshot = publication.current(projection_id)
    if not snapshot:
        return {"completeness": "unavailable", "rows": [], "endpoints": {}, "error": "No published snapshot"}
    if not partial:
        try:
            rows = query_cq(17, next(iter(snapshot["cases"])), snapshot)
            return {
                "completeness": "complete",
                "rows": rows,
                "endpoints": {"AT": "available", "CZ": "available"},
                "projection_id": snapshot["id"],
            }
        except httpx.HTTPError:
            return {
                "completeness": "unavailable",
                "rows": [],
                "endpoints": {"AT": "coordinator or required endpoint failed", "CZ": "not confirmed"},
                "projection_id": snapshot["id"],
            }
    rows = []
    endpoints = {}
    for country in ["AT", "CZ"]:
        uri = snapshot["manifest"]["graphs"][country]["asserted"]["uri"]
        query = f"""PREFIX isw: <https://example.org/isw/term/> SELECT ?country ?ready (COUNT(?claim) AS ?count)
        WHERE {{ GRAPH <{uri}> {{ ?claim a isw:Claim; isw:country ?country; isw:ready ?ready }} }} GROUP BY ?country ?ready"""
        try:
            rows.extend(publication.sparql(country, query))
            endpoints[country] = "available"
        except httpx.HTTPError:
            endpoints[country] = "unavailable"
    good = sum(value == "available" for value in endpoints.values())
    return {
        "completeness": "complete" if good == 2 else "partial" if good else "unavailable",
        "rows": rows,
        "endpoints": endpoints,
        "projection_id": snapshot["id"],
    }
