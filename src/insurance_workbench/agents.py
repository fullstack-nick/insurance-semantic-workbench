"""Durable assistant jobs and the server-enforced MCP authorization boundary."""

import asyncio
import hashlib
import hmac
import json
import secrets
from datetime import timedelta
from functools import lru_cache

import httpx
from rdflib import SKOS
from sqlalchemy import insert, select, text, update

from . import artifacts, db, governance, publication, retrieval, semantics
from .agent_contracts import OntologyReview, ReviewBrief
from .codex_gateway import CLAIM_TOOLS, ONTOLOGY_TOOLS, CodexGateway
from .config import settings
from .util import digest, new_id


@lru_cache
def secret():
    path = settings().data_root / "session.key"
    if not path.exists():
        try:
            with path.open("xb") as stream:
                stream.write(secrets.token_bytes(32))
        except FileExistsError:
            pass
    return path.read_bytes()


def token_for(run_id):
    return hmac.new(secret(), run_id.encode(), hashlib.sha256).hexdigest()


def event(run_id, kind, payload=None, connection=None):
    if connection is None:
        with db.engine().begin() as transaction:
            return event(run_id, kind, payload, transaction)
    connection.execute(insert(db.run_events).values(run_id=run_id, kind=kind, payload=payload or {}))


def create_run(case_id=None, role="claim", projection_id=None):
    snapshot = publication.current(projection_id)
    if not snapshot:
        raise ValueError("Publish a snapshot before requesting a review")
    if role not in {"claim", "ontology"}:
        raise ValueError("Unknown assistant role")
    if role == "claim" and case_id not in snapshot["cases"]:
        raise ValueError("Unknown case")
    if role == "claim" and snapshot["cases"][case_id]["quarantined"]:
        raise ValueError("Correct the quarantined source before requesting a cited brief")
    run_id = new_id("run")
    with db.engine().begin() as c:
        c.execute(text("SELECT pg_advisory_xact_lock(91422072)"))
        if db.one(c, select(db.state).where(db.state.c.id == "maintenance")):
            raise ValueError("Assistant starts are paused during backup")
        if db.one(c, select(db.runs).where(db.runs.c.state.in_(["queued", "running"]))):
            raise ValueError("One assistant run is already active")
        c.execute(
            insert(db.runs).values(
                id=run_id,
                case_id=case_id,
                projection_id=snapshot["id"],
                role=role,
                state="queued",
                token_hash=digest(token_for(run_id)),
                expires_at=db.now() + timedelta(seconds=settings().agent_timeout + 90),
            )
        )
        event(run_id, "queued", {"projection_id": snapshot["id"], "release_id": snapshot["release_id"]}, c)
    return run_id


def cancel(run_id):
    with db.engine().begin() as c:
        row = db.one(c, select(db.runs).where(db.runs.c.id == run_id))
        if not row:
            raise ValueError("Unknown run")
        if row["state"] not in {"queued", "running"}:
            return
        c.execute(
            update(db.runs)
            .where(db.runs.c.id == run_id)
            .values(
                cancel_requested=True,
                state="cancelled" if row["state"] == "queued" else "running",
                expires_at=db.now(),
            )
        )
        event(run_id, "cancellation-requested", {}, c)


def scoped_tool(token, name, args):
    with db.engine().begin() as c:
        run = db.one(c, select(db.runs).where(db.runs.c.token_hash == digest(token)).with_for_update())
        if not run or run["state"] != "running" or run["cancel_requested"] or run["expires_at"] < db.now():
            raise PermissionError("Run token is expired, revoked or unknown")
        allowed = CLAIM_TOOLS if run["role"] == "claim" else ONTOLOGY_TOOLS
        if name not in allowed:
            raise PermissionError("Tool is outside the bound role")
        if run["tool_count"] >= settings().tool_budget:
            raise PermissionError("Run tool budget exhausted")
        expected = {
            "resolve_concept": {"text", "language"},
            "retrieve_evidence": {"question", "mode"},
            "get_source_excerpt": {"issued_evidence_id"},
        }.get(name, set())
        if set(args) - expected:
            raise PermissionError("Unknown parameters cannot change the bound scope")
        c.execute(update(db.runs).where(db.runs.c.id == run["id"]).values(tool_count=run["tool_count"] + 1))
        event(run["id"], "tool", {"name": name}, c)
    snapshot = publication.current(run["projection_id"])
    if not snapshot:
        raise PermissionError("Pinned snapshot no longer exists")
    if run["role"] == "ontology":
        impact = governance.impact(snapshot["release_id"])
        if not impact["candidate"] or impact["candidate"]["id"] != run["projection_id"]:
            raise PermissionError("Candidate changed; begin a new review")
        if name == "get_release_diff":
            return {"reference": "release-diff", **impact["diff"]}
        if name == "get_change_impact":
            return {
                "reference": "change-impact",
                "consumers": impact["affected_consumers"],
                "records": impact["changed_records"],
                "unresolved": impact["unresolved_records"],
                "query_comparisons": impact["query_comparisons"],
                "evidence_changes": impact["evidence_changes"][:5],
            }
        return {
            "reference": "candidate-validation",
            "projection_id": snapshot["id"],
            "release_id": snapshot["release_id"],
            "findings": snapshot["validation"],
        }
    case = snapshot["cases"][run["case_id"]]
    if name == "get_case_context":
        return {
            "case_id": case["id"],
            "country": case["country"],
            "claim": case["claim"],
            "evidence_status": case["status"],
            "classification": case["classification"],
            "projection_id": snapshot["id"],
            "semantic_release_id": snapshot["release_id"],
            "freshness": snapshot["freshness"],
        }
    if name == "get_policy_context":
        return {
            "policy_id": case["claim"]["policy_id"],
            "eligible_versions": case["policy_versions"],
            "missing": case["missing"],
            "ambiguous": len(case["candidate_versions"]) > 1,
        }
    if name == "get_validation_report":
        return {"findings": case["findings"], "missing": case["missing"], "conflicts": case["conflicts"]}
    if name == "resolve_concept":
        term = str(args.get("text", ""))[:200].casefold()
        language = args.get("language", "en")
        if language not in {"en", "de", "cs"}:
            raise ValueError("Unsupported vocabulary language")
        graph = semantics.ontology(snapshot["release_id"], artifacts.for_snapshot(snapshot))
        matches = [
            {"concept": str(subject), "label": str(label), "language": label.language}
            for subject, label in graph.subject_objects(SKOS.prefLabel)
            if label.language == language and term in str(label).casefold()
        ]
        return {"concepts": matches[:15], "release_id": snapshot["release_id"]}
    if name == "retrieve_evidence":
        bundle = retrieval.retrieve(
            case["id"], str(args.get("question", "")), args.get("mode", "hybrid"), snapshot["id"]
        )
        with db.engine().begin() as c:
            latest = db.one(c, select(db.runs).where(db.runs.c.id == run["id"]).with_for_update())
            c.execute(
                update(db.runs)
                .where(db.runs.c.id == run["id"])
                .values(
                    issued_ids=sorted(
                        set(latest["issued_ids"]) | {e["evidence_id"] for e in bundle["evidence"]}
                    ),
                    bundle_ids=[*latest["bundle_ids"], bundle["bundle_id"]],
                )
            )
        return bundle
    evidence_id = args.get("issued_evidence_id")
    if evidence_id not in run["issued_ids"]:
        raise PermissionError("Evidence was not issued to this run")
    with db.engine().connect() as c:
        row = db.one(
            c,
            select(db.evidence).where(
                db.evidence.c.id == evidence_id,
                db.evidence.c.case_id == run["case_id"],
                db.evidence.c.projection_id == run["projection_id"],
            ),
        )
    if not row:
        raise PermissionError("Evidence is outside the pinned scope")
    return row["payload"]


def validate_result(raw, run):
    snapshot = publication.current(run["projection_id"])
    if run["role"] == "ontology":
        result = OntologyReview.model_validate_json(raw)
        if result.projection_id != run["projection_id"] or result.release_id != snapshot["release_id"]:
            raise ValueError("Candidate context mismatch")
        if not set(result.report_references) <= {"release-diff", "change-impact", "candidate-validation"}:
            raise ValueError("Unknown report reference")
        return result.model_dump()
    result = ReviewBrief.model_validate_json(raw)
    case = snapshot["cases"][run["case_id"]]
    if (
        result.case_id != run["case_id"]
        or result.projection_id != run["projection_id"]
        or result.semantic_release_id != snapshot["release_id"]
    ):
        raise ValueError("Brief scope does not match the pinned run")
    if set(result.policy_version_ids) != {v["id"] for v in case["policy_versions"]}:
        raise ValueError("Incorrect historical policy versions")
    if not set(result.evidence_bundle_ids) <= set(run["bundle_ids"]):
        raise ValueError("Unknown evidence bundle")
    required_status = "incomplete" if case["status"] == "quarantined" else case["status"]
    if result.evidence_status != required_status:
        raise ValueError("Evidence category disagrees with deterministic findings")
    cited = []
    for item in [*result.observations, *result.conflicts, *result.suggested_next_actions]:
        cited.extend(item.evidence_ids)
    for item in result.missing_information:
        cited.extend(item.related_evidence_ids)
    if not set(cited) <= set(run["issued_ids"]):
        raise ValueError("Citations contain evidence outside this run")
    if case["conflicts"] and not result.conflicts:
        raise ValueError("Conflicting assertions were omitted")
    if case["missing"] and not result.missing_information:
        raise ValueError("Required missing context was omitted")
    return result.model_dump()


async def _execute(run):
    run_id = run["id"]

    async def started(thread_id, turn_id, inventory):
        with db.engine().begin() as c:
            c.execute(
                update(db.runs).where(db.runs.c.id == run_id).values(thread_id=thread_id, turn_id=turn_id)
            )
            event(
                run_id,
                "running",
                {"allowed_tools": CLAIM_TOOLS if run["role"] == "claim" else ONTOLOGY_TOOLS},
                c,
            )

    async def cancelled():
        with db.engine().connect() as c:
            row = db.one(c, select(db.runs).where(db.runs.c.id == run_id))
            return row["cancel_requested"]

    schema = ReviewBrief if run["role"] == "claim" else OntologyReview
    prompt = (
        "Review the bound case. Call get_case_context, get_policy_context, get_validation_report and retrieve_evidence. "
        "Use the returned projection/release/bundle/evidence IDs exactly. Keep all factual observations cited. "
        "Preserve missing and conflicting information and the deterministic evidence_status. Return only the structured review; suggested actions require human review."
        if run["role"] == "claim"
        else "Review the bound semantic candidate using all three provided tools. Cite their reference IDs. Do not approve or activate anything. Return the structured review."
    )
    outcome = "failed"
    result = {}
    error = None
    deadline = asyncio.get_running_loop().time() + settings().agent_timeout
    try:
        for attempt in range(2):
            async with asyncio.timeout_at(deadline):
                answer = await CodexGateway().run(
                    token_for(run_id), run["role"], prompt, schema.model_json_schema(), started, cancelled
                )
            if answer["status"] != "completed":
                raise ValueError("Codex turn did not complete")
            with db.engine().begin() as c:
                c.execute(update(db.runs).where(db.runs.c.id == run_id).values(model=answer.get("model")))
            (settings().data_root / "logs" / f"{run_id}-result.json").write_text(
                json.dumps(answer, ensure_ascii=False, default=str), encoding="utf-8"
            )
            with db.engine().connect() as c:
                latest = db.one(c, select(db.runs).where(db.runs.c.id == run_id))
            try:
                result = validate_result(answer["text"], latest)
                outcome = "completed"
                break
            except ValueError as exc:
                if attempt:
                    raise
                event(run_id, "repair", {"reason": str(exc)[:250]})
                prompt += (
                    "\nA previous attempt failed validation: "
                    + str(exc)
                    + ". Produce a corrected result using the same scoped tools."
                )
        if outcome == "completed":
            event(run_id, "usage", answer.get("usage") or {})
    except asyncio.CancelledError:
        outcome = "cancelled"
        error = "Cancelled by the user or semantic activation"
    except TimeoutError:
        outcome = "timed_out"
        error = "Run exceeded the configured time budget"
    except Exception as exc:  # noqa: BLE001 - persist a bounded failure at the process boundary
        text_ = str(exc)
        outcome = (
            "rate_limited"
            if any(term in text_.lower() for term in ["rate limit", "usage limit", "quota"])
            else "failed"
        )
        error = (type(exc).__name__ + ": " + text_)[:600]
    with db.engine().begin() as c:
        latest = db.one(c, select(db.runs).where(db.runs.c.id == run_id).with_for_update())
        if latest["cancel_requested"] and outcome == "completed":
            outcome, result, error = "cancelled", {}, "Cancelled before the brief was committed"
        c.execute(
            update(db.runs)
            .where(db.runs.c.id == run_id)
            .values(state=outcome, result=result, error=error, finished_at=db.now(), expires_at=db.now())
        )
        event(run_id, outcome, {"error": error}, c)
    if outcome == "completed" and run["role"] == "claim":
        try:
            _brief_graph(run, result)
        except (ValueError, OSError, RuntimeError, httpx.HTTPError) as exc:
            event(run_id, "archive-error", {"error": type(exc).__name__})


def _brief_graph(run, result):
    from rdflib import RDF, Graph

    from .semantics import ENTITY, ISW

    g = Graph()
    node = ENTITY[run["id"]]
    g.add((node, RDF.type, ISW.ReviewBrief))
    g.add((node, ISW.projection, ENTITY[result["projection_id"]]))
    g.add((node, ISW.release, ENTITY["release-" + result["semantic_release_id"]]))
    for bundle in result["evidence_bundle_ids"]:
        g.add((node, ISW.evidenceBundle, ENTITY[bundle]))
    country = publication.current(run["projection_id"])["cases"][run["case_id"]]["country"]
    publication.upload(country, "https://example.org/isw/brief/" + run["id"], g)


async def runner():
    with db.engine().begin() as c:
        c.execute(
            update(db.runs)
            .where(db.runs.c.state == "running")
            .values(state="failed", error="Owned runner restarted; start a new run", expires_at=db.now())
        )
    while True:
        with db.engine().begin() as c:
            run = db.one(
                c,
                select(db.runs)
                .where(db.runs.c.state == "queued")
                .order_by(db.runs.c.created_at)
                .limit(1)
                .with_for_update(),
            )
            if run:
                c.execute(
                    update(db.runs)
                    .where(db.runs.c.id == run["id"])
                    .values(
                        state="running",
                        expires_at=db.now() + timedelta(seconds=settings().agent_timeout * 2 + 60),
                    )
                )
        if run:
            await _execute(run)
        else:
            await asyncio.sleep(0.5)
