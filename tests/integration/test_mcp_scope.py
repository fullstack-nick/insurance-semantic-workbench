"""One necessary live boundary check: a browser cannot issue adversarial STDIO MCP messages."""

import asyncio
import json
import sys
from datetime import timedelta

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from sqlalchemy import insert, select, update

from insurance_workbench import agents, db, publication
from insurance_workbench.codex_gateway import CLAIM_TOOLS
from insurance_workbench.config import ROOT, settings
from insurance_workbench.util import digest, new_id


def test_real_mcp_rejects_scope_escape_and_revoked_token():
    assert settings().namespace == "isw-e2e", "The probe requires the isolated test namespace"
    snapshot = publication.current()
    run_id = new_id("scope-probe")
    token = agents.token_for(run_id)
    with db.engine().begin() as c:
        assert not db.one(c, select(db.runs).where(db.runs.c.state.in_(["queued", "running"])))
        # This is an explicit protocol probe, not a generated model review.
        c.execute(
            insert(db.runs).values(
                id=run_id,
                case_id="CLM-AT-002",
                projection_id=snapshot["id"],
                role="claim",
                state="running",
                token_hash=digest(token),
                expires_at=db.now() + timedelta(minutes=3),
            )
        )
        other = db.one(
            c,
            select(db.evidence).where(
                db.evidence.c.projection_id == snapshot["id"], db.evidence.c.case_id == "CLM-CZ-002"
            ),
        )
    checks = []

    async def probe():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "insurance_workbench.mcp_server"],
            cwd=str(ROOT),
            env={
                "ISW_RUN_TOKEN": token,
                "ISW_AGENT_ROLE": "claim",
                "PYTHONIOENCODING": "utf-8",
                "ISW_AGENT_URL": "http://127.0.0.1:8001/internal/agent",
            },
        )
        with (ROOT / "output/playwright/mcp-probe.log").open("w", encoding="utf-8") as log:
            async with (
                stdio_client(params, errlog=log) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                inventory = await session.list_tools()
                assert {t.name for t in inventory.tools} == set(CLAIM_TOOLS)
                checks.append("exact six-tool MCP inventory")
                context = await session.call_tool("get_case_context")
                assert not context.is_error and "CLM-AT-002" in str(context.content)
                checks.append("valid bound case request succeeds")
                refused = await session.call_tool("get_source_excerpt", {"issued_evidence_id": other["id"]})
                assert refused.is_error
                checks.append("cross-country and unissued evidence rejected")
                refused = await session.call_tool("activate_release", {"release_id": "2.0.0"})
                assert refused.is_error
                checks.append("write tool absent and rejected")
                bundle = await session.call_tool(
                    "retrieve_evidence", {"question": "Which policy and clause apply?", "mode": "hybrid"}
                )
                assert not bundle.is_error
                with db.engine().connect() as c:
                    run = db.one(c, select(db.runs).where(db.runs.c.id == run_id))
                excerpt = await session.call_tool(
                    "get_source_excerpt", {"issued_evidence_id": run["issued_ids"][0]}
                )
                assert not excerpt.is_error
                checks.append("hybrid retrieval and issued evidence succeed through the actual protocol")
                with httpx.Client() as client:
                    response = client.post(
                        "http://127.0.0.1:8001/internal/agent/get_case_context",
                        headers={"Authorization": "Bearer " + token},
                        json={"case_id": "CLM-CZ-002"},
                    )
                assert response.status_code == 403
                checks.append("server rejects scope-changing parameters")
                agents.cancel(run_id)
                refused = await session.call_tool("get_case_context")
                assert refused.is_error
                checks.append("cancelled token is immediately revoked")

    try:
        asyncio.run(probe())
    finally:
        with db.engine().begin() as c:
            c.execute(
                update(db.runs)
                .where(db.runs.c.id == run_id)
                .values(
                    state="cancelled",
                    expires_at=db.now(),
                    finished_at=db.now(),
                    error="Intentional live MCP protocol probe; no model request",
                )
            )
    report = {
        "recorded_at": str(db.now()),
        "namespace": "isw-e2e",
        "model_requests": 0,
        "checks_passed": checks,
        "reason": "Scope attacks must exercise actual MCP serialization and the authenticated HTTP boundary; UI paths cannot express them.",
    }
    (ROOT / "docs/verification/mcp-scope.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
