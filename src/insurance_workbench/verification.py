"""Executable acceptance checks over the installed semantic engines and live endpoints."""

import json
from importlib.metadata import version

from pyshacl import validate
from rdflib import OWL, RDF, RDFS, Graph
from sqlalchemy import select

from . import artifacts, db, publication, retrieval, semantics
from .config import ROOT
from .util import digest


def semantic_check():
    snapshot = publication.current()
    if not snapshot or "semantic_inputs" not in snapshot["manifest"]:
        raise ValueError("Publish a projection with frozen semantic inputs first")
    root = artifacts.for_snapshot(snapshot)
    ontology = semantics.ontology(snapshot["release_id"], root)
    shapes = semantics.shapes(snapshot["release_id"], root)
    validate(Graph(), shacl_graph=shapes, meta_shacl=True, do_owl_imports=False)
    consumers = json.loads((root / "consumers.json").read_text(encoding="utf-8"))
    unresolved = sorted(
        {
            term
            for consumer in consumers
            for term in consumer["terms"]
            if not list(ontology.triples((semantics.ISW[term], None, None)))
        }
    )
    if unresolved:
        raise ValueError("Unresolved consumer terms: " + str(unresolved))
    expectations = json.loads((ROOT / "fixtures/competency-expectations.json").read_text())
    results = []
    for expected in expectations:
        number = int(expected["id"][2:])
        target = snapshot
        if number == 18:
            with db.engine("reader").connect() as c:
                run = db.one(
                    c,
                    select(db.runs)
                    .where(db.runs.c.case_id == expected["case"], db.runs.c.state == "completed")
                    .order_by(db.runs.c.created_at.desc())
                    .limit(1),
                )
            if run:
                target = publication.current(run["projection_id"])
        rows = retrieval.query_cq(number, expected["case"], target)
        values = [r.get(expected["field"], {}).get("value", "") for r in rows]
        checks = []
        if "exact_rows" in expected:
            checks.append(len(rows) == expected["exact_rows"])
        if "min_rows" in expected:
            checks.append(len(rows) >= expected["min_rows"])
        if "contains" in expected:
            checks.append(any(expected["contains"].lower() in v.lower() for v in values))
        if "values" in expected:
            checks.append(set(values) == set(expected["values"]))
        if "languages" in expected:
            checks.append({r["label"]["xml:lang"] for r in rows} == set(expected["languages"]))
        if "forbidden" in expected:
            checks.append(all(expected["forbidden"] not in v for v in values))
        if number == 9:
            checks.append(all(len(v) == 64 for v in values))
        if number == 18:
            checks.append(bool(rows) if run else rows == [])
            if run:
                checks.append(all(v.endswith(run["projection_id"]) for v in values))
        results.append(
            {
                "id": expected["id"],
                "case": expected["case"],
                "passed": all(checks),
                "row_count": len(rows),
                "projection_id": target["id"],
                "bindings": rows,
            }
        )
    report = {
        "recorded_at": str(db.now()),
        "projection_id": snapshot["id"],
        "release_manifest_hash": snapshot["manifest"]["release_manifest_hash"],
        "corpus_sha256": digest((ROOT / "fixtures/corpus.json").read_bytes()),
        "versions": {name: version(name) for name in ["rdflib", "pyshacl", "owlrl"]},
        "classes": len(set(ontology.subjects(RDF.type, OWL.Class))),
        "properties": len(set(ontology.subjects(RDF.type, RDF.Property))),
        "shapes": len(set(shapes.subjects(RDF.type, semantics.SH.NodeShape))),
        "inference_axiom": [str(semantics.ISW.Policy), str(RDFS.subClassOf), str(semantics.ISW.Contract)],
        "meta_shacl": "passed",
        "unresolved_consumer_terms": unresolved,
        "queries": results,
        "passed": all(r["passed"] for r in results),
    }
    out = ROOT / "docs/verification/semantic.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if not report["passed"]:
        raise ValueError("Failed competency queries: " + str([r["id"] for r in results if not r["passed"]]))
    return {"queries_passed": len(results), "report": "docs/verification/semantic.json"}
