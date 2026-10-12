"""Local server-rendered workbench and narrow source/agent APIs."""

import asyncio
import hmac
import json
import secrets
import time
from contextlib import asynccontextmanager
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from rdflib import SKOS
from sqlalchemy import select, text
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import agents, artifacts, db, embedding, governance, publication, retrieval, semantics, sources
from .codex_gateway import account_state
from .config import ROOT
from .util import serializable


@asynccontextmanager
async def lifespan(app):
    # Model initialization belongs to readiness, outside a bounded MCP tool request.
    await asyncio.to_thread(embedding.encode, ["Prepare local retrieval"], query=True)
    await asyncio.to_thread(embedding.tokenizer)
    yield


app = FastAPI(title="Insurance Semantic Workbench", docs_url=None, redoc_url=None, lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
app.mount("/static", StaticFiles(directory=ROOT / "src/insurance_workbench/static"), name="static")
templates = Jinja2Templates(directory=ROOT / "src/insurance_workbench/templates")


def signature(value):
    import hashlib

    return hmac.new(agents.secret(), value.encode(), hashlib.sha256).hexdigest()


@app.middleware("http")
async def local_boundary(request, call_next):
    value = request.cookies.get("isw_session", "")
    parts = value.split(".")
    valid = len(parts) == 2 and hmac.compare_digest(signature(parts[0]), parts[1])
    sid = parts[0] if valid else secrets.token_hex(24)
    request.state.csrf = signature("csrf:" + sid)
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and not request.url.path.startswith(
        "/internal/agent/"
    ):
        origin = request.headers.get("origin")
        if origin and origin != str(request.base_url).rstrip("/"):
            return JSONResponse({"detail": "Same-origin requests only"}, status_code=403)
        body = await request.body()
        if len(body) > 2_000_000:
            return JSONResponse({"detail": "Source payload too large"}, status_code=413)
        token = request.headers.get("x-csrf-token", "")
        if request.headers.get("content-type", "").startswith("application/x-www-form-urlencoded"):
            token = parse_qs(body.decode()).get("csrf", [""])[0]
        if not valid or not hmac.compare_digest(token, request.state.csrf):
            return JSONResponse({"detail": "Invalid session CSRF token"}, status_code=403)
        with db.engine().connect() as connection:
            if db.one(connection, select(db.state).where(db.state.c.id == "maintenance")):
                return JSONResponse(
                    {"detail": "Project writes are paused for backup or restore"}, status_code=503
                )
    response = await call_next(request)
    if not valid:
        response.set_cookie(
            "isw_session", sid + "." + signature(sid), httponly=True, samesite="strict", max_age=86400
        )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    )
    return response


@app.exception_handler(ValueError)
async def bad_input(request, exc):
    if request.url.path.startswith(("/api/", "/internal/")):
        return JSONResponse({"detail": str(exc)[:600]}, status_code=400)
    return render(request, "error.html", title="This action needs attention", error=str(exc), status_code=400)


@app.exception_handler(PermissionError)
async def denied(request, exc):
    return JSONResponse({"detail": str(exc)[:300]}, status_code=403)


def render(request, name, status_code=200, **context):
    snapshot = context.pop("snapshot", None) or publication.current()
    return templates.TemplateResponse(
        request=request,
        name=name,
        context={
            "request": request,
            "csrf": request.state.csrf,
            "snapshot": snapshot,
            "role": request.cookies.get("isw_role", "handler"),
            "path": request.url.path,
            **context,
        },
        status_code=status_code,
    )


def redirect(path):
    return RedirectResponse(path, status_code=303)


@app.get("/", response_class=HTMLResponse)
@app.get("/cases", response_class=HTMLResponse)
def cases_page(request: Request, country: str = "", status: str = "", q: str = "", freshness: str = ""):
    snapshot = publication.current()
    cases = list((snapshot or {}).get("cases", {}).values())
    counts = {
        "all": len(cases),
        "ready": sum(c["status"] == "sufficient" for c in cases),
        "attention": sum(c["status"] != "sufficient" for c in cases),
    }
    filtered = [
        c
        for c in cases
        if (not country or c["country"] == country)
        and (not freshness or snapshot["freshness"] == freshness)
        and (not status or c["status"] == status)
        and (not q or q.casefold() in (c["id"] + c["summary"] + c["claim"]["policy_id"]).casefold())
    ]
    return render(
        request,
        "cases.html",
        title="Case workspace",
        cases=filtered,
        counts=counts,
        filters={"country": country, "status": status, "q": q, "freshness": freshness},
        snapshot=snapshot,
    )


@app.get("/cases/{case_id}", response_class=HTMLResponse)
def case_page(request: Request, case_id: str, projection_id: str | None = None):
    snapshot, case = retrieval.get_case(case_id, publication.current(projection_id))
    with db.engine().connect() as c:
        evidence = db.many(
            c,
            select(db.evidence)
            .where(db.evidence.c.projection_id == snapshot["id"], db.evidence.c.case_id == case_id)
            .order_by(db.evidence.c.group_id),
        )
        runs = db.many(
            c, select(db.runs).where(db.runs.c.case_id == case_id).order_by(db.runs.c.created_at.desc())
        )
        decisions = db.many(
            c,
            select(db.decisions)
            .where(db.decisions.c.case_id == case_id)
            .order_by(db.decisions.c.created_at.desc()),
        )
    return render(
        request,
        "case.html",
        title=case_id,
        case=case,
        evidence=evidence,
        runs=runs,
        decisions=decisions,
        snapshot=snapshot,
    )


@app.get("/sources/{identifier}", response_class=HTMLResponse)
def source_page(request: Request, identifier: str):
    with db.engine().connect() as c:
        evidence = db.one(c, select(db.evidence).where(db.evidence.c.id == identifier))
        source_id = evidence["payload"]["source_snapshot_id"] if evidence else identifier
        source = db.one(c, select(db.snapshots).where(db.snapshots.c.id == source_id))
        if not source:
            raise ValueError("Unknown immutable source identifier")
        head = db.one(c, select(db.heads).where(db.heads.c.aggregate_id == source["aggregate_id"]))
        history = db.many(
            c,
            select(db.snapshots)
            .where(db.snapshots.c.aggregate_id == source["aggregate_id"])
            .order_by(db.snapshots.c.version.desc()),
        )
    return render(
        request,
        "source.html",
        title="Original source",
        source=source,
        evidence=evidence,
        historical=not head or head["snapshot_id"] != source_id,
        history=history,
        raw=json.dumps(source["payload"], indent=2, ensure_ascii=False),
    )


@app.get("/terminology", response_class=HTMLResponse)
def terminology(request: Request, q: str = ""):
    snapshot = publication.current()
    release = snapshot["release_id"] if snapshot else "1.0.0"
    graph = semantics.ontology(release, artifacts.for_snapshot(snapshot) if snapshot else semantics.SEMANTIC)
    terms = []
    for subject in set(graph.subjects(predicate=SKOS.prefLabel)):
        labels = {label.language: str(label) for label in graph.objects(subject, SKOS.prefLabel)}
        if q and q.casefold() not in str(labels).casefold():
            continue
        terms.append(
            {
                "id": str(subject),
                "slug": str(subject).rsplit("/", 1)[-1],
                "labels": labels,
                "definition": str(graph.value(subject, SKOS.definition)),
                "broader": [str(x).rsplit("/", 1)[-1] for x in graph.objects(subject, SKOS.broader)],
            }
        )
    with db.engine().connect() as c:
        proposals = db.many(c, select(db.proposals).order_by(db.proposals.c.created_at))
    return render(
        request,
        "terminology.html",
        title="Terminology & stewardship",
        terms=sorted(terms, key=lambda t: t["labels"].get("en", "")),
        proposals=proposals,
        q=q,
    )


@app.get("/validation", response_class=HTMLResponse)
def validation(request: Request):
    snapshot = publication.current()
    return render(
        request, "validation.html", title="Validation queue", findings=(snapshot or {}).get("validation", [])
    )


@app.get("/releases", response_class=HTMLResponse)
def release_page(request: Request):
    impact = governance.impact()
    with db.engine().connect() as c:
        projections = db.many(
            c,
            select(db.projections)
            .where(db.projections.c.state.in_(["ready", "active"]))
            .order_by(db.projections.c.created_at.desc()),
        )
        retained = governance.previously_active(c)
        projections = [p for p in projections if p["id"] in retained]
        decisions = db.many(
            c,
            select(db.decisions)
            .where(db.decisions.c.actor == "architect")
            .order_by(db.decisions.c.created_at.desc()),
        )
    return render(
        request,
        "releases.html",
        title="Semantic releases",
        impact=impact,
        projections=projections,
        decisions=decisions,
    )


@app.get("/compare", response_class=HTMLResponse)
def compare(
    request: Request,
    case_id: str = "CLM-AT-001",
    question: str = "Which policy terms and evidence apply to this claim?",
):
    snapshot = publication.current()
    bundles = []
    if snapshot:
        for mode in retrieval.MODES:
            bundles.append(retrieval.retrieve(case_id, question, mode, snapshot["id"], persist=False))
    memberships = [{e["group_id"] for e in b["evidence"]} for b in bundles]
    overlap = {
        "shared": len(set.intersection(*memberships)) if memberships else 0,
        "union": len(set.union(*memberships)) if memberships else 0,
    }
    return render(
        request,
        "compare.html",
        title="Retrieval comparison",
        bundles=bundles,
        overlap=overlap,
        case_id=case_id,
        question=question,
        snapshot=snapshot,
    )


@app.get("/federation", response_class=HTMLResponse)
def federation_page(request: Request, partial: bool = False):
    return render(
        request,
        "federation.html",
        title="Country federation",
        result=retrieval.federation(partial),
        partial=partial,
    )


@app.get("/status", response_class=HTMLResponse)
def status_page(request: Request):
    with db.engine().connect() as c:
        jobs = db.many(c, select(db.jobs).order_by(db.jobs.c.created_at.desc()).limit(20))
        runs = db.many(c, select(db.runs).order_by(db.runs.c.created_at.desc()).limit(10))
        backup = db.one(c, select(db.state).where(db.state.c.id == "last-backup"))
        counts = {"source_versions": c.execute(select(db.snapshots.c.id)).rowcount}
    return render(
        request,
        "status.html",
        title="Local system",
        health=health(),
        jobs=jobs,
        runs=runs,
        backup=backup,
        counts=counts,
    )


@app.get("/runs/{run_id}", response_class=HTMLResponse)
def run_page(request: Request, run_id: str):
    with db.engine().connect() as c:
        run = db.one(c, select(db.runs).where(db.runs.c.id == run_id))
        events = db.many(
            c, select(db.run_events).where(db.run_events.c.run_id == run_id).order_by(db.run_events.c.id)
        )
    if not run:
        raise ValueError("Unknown assistant run")
    snapshot = publication.current(run["projection_id"])
    return render(
        request, "run.html", title="Evidence review brief", run=run, events=events, snapshot=snapshot
    )


@app.get("/api/v1/health")
def health():
    services = {}
    started = time.perf_counter()
    try:
        with db.engine().connect() as c:
            c.execute(text("SELECT 1"))
        services["PostgreSQL"] = "available"
    except Exception:  # noqa: BLE001 - health reports any service failure as unavailable
        services["PostgreSQL"] = "unavailable"
    for country in ["AT", "CZ"]:
        try:
            publication.sparql(country, "ASK {}", timeout=2)
            services["Fuseki " + country] = "available"
        except Exception:  # noqa: BLE001 - health reports any service failure as unavailable
            services["Fuseki " + country] = "unavailable"
    return {
        "services": services,
        "complete": all(v == "available" for v in services.values()),
        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
    }


@app.get("/api/v1/codex")
def codex_health():
    state = account_state()
    return {"state": state["state"], "auth_type": state.get("auth_type"), "error": state.get("error")}


@app.get("/api/v1/snapshot")
def snapshot_api():
    snapshot = publication.current()
    return {
        "projection_id": snapshot["id"] if snapshot else None,
        "freshness": snapshot["freshness"] if snapshot else "unavailable",
        "release_id": snapshot["release_id"] if snapshot else None,
        "case_count": len(snapshot["cases"]) if snapshot else 0,
    }


@app.post("/api/v1/sources")
def ingest_api(envelope: sources.SourceEnvelope):
    return sources.ingest(envelope)


@app.post("/api/v1/sources/{aggregate_id}/correct")
async def correct_api(request: Request, aggregate_id: str):
    return sources.correct(aggregate_id, await request.json())


@app.post("/actions/correct")
async def correct_form(request: Request):
    form = await request.form()
    patch = json.loads(str(form["patch"]))
    sources.correct(str(form["aggregate_id"]), patch)
    publication.enqueue()
    return redirect("/status")


@app.post("/actions/replay")
def replay(request: Request):
    publication.enqueue()
    return redirect("/status")


@app.post("/actions/role")
async def role(request: Request):
    form = await request.form()
    selected = str(form["role"])
    if selected not in {"handler", "steward", "architect"}:
        raise ValueError("Unknown simulated role")
    response = redirect("/cases")
    response.set_cookie("isw_role", selected, samesite="strict", httponly=True)
    return response


@app.post("/actions/review/{case_id}")
async def review(request: Request, case_id: str):
    form = await request.form()
    governance.review(case_id, str(form["action"]), str(form["rationale"]), str(form["projection_id"]))
    return redirect("/cases/" + case_id)


@app.post("/actions/proposal")
async def proposal(request: Request):
    form = await request.form()
    governance.propose(
        str(form["country"]),
        str(form["title"]),
        str(form["target"]),
        str(form["rationale"]),
        str(form.get("case_id") or "") or None,
    )
    return redirect("/terminology#proposals")


@app.post("/actions/proposal/{proposal_id}")
async def decide(request: Request, proposal_id: str):
    form = await request.form()
    governance.decide_proposal(proposal_id, str(form["decision"]), str(form["rationale"]))
    return redirect("/terminology#proposals")


@app.post("/actions/releases/build")
def build_candidate():
    publication.enqueue("candidate", "2.0.0")
    return redirect("/status")


@app.post("/actions/releases/approve")
async def approve_candidate(request: Request):
    form = await request.form()
    governance.approve_release("2.0.0", str(form["rationale"]))
    return redirect("/releases")


@app.post("/actions/releases/activate")
def activate_candidate():
    governance.activate("2.0.0")
    return redirect("/releases")


@app.post("/actions/releases/rollback")
async def rollback(request: Request):
    form = await request.form()
    governance.rollback(str(form["projection_id"]), str(form["rationale"]))
    return redirect("/releases")


@app.post("/actions/jobs/{job_id}/retry")
def retry(job_id: str):
    publication.retry(job_id)
    return redirect("/status")


@app.post("/actions/runs")
async def start_run(request: Request):
    form = await request.form()
    rid = agents.create_run(
        str(form.get("case_id") or "") or None,
        str(form.get("role") or "claim"),
        str(form.get("projection_id") or "") or None,
    )
    return redirect("/runs/" + rid)


@app.post("/actions/runs/{run_id}/cancel")
def cancel_run(run_id: str):
    agents.cancel(run_id)
    return redirect("/runs/" + run_id)


@app.get("/api/v1/runs/{run_id}")
def run_api(run_id: str):
    with db.engine().connect() as c:
        run = db.one(c, select(db.runs).where(db.runs.c.id == run_id))
    if not run:
        raise ValueError("Unknown run")
    return {
        key: serializable(run[key])
        for key in ["id", "state", "case_id", "projection_id", "result", "error", "tool_count"]
    }


@app.get("/api/v1/runs/{run_id}/events")
async def run_events(request: Request, run_id: str):
    async def stream():
        last = int(request.headers.get("last-event-id", "0"))
        while not await request.is_disconnected():
            with db.engine().connect() as c:
                rows = db.many(
                    c,
                    select(db.run_events)
                    .where(db.run_events.c.run_id == run_id, db.run_events.c.id > last)
                    .order_by(db.run_events.c.id),
                )
                run = db.one(c, select(db.runs.c.state).where(db.runs.c.id == run_id))
            for row in rows:
                last = row["id"]
                yield f"id: {last}\nevent: progress\ndata: {json.dumps({'kind': row['kind'], 'payload': row['payload']})}\n\n"
            if not run or run["state"] not in {"queued", "running"}:
                break
            yield ": keepalive\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.post("/internal/agent/{tool}")
async def internal_tool(request: Request, tool: str):
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer "):
        raise PermissionError("Run token required")
    args = await request.json()
    if not isinstance(args, dict):
        raise ValueError("Tool arguments must be an object")  # noqa: TRY004 - public input maps to HTTP 400
    return await asyncio.to_thread(agents.scoped_tool, header[7:], tool, args)
