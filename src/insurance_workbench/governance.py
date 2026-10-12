"""Explicit human decisions, structural diffs, candidate impact and epoch-fenced activation."""

import json

from rdflib.compare import to_canonical_graph
from sqlalchemy import insert, select, update

from . import artifacts, db, publication, retrieval, semantics, sources
from .config import ROOT
from .util import digest, new_id


def diff(old="1.0.0", new="2.0.0", before_root=semantics.SEMANTIC, after_root=semantics.SEMANTIC):
    before = semantics.ontology(old, before_root) + semantics.shapes(old, before_root)
    after = semantics.ontology(new, after_root) + semantics.shapes(new, after_root)

    def triples(graph):
        return {" ".join(term.n3() for term in triple) + " ." for triple in to_canonical_graph(graph)}

    a, b = triples(before), triples(after)
    return {
        "from": old,
        "to": new,
        "added": sorted(b - a),
        "removed": sorted(a - b),
        "mapping_before": json.loads((before_root / old / "mappings.json").read_text()),
        "mapping_after": json.loads((after_root / new / "mappings.json").read_text()),
        "interpretation": "Structural change only; this is not a proof of semantic equivalence",
    }


def impact(release="2.0.0"):
    with db.engine().connect() as c:
        rel = db.one(c, select(db.releases).where(db.releases.c.id == release))
    if not rel:
        raise ValueError("Unknown release")
    candidate = publication.current(rel["candidate_id"]) if rel["candidate_id"] else None
    baseline = publication.current()
    if candidate:
        with db.engine("reader").connect() as c:
            row = db.one(
                c,
                select(db.projections)
                .where(
                    db.projections.c.release_id == rel["predecessor"],
                    db.projections.c.watermark == candidate["watermark"],
                    db.projections.c.state.in_(["ready", "active"]),
                )
                .order_by(db.projections.c.created_at.desc())
                .limit(1),
            )
        if row:
            baseline = publication.current(row["id"])
    changed = []
    if candidate and baseline:
        for cid, after in candidate["cases"].items():
            before = baseline["cases"].get(cid, {})
            fields = {
                key: {"before": before.get(key), "after": after.get(key)}
                for key in ["classification", "status", "missing"]
                if before.get(key) != after.get(key)
            }
            if fields:
                changed.append({"case_id": cid, "changes": fields})
    consumers = json.loads((ROOT / "semantic/consumers.json").read_text())
    changed_terms = {"classification", "cause", "ready"}
    affected = [
        {**consumer, "matched_terms": sorted(set(consumer["terms"]) & changed_terms)}
        for consumer in consumers
        if set(consumer["terms"]) & changed_terms
    ]
    unresolved = [
        cid
        for cid, case in (candidate or {}).get("cases", {}).items()
        if case["classification"] == "water-damage"
    ]
    evidence_changes = []
    query_changes = []
    if candidate and baseline and candidate["state"] in {"ready", "active"}:
        with db.engine("reader").connect() as c:

            def membership(pid):
                return {
                    r["group_id"]: r["text"]
                    for r in db.many(c, select(db.evidence).where(db.evidence.c.projection_id == pid))
                }

            before, after = membership(baseline["id"]), membership(candidate["id"])
        evidence_changes = [
            {"group_id": group, "before": before.get(group), "after": after.get(group)}
            for group in sorted(before.keys() | after.keys())
            if before.get(group) != after.get(group)
        ]
        import httpx

        for cid in ["CLM-AT-002", "CLM-AT-004", "CLM-AT-005"]:
            try:
                query_changes.append(
                    {
                        "query": "CQ16",
                        "case_id": cid,
                        "before": retrieval.query_cq(16, cid, baseline),
                        "after": retrieval.query_cq(16, cid, candidate),
                    }
                )
            except httpx.HTTPError:
                query_changes.append({"query": "CQ16", "case_id": cid, "status": "endpoint unavailable"})
    return {
        "release": rel,
        "candidate": candidate,
        "diff": diff(
            before_root=artifacts.for_snapshot(baseline) if baseline else semantics.SEMANTIC,
            after_root=artifacts.for_snapshot(candidate)
            if candidate and candidate["manifest"]
            else semantics.SEMANTIC,
        ),
        "affected_consumers": affected,
        "changed_records": changed,
        "evidence_changes": evidence_changes,
        "query_comparisons": query_changes,
        "unresolved_records": unresolved,
        "baseline_id": baseline["id"] if baseline else None,
        "candidate_fresh": bool(candidate and candidate["watermark"] == _current_watermark()),
    }


def _current_watermark():
    with db.engine().connect() as c:
        return digest(sources.source_cut(c))


def approve_release(release, rationale):
    if not rationale.strip():
        raise ValueError("Record the human review rationale")
    with db.engine().begin() as c:
        rel = db.one(c, select(db.releases).where(db.releases.c.id == release).with_for_update())
        if not rel or rel["state"] != "reviewable":
            raise ValueError("Build and inspect a candidate before approval")
        candidate = db.one(c, select(db.projections).where(db.projections.c.id == rel["candidate_id"]))
        if candidate["state"] != "ready" or candidate["watermark"] != digest(sources.source_cut(c)):
            raise ValueError("Candidate is incomplete or stale; rebuild before approval")
        c.execute(update(db.releases).where(db.releases.c.id == release).values(state="approved"))
        c.execute(
            insert(db.decisions).values(
                id=new_id("decision"),
                projection_id=candidate["id"],
                actor="architect",
                action="approve-release",
                rationale=rationale,
                payload={"release_id": release},
            )
        )


def activate(release):
    with db.engine().begin() as c:
        rel = db.one(c, select(db.releases).where(db.releases.c.id == release).with_for_update())
        if not rel or rel["state"] != "approved" or not rel["candidate_id"]:
            raise ValueError("Explicit approval of a ready candidate is required")
        candidate = db.one(c, select(db.projections).where(db.projections.c.id == rel["candidate_id"]))
        if candidate["state"] not in {"ready", "active"}:
            raise ValueError("Candidate artifacts are not complete")
        if candidate["watermark"] != digest(sources.source_cut(c)):
            raise ValueError("Source cut changed after approval; rebuild")
        _switch(c, candidate, "activate")
        c.execute(update(db.releases).where(db.releases.c.id == release).values(state="active"))


def rollback(projection_id, rationale):
    if not rationale.strip():
        raise ValueError("Rollback needs a human rationale")
    with db.engine().begin() as c:
        candidate = db.one(c, select(db.projections).where(db.projections.c.id == projection_id))
        if not candidate or candidate["state"] not in {"ready", "active"}:
            raise ValueError("Select a complete retained projection")
        if projection_id not in previously_active(c):
            raise ValueError("Rollback requires a previously active snapshot; a new candidate needs approval")
        _switch(c, candidate, "rollback")
        c.execute(
            insert(db.decisions).values(
                id=new_id("decision"),
                projection_id=projection_id,
                actor="architect",
                action="rollback",
                rationale=rationale,
                payload={},
            )
        )


def previously_active(c):
    return {
        row["payload"].get("projection_id", row["payload"].get("to"))
        for row in db.many(
            c, select(db.audits).where(db.audits.c.action.in_(["projection.active", "activate", "rollback"]))
        )
    }


def _switch(c, candidate, action):
    pointer = db.one(c, select(db.active).where(db.active.c.id == 1).with_for_update())
    epoch = pointer["epoch"] + 1
    c.execute(update(db.projections).where(db.projections.c.state == "active").values(state="ready"))
    c.execute(update(db.projections).where(db.projections.c.id == candidate["id"]).values(state="active"))
    c.execute(update(db.releases).where(db.releases.c.state == "active").values(state="superseded"))
    c.execute(update(db.releases).where(db.releases.c.id == candidate["release_id"]).values(state="active"))
    c.execute(
        update(db.active)
        .where(db.active.c.id == 1)
        .values(projection_id=candidate["id"], release_id=candidate["release_id"], epoch=epoch)
    )
    c.execute(update(db.jobs).where(db.jobs.c.state.in_(["queued", "building"])).values(state="superseded"))
    for run in db.many(c, select(db.runs).where(db.runs.c.state.in_(["queued", "running"]))):
        queued = run["state"] == "queued"
        c.execute(
            update(db.runs)
            .where(db.runs.c.id == run["id"])
            .values(
                state="cancelled" if queued else "running",
                cancel_requested=True,
                expires_at=db.now(),
                finished_at=db.now() if queued else None,
            )
        )
        c.execute(
            insert(db.run_events).values(
                run_id=run["id"],
                kind="cancelled" if queued else "cancellation-requested",
                payload={"reason": "Semantic activation changed the pinned context"},
            )
        )
    c.execute(
        insert(db.audits).values(
            id=new_id("audit"),
            action=action,
            payload={"from": pointer["projection_id"], "to": candidate["id"], "epoch": epoch},
        )
    )


def propose(country, title, target, rationale, case_id=None):
    if not title.strip() or not rationale.strip():
        raise ValueError("Describe the meaning and evidence")
    if target not in {"water-damage", "pipe-leakage", "surface-flooding", "MitigationAssessment"}:
        raise ValueError("Unknown target concept")
    pid = new_id("proposal")
    with db.engine().begin() as c:
        c.execute(
            insert(db.proposals).values(
                id=pid,
                country=country,
                state="proposed",
                payload={
                    "title": title,
                    "target": target,
                    "rationale": rationale,
                    "case_id": case_id,
                    "decision_kind": "case-narrowing" if case_id else "mapping",
                },
            )
        )
    return pid


def decide_proposal(proposal_id, decision, rationale):
    if decision not in {"approved", "rejected"} or not rationale.strip():
        raise ValueError("Choose a decision and record its rationale")
    with db.engine().begin() as c:
        row = db.one(c, select(db.proposals).where(db.proposals.c.id == proposal_id).with_for_update())
        if not row or row["state"] != "proposed":
            raise ValueError("Proposal is no longer awaiting a decision")
        payload = row["payload"]
        if decision == "approved" and payload.get("case_id"):
            snapshot = publication.current()
            case = snapshot["cases"].get(payload["case_id"])
            if not case or case["country"] != row["country"]:
                raise ValueError("Case is outside proposal country")
            observations = case["claim"]["observations"]
            causes = {obs["cause"] for obs in observations}
            if causes != {payload["target"]}:
                raise ValueError("Source assertions do not unambiguously support that narrowing")
            payload = {
                **payload,
                "supporting_source": case["claim_source"],
                "activation_rule": "Applied only in a release that approves the specific concept",
            }
        if decision == "approved" and payload.get("decision_kind") == "reject-global":
            raise ValueError("This proposal is explicitly scoped for rejection; retain the country extension")
        c.execute(
            update(db.proposals)
            .where(db.proposals.c.id == proposal_id)
            .values(state=decision, payload=payload)
        )
        c.execute(
            insert(db.decisions).values(
                id=new_id("decision"),
                case_id=payload.get("case_id"),
                actor="steward",
                action="proposal." + decision,
                rationale=rationale,
                payload={"proposal_id": proposal_id, **payload},
            )
        )


def review(case_id, action, rationale, projection_id):
    if action not in {"request-information", "escalate-conflict", "review-complete"}:
        raise ValueError("Unknown disposition")
    if not rationale.strip():
        raise ValueError("A human review note is required")
    projection = publication.current(projection_id)
    if not projection or case_id not in projection["cases"]:
        raise ValueError("Invalid review context")
    with db.engine().begin() as c:
        c.execute(
            insert(db.decisions).values(
                id=new_id("decision"),
                case_id=case_id,
                projection_id=projection_id,
                actor="handler",
                action=action,
                rationale=rationale,
                payload={"kind": "human", "scope": "evidence review; no coverage or payment decision"},
            )
        )
