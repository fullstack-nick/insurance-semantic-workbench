"""Frozen, authored evidence-level evaluation; no model calls and no manufactured scores."""

import json
import statistics
import time
from importlib.metadata import version

from sqlalchemy import select

from . import db, embedding, operations, publication, retrieval
from .config import ROOT, settings
from .util import digest, new_id

PARAMETERS = {
    "items": 12,
    "tokens": 6000,
    "hops": 3,
    "distance": "exact cosine",
    "graph_candidate_limit": 200,
    "tie_break": "evidence ID",
    "embedding": embedding.MANIFEST,
}


def evaluate():
    if settings().namespace != "isw-e2e":
        raise ValueError("Evaluation requires the isolated isw-e2e workflow history; run Verify-Lab first")
    output = ROOT / "docs/evaluation/retrieval.json"
    reproduction = output.exists()
    if reproduction:
        output = settings().data_root / "reports" / (new_id("retrieval-reproduction") + ".json")
    labels = {}
    for split in ["development", "holdout"]:
        path = ROOT / f"fixtures/evaluation-{split}.json"
        labels[split] = json.loads(path.read_text(encoding="utf-8"))
    freeze = {
        "parameters": PARAMETERS,
        "labels_sha256": {split: digest(rows) for split, rows in labels.items()},
        "corpus_sha256": digest((ROOT / "fixtures/corpus.json").read_bytes()),
        "frozen_at": str(db.now()),
        "policy": "No parameter changes between development and held-out scoring",
    }
    frozen_path = ROOT / "fixtures/retrieval-freeze.json"
    if frozen_path.exists():
        old = json.loads(frozen_path.read_text(encoding="utf-8"))
        if any(old[k] != freeze[k] for k in ["parameters", "labels_sha256", "corpus_sha256"]):
            raise ValueError("Settings or labels changed after freezing")
        freeze = old
    else:
        frozen_path.write_text(json.dumps(freeze, indent=2, ensure_ascii=False), encoding="utf-8")
    current = publication.current()
    with db.engine("reader").connect() as c:
        history = db.many(
            c,
            select(db.projections)
            .where(db.projections.c.state.in_(["active", "ready"]))
            .order_by(db.projections.c.created_at.desc()),
        )
        release = db.one(c, select(db.releases).where(db.releases.c.id == "2.0.0"))
    candidate = publication.current(release["candidate_id"]) if release["candidate_id"] else None
    if not candidate or candidate["watermark"] != current["watermark"]:
        job_id = publication.enqueue("candidate", "2.0.0")
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            with db.engine("reader").connect() as c:
                job = db.one(c, select(db.jobs).where(db.jobs.c.id == job_id))
            if job["state"] == "failed":
                raise ValueError(job["error"])
            if job["state"] == "completed":
                candidate = publication.current(job["payload"]["projection_id"])
                break
            time.sleep(0.5)
        else:
            raise ValueError("Candidate did not finish before the evaluation deadline")

    def select_snapshot(row):
        selection = row.get("selection")
        if selection == "candidate":
            return candidate
        if selection in {"late-endorsement", "stale-cut"}:
            for projection in history:
                case = projection["cases"].get(row["case"], {})
                late = selection == "late-endorsement" and any(
                    v["id"].endswith("-v3") for v in case.get("policy_versions", [])
                )
                stale = selection == "stale-cut" and case.get("claim", {}).get("amount") == "1840.00"
                if projection["release_id"] == "1.0.0" and (late or stale):
                    return publication.current(projection["id"])
            raise ValueError("Missing E2E history for " + row["id"])
        return current

    cold_start = time.perf_counter()
    embedding.encode(["Warm the local embedding model before measurement"], query=True)
    cold_seconds = time.perf_counter() - cold_start
    results = []
    # Labels and parameters are frozen before either split is scored. No tuning in this function.
    for split, questions in labels.items():
        for row in questions:
            snapshot = select_snapshot(row)
            outage = row.get("selection") == "country-outage"
            if outage:
                operations.compose("stop", "fuseki-cz", capture_output=True)
            try:
                federated = retrieval.federation(projection_id=snapshot["id"]) if outage else None
                for mode in retrieval.MODES:
                    bundle = retrieval.retrieve(
                        row["case"], row["question"], mode, snapshot["id"], persist=False
                    )
                    evidence = bundle["evidence"]
                    groups = {e["group_id"].split("/", 1)[1] for e in evidence}
                    required = set(row["required"])
                    case = snapshot["cases"][row["case"]]
                    allowed_sources = {
                        row["case"],
                        case["claim"]["policy_id"],
                        *(v["document_id"] for v in case["policy_versions"]),
                    }
                    forbidden = [
                        e["evidence_id"]
                        for e in evidence
                        if e["case_scope"] != row["case"]
                        or e["country_scope"] != case["country"]
                        or e["source_id"] not in allowed_sources
                        or e["projection_id"] != snapshot["id"]
                        or e["group_id"].split("/", 1)[1] in row.get("forbidden_groups", [])
                    ]
                    for item in evidence:
                        if item["kind"] == "clause" and (
                            not case["claim"].get("loss_date")
                            or case["claim"]["loss_date"] < item["valid_from"]
                            or item.get("valid_to")
                            and case["claim"]["loss_date"] >= item["valid_to"]
                        ):
                            forbidden.append(item["evidence_id"])
                    expected_status = "incomplete" if outage and mode != "vector" else row["status"]
                    results.append(
                        {
                            "id": row["id"],
                            "split": split,
                            "case": row["case"],
                            "mode": mode,
                            "query": row["question"],
                            "projection_id": snapshot["id"],
                            "release": snapshot["release_id"],
                            "watermark": snapshot["watermark"],
                            "release_manifest_hash": snapshot["manifest"]["release_manifest_hash"],
                            "required_groups": sorted(required),
                            "retrieved_groups": sorted(groups),
                            "coverage": len(required & groups) / len(required) if required else None,
                            "useful_precision": len(required & groups) / len(groups)
                            if groups and required
                            else None,
                            "forbidden_evidence_ids": sorted(set(forbidden)),
                            "category_matches": bundle["evidence_status"] == expected_status,
                            "status": bundle["evidence_status"],
                            "completeness": bundle["completeness"],
                            "freshness": bundle["freshness"],
                            "freshness_matches": bundle["freshness"]
                            == row.get("freshness", bundle["freshness"]),
                            "expected_text_found": row.get("text", "")
                            in "\n".join(e["text_or_value"] for e in evidence),
                            "latency_ms": bundle["latency_ms"],
                            "budget": bundle["budget"],
                            "evidence": [
                                {
                                    k: e[k]
                                    for k in [
                                        "evidence_id",
                                        "group_id",
                                        "source_id",
                                        "source_version",
                                        "locator",
                                        "text_or_value",
                                    ]
                                }
                                for e in evidence
                            ],
                            "federation": federated,
                            "cross_country_answer_eligible": False if outage else None,
                        }
                    )
            finally:
                if outage:
                    operations.compose("up", "-d", "--wait", "fuseki-cz", capture_output=True)
    summary = []
    for split in labels:
        for mode in retrieval.MODES:
            rows = [r for r in results if r["split"] == split and r["mode"] == mode]
            latencies = sorted(r["latency_ms"] for r in rows)
            summary.append(
                {
                    "split": split,
                    "mode": mode,
                    "questions": len(rows),
                    "mean_coverage": statistics.mean(
                        r["coverage"] for r in rows if r["coverage"] is not None
                    ),
                    "mean_useful_precision": statistics.mean(
                        r["useful_precision"] for r in rows if r["useful_precision"] is not None
                    ),
                    "forbidden_count": sum(len(r["forbidden_evidence_ids"]) for r in rows),
                    "category_matches": sum(r["category_matches"] for r in rows),
                    "text_matches": sum(r["expected_text_found"] for r in rows),
                    "median_ms": statistics.median(latencies),
                    "p95_ms": latencies[max(0, int(len(rows) * 0.95) - 1)],
                }
            )
    report = {
        "run_type": "reproduction of frozen protocol"
        if reproduction
        else "first frozen development and holdout pass",
        "recorded_at": str(db.now()),
        "freeze": freeze,
        "cold_model_load_and_first_encode_seconds": round(cold_seconds, 3),
        "versions": {p: version(p) for p in ["sentence-transformers", "torch", "pgvector", "rdflib"]},
        "conditions": "Local CPU, exact vector search; one warm pass per question/mode. R27 measures a real outage separately from evidence coverage.",
        "limitations": [
            "Small authored corpus; overlapping E2E business scenarios. Held-out means withheld from retrieval scoring, not an independently sourced benchmark.",
            "Most eligible case contexts fit within the 12-item budget, so coverage can reach a ceiling while useful precision is low.",
            "No parameter tuning followed the development pass. Latency is a single-pass local observation, not a production benchmark.",
        ],
        "summary": summary,
        "results": results,
        "scope_gate_passed": all(not r["forbidden_evidence_ids"] for r in results),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if not report["scope_gate_passed"]:
        raise ValueError("The non-negotiable scope gate failed; inspect the saved report")
    return {
        "questions": 28,
        "retrievals": len(results),
        "scope_gate_passed": True,
        "summary": summary,
        "report": str(output.relative_to(ROOT)),
    }
