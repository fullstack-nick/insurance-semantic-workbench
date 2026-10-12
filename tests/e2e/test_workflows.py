"""Ten complete browser/source/service workflows; no mocks and no unit tests."""

import copy
import subprocess

from conftest import current_after, poll
from playwright.sync_api import expect
from sqlalchemy import func, select, text

from insurance_workbench import db, operations, publication, retrieval
from insurance_workbench.config import ROOT


def test_e01_valid_ingestion_and_source_provenance(page, base_url):
    page.goto(base_url + "/cases/CLM-AT-001")
    expect(page.get_by_role("heading", name="Water damage in the kitchen")).to_be_visible()
    expect(page.locator(".timeline")).to_contain_text("POL-AT-001-v1")
    expect(page.locator(".timeline")).to_contain_text("Purchased · pipe")
    card = page.locator(".evidence-card").filter(has=page.locator(".eyebrow", has_text="clause pipe"))
    expect(card).to_contain_text("120 EUR")
    card.get_by_role("link", name="Inspect source").click()
    expect(page.locator("mark")).to_contain_text("120 EUR")
    expect(page.get_by_role("heading", name="Provenance trail")).to_be_visible()
    expect(page.locator(".source-meta")).to_contain_text("document-span")
    with db.engine("reader").connect() as c:
        assert c.execute(select(func.count()).select_from(db.policies)).scalar() == 100
        assert c.execute(select(func.count()).select_from(db.claims)).scalar() == 50
        assert c.execute(select(func.count()).select_from(db.documents)).scalar() == 32


def test_e02_quarantine_correct_and_republish(page, base_url, api):
    before = publication.current()
    old = before["cases"]["CLM-AT-010"]["claim_source"]
    page.goto(base_url + "/cases/CLM-AT-010")
    expect(page.locator(".page-heading .badge")).to_have_text("quarantined")
    page.goto(base_url + "/validation")
    page.get_by_label("Aggregate ID").fill("CLM-AT-010")
    page.get_by_label("Changed fields as JSON").fill('{"currency":"EUR"}')
    page.get_by_role("button", name="Save a new source version").click()
    snapshot = current_after(before["id"])
    assert snapshot["cases"]["CLM-AT-010"]["status"] == "sufficient"
    page.goto(base_url + "/sources/" + old)
    page.get_by_text("Exact immutable JSON / SQL snapshot").click()
    expect(page.locator(".code-block")).to_contain_text('"currency": "BAD"')
    expect(page.locator(".page-heading")).to_contain_text("Older source version")
    # Malformed decimal input must become a visible quarantine, never a crashed publication.
    assert api.post("/api/v1/sources/CLM-AT-010/correct", json={"amount": "not-a-number"}).status_code == 200
    invalid = current_after(snapshot["id"])
    assert invalid["cases"]["CLM-AT-010"]["quarantined"]
    page.goto(base_url + "/cases/CLM-AT-010")
    expect(page.locator(".page-heading .badge")).to_have_text("quarantined")
    assert api.post("/api/v1/sources/CLM-AT-010/correct", json={"amount": "1840.00"}).status_code == 200
    repaired = current_after(invalid["id"])
    assert repaired["cases"]["CLM-AT-010"]["status"] == "sufficient"


def test_e03_mapping_approval_requires_case_evidence(page, base_url):
    page.goto(base_url + "/terminology")
    expect(page.locator(".notice")).to_contain_text("cannot establish pipe leakage")
    form = page.locator('form[action="/actions/proposal"]')
    form.get_by_label("Title", exact=True).fill("Unsupported narrow-cause proposal")
    form.get_by_label("Target meaning").select_option("pipe-leakage")
    form.get_by_label("Case ID", exact=False).fill("CLM-AT-004")
    form.get_by_label("Meaning, supporting evidence", exact=False).fill(
        "Demonstration: the broad source code alone is insufficient."
    )
    form.get_by_role("button", name="Submit proposal").click()
    article = page.locator(".proposal").filter(has_text="Unsupported narrow-cause proposal")
    article.get_by_label("Review rationale").fill("Attempting unsupported narrowing must fail.")
    article.get_by_role("button", name="Approve", exact=True).click()
    expect(page.locator(".subtitle")).to_contain_text("do not unambiguously support")
    page.goto(base_url + "/terminology")
    for title, button in [
        ("Reuse shared water-damage meaning", "Approve"),
        ("CZ mitigation assessment", "Approve"),
        ("Globalize the CZ document checklist", "Reject"),
    ]:
        article = page.locator(".proposal").filter(has=page.get_by_role("heading", name=title, exact=True))
        article.get_by_label("Review rationale").fill(
            "Demonstration steward decision: preserve shared meaning and the justified country scope."
        )
        article.get_by_role("button", name=button, exact=True).click()
    page.goto(base_url + "/cases/CLM-AT-004")
    expect(page.locator(".facts")).to_contain_text("water damage")


def test_e04_country_scope_independent_of_language(page, base_url):
    page.goto(base_url + "/cases/CLM-CZ-002")
    expect(page.locator(".page-heading")).to_contain_text("CZ OPERATING PROFILE")
    expect(page.locator(".evidence-list")).to_contain_text("DE · clause")
    for mode in retrieval.MODES:
        bundle = retrieval.retrieve("CLM-CZ-002", "Which pipe clause and operating profile apply?", mode)
        assert bundle["evidence"]
        assert all(e["country_scope"] == "CZ" and e["case_scope"] == "CLM-CZ-002" for e in bundle["evidence"])
        assert all("AT" not in e["source_id"] for e in bundle["evidence"])
    page.goto(base_url + "/cases/CLM-CZ-006")
    expect(page.locator(".attention")).to_contain_text("mitigation assessment")


def test_e05_historical_boundary_and_overlap(page, base_url):
    page.goto(base_url + "/cases/CLM-AT-008")
    expect(page.locator(".timeline")).to_contain_text("POL-AT-008-v2")
    page.goto(base_url + "/cases/CLM-AT-009")
    expect(page.get_by_text("No unambiguous applicable version.", exact=False)).to_be_visible()
    expect(page.locator(".attention")).to_contain_text("overlapping periods")
    bundle = retrieval.retrieve("CLM-AT-009", "Which policy version applies?", "hybrid")
    assert not any(e["kind"] == "clause" for e in bundle["evidence"])


def test_e06_duplicate_event_and_replay_converge(page, base_url, api):
    before = publication.current()
    claim = before["cases"]["CLM-AT-002"]["claim"]
    response = api.post(
        "/api/v1/sources",
        json={
            "aggregate_id": claim["id"],
            "kind": "claim",
            "version": 1,
            "country": "AT",
            "payload": claim,
            "event_id": "seed-CLM-AT-002",
        },
    )
    assert response.status_code == 200 and response.json()["state"] == "duplicate"
    altered = {**claim, "amount": "999.00"}
    response = api.post(
        "/api/v1/sources",
        json={
            "aggregate_id": claim["id"],
            "kind": "claim",
            "version": 1,
            "country": "AT",
            "payload": altered,
            "event_id": "seed-CLM-AT-002",
        },
    )
    assert response.status_code == 400
    publication.enqueue()
    after = current_after(before["id"])
    assert after["watermark"] == before["watermark"]
    assert after["manifest"]["evidence_count"] == before["manifest"]["evidence_count"]
    with db.engine("reader").connect() as c:
        assert (
            c.execute(
                select(func.count())
                .select_from(db.receipts)
                .where(db.receipts.c.event_id == "seed-CLM-AT-002")
            ).scalar()
            == 1
        )
    page.goto(base_url + "/cases/CLM-AT-002")
    expect(page.locator(".freshness")).to_have_text("current")
    original_source = after["cases"]["CLM-AT-030"]["claim_source"]
    response = api.post(
        "/api/v1/sources",
        json={
            "aggregate_id": "CLM-AT-030",
            "kind": "claim",
            "version": 2,
            "country": "AT",
            "payload": {"id": "CLM-AT-030", "country": "AT"},
            "event_id": "e06-tombstone",
            "tombstone": True,
        },
    )
    assert response.status_code == 200
    deleted = current_after(after["id"])
    assert "CLM-AT-030" not in deleted["cases"]
    page.goto(base_url + "/cases?q=CLM-AT-030")
    expect(page.locator(".empty")).to_contain_text("No claims match")
    page.goto(base_url + "/sources/" + original_source)
    expect(page.locator(".page-heading")).to_contain_text("Older source version")


def test_e07_out_of_order_and_interrupted_publication(page, base_url, api):
    before = publication.current()
    claim = before["cases"]["CLM-AT-018"]["claim"]
    with db.engine("worker").connect() as lock:
        lock.execute(text("SELECT pg_advisory_lock(:key)"), {"key": publication.LOCK})
        lock.commit()
        try:
            for version, amount in [(3, "2300.00"), (2, "1900.00")]:
                response = api.post(
                    "/api/v1/sources",
                    json={
                        "aggregate_id": claim["id"],
                        "kind": "claim",
                        "version": version,
                        "country": "AT",
                        "payload": {**claim, "amount": amount},
                        "event_id": f"e07-version-{version}",
                    },
                )
                assert response.status_code == 200
                if version == 2:
                    assert response.json()["state"] == "superseded"
            job_id = publication.enqueue(fail_after="AT")
        finally:
            lock.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": publication.LOCK})
            lock.commit()

    def failed():
        with db.engine("reader").connect() as c:
            row = db.one(c, select(db.jobs).where(db.jobs.c.id == job_id))
        return row if row["state"] == "failed" else None

    job = poll(failed)
    assert "Deliberate publication interruption" in job["error"]
    assert publication.current()["id"] == before["id"]
    page.goto(base_url + "/cases/CLM-AT-018")
    expect(page.locator(".freshness")).to_have_text("stale")
    expect(page.locator(".facts")).to_contain_text("1840.00")
    page.goto(base_url + "/status")
    row = page.locator("tr").filter(has_text=job_id)
    row.get_by_role("button", name="Retry job").click()
    after = current_after(before["id"])
    assert after["cases"][claim["id"]]["claim"]["amount"] == "2300.00"
    assert after["id"] == job["payload"]["projection_id"]
    page.goto(base_url + "/cases/CLM-AT-018")
    expect(page.locator(".facts")).to_contain_text("2300.00")


def test_e08_document_replacement_preserves_saved_evidence(page, base_url, api):
    before = publication.current()
    cid = "CLM-AT-020"
    case = before["cases"][cid]
    bundle = retrieval.retrieve(cid, "Which deductible applies?", "hybrid")
    old = next(e for e in bundle["evidence"] if e["group_id"].endswith("/clause-pipe"))
    with db.engine("reader").connect() as c:
        document = db.one(c, select(db.documents).where(db.documents.c.id == old["source_id"]))["payload"]
    newdoc = copy.deepcopy(document)
    newdoc.update(id="DOC-AT-02-v3", version=3, valid_from="2025-07-01", valid_to=None)
    newdoc["text"] = newdoc["text"].replace("180 EUR", "190 EUR")
    policy = copy.deepcopy(case["policy"])
    policy["versions"][-1]["valid_to"] = "2025-07-01"
    policy["versions"].append(
        {
            **policy["versions"][-1],
            "id": "POL-AT-020-v3",
            "valid_from": "2025-07-01",
            "valid_to": None,
            "document_id": newdoc["id"],
        }
    )
    with db.engine("worker").connect() as lock:
        lock.execute(text("SELECT pg_advisory_lock(:key)"), {"key": publication.LOCK})
        lock.commit()
        try:
            assert (
                api.post(
                    "/api/v1/sources",
                    json={
                        "aggregate_id": newdoc["id"],
                        "kind": "document",
                        "version": 1,
                        "country": "AT",
                        "payload": newdoc,
                    },
                ).status_code
                == 200
            )
            assert (
                api.post(
                    "/api/v1/sources/POL-AT-020/correct", json={"versions": policy["versions"]}
                ).status_code
                == 200
            )
        finally:
            lock.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": publication.LOCK})
            lock.commit()
    after = current_after(before["id"])
    page.goto(base_url + "/cases/" + cid)
    expect(page.locator(".timeline")).to_contain_text("POL-AT-020-v3")
    expect(page.locator(".evidence-list")).to_contain_text("190 EUR")
    page.goto(base_url + "/sources/" + old["evidence_id"])
    expect(page.locator("mark")).to_contain_text("180 EUR")
    assert api.post("/api/v1/sources/CLM-AT-020/correct", json={"loss_date": "2025-06-30"}).status_code == 200
    current_after(after["id"])
    page.goto(base_url + "/cases/" + cid)
    expect(page.locator(".timeline")).to_contain_text("POL-AT-020-v2")
    expect(page.locator(".evidence-list")).to_contain_text("180 EUR")


def test_e09_release_rollback_and_restore_saved_review(page, base_url, api):
    baseline = publication.current()
    page.goto(base_url + "/cases/CLM-AT-002")
    page.get_by_label("Your rationale").fill("E2E saved human review: original policy and clause inspected.")
    page.get_by_role("button", name="Record human decision").click()
    page.goto(base_url + "/releases")
    page.get_by_role("button", name="Build candidate").click()

    def candidate():
        with db.engine("reader").connect() as c:
            r = db.one(c, select(db.releases).where(db.releases.c.id == "2.0.0"))
        return r if r["state"] == "reviewable" else None

    release = poll(candidate)
    assert publication.current()["id"] == baseline["id"]
    bypass = api.post(
        "/actions/releases/rollback",
        data={
            "csrf": api.headers["x-csrf-token"],
            "projection_id": release["candidate_id"],
            "rationale": "Attempting to bypass candidate approval",
        },
    )
    assert bypass.status_code == 400 and "previously active" in bypass.text
    page.goto(base_url + "/releases")
    expect(page.get_by_role("heading", name="Record-level impact")).to_be_visible()
    page.get_by_label("Approval rationale").fill(
        "E2E architect review: supported causes narrow; unresolved legacy cases remain broad."
    )
    page.get_by_role("button", name="Approve candidate").click()
    page.get_by_role("button", name="Activate 2.0.0").click()
    activated = publication.current()
    assert activated["id"] == release["candidate_id"]
    assert activated["cases"]["CLM-AT-002"]["classification"] == "pipe-leakage"
    assert activated["cases"]["CLM-AT-004"]["status"] == "incomplete"
    page.get_by_label("Complete projection").select_option(baseline["id"])
    page.get_by_label("Rollback rationale").fill("E2E rollback preserves source and human review history.")
    page.get_by_role("button", name="Restore this snapshot").click()
    assert publication.current()["id"] == baseline["id"]
    with db.engine("reader").connect() as c:
        states = {r["id"]: r["state"] for r in db.many(c, select(db.releases))}
    assert states["1.0.0"] == "active" and states["2.0.0"] == "superseded"
    backup = operations.backup()
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts/Restore-Lab.ps1"),
            "-Namespace",
            "isw-e2e-restore",
            "-BackupPath",
            backup,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    # Windows background descendants can inherit capture-pipe handles. A file keeps
    # script completion independent of the lifetime of the services it starts.
    with (ROOT / "output/playwright/restore-start.log").open("w") as log:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ROOT / "scripts/Start-Lab.ps1"),
                "-Namespace",
                "isw-e2e-restore",
            ],
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=240,
        )
    assert result.returncode == 0
    page.goto("http://127.0.0.1:8003/cases/CLM-AT-002")
    expect(page.locator(".history-entry").filter(has_text="E2E saved human review").first).to_be_visible()
    expect(page.locator(".freshness")).to_have_text("current")
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts/Stop-Lab.ps1"),
            "-Namespace",
            "isw-e2e-restore",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_e10_country_outage_is_explicit_and_recovers(page, base_url):
    page.goto(base_url + "/federation")
    expect(page.locator(".page-heading .badge")).to_have_text("complete")
    operations.compose("stop", "fuseki-cz", capture_output=True)
    try:
        page.goto(base_url + "/federation")
        expect(page.locator(".page-heading .badge")).to_have_text("unavailable")
        page.get_by_role("link", name="Labeled partial results").click()
        expect(page.locator(".page-heading .badge")).to_have_text("partial")
        expect(page.locator(".service").filter(has_text="CZ endpoint")).to_contain_text("unavailable")
    finally:
        operations.compose("up", "-d", "--wait", "fuseki-cz", capture_output=True)
    page.goto(base_url + "/federation")
    expect(page.locator(".page-heading .badge")).to_have_text("complete")
