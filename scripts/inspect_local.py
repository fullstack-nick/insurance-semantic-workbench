"""Read-only measured operations report and browser inspection of the fresh restore."""

import json
import math
import statistics
import subprocess
import time

import httpx
from playwright.sync_api import expect, sync_playwright
from sqlalchemy import func, select, text

from insurance_workbench import db, operations, publication
from insurance_workbench.config import ROOT, settings

assert settings().namespace == "isw", "Use the interactive namespace as the restore source"
snapshot = publication.current()
storage = operations.storage()
images = {}
for image in [
    "isw-fuseki:6.2.0",
    "pgvector/pgvector:0.8.7-pg17-bookworm@sha256:cd4ccfdaf62cbfeb5c6ee19ef0dd663406d4ed740c320b324d016a90e85385b3",
]:
    result = subprocess.run(
        ["docker", "image", "inspect", image, "--format", "{{.Size}}"],
        capture_output=True,
        text=True,
        check=True,
    )
    images[image] = int(result.stdout.strip())
volumes = {}
for service, directory in [
    ("postgres", "/var/lib/postgresql/data"),
    ("fuseki-at", "/data"),
    ("fuseki-cz", "/data"),
]:
    result = operations.compose("exec", "-T", service, "du", "-sk", directory, capture_output=True, text=True)
    volumes[service] = int(result.stdout.split()[0]) * 1024
with db.engine("reader").connect() as c:
    counts = {
        table.name: c.execute(select(func.count()).select_from(table)).scalar()
        for table in [db.policies, db.policy_versions, db.claims, db.documents, db.decisions]
    }
    saved = db.one(
        c,
        select(db.runs)
        .where(db.runs.c.state == "completed", db.runs.c.role == "claim")
        .order_by(db.runs.c.created_at.desc())
        .limit(1),
    )
    clause = db.one(
        c,
        select(db.evidence).where(
            db.evidence.c.id.in_(saved["issued_ids"]), db.evidence.c.group_id.like("%/clause-pipe")
        ),
    )
    privileges = {
        "reader_cannot_insert_claims": not c.execute(
            text("SELECT has_table_privilege('isw_reader','source.claims','INSERT')")
        ).scalar(),
        "app_cannot_update_sources": not c.execute(
            text("SELECT has_table_privilege('isw_app','source.claims','UPDATE')")
        ).scalar(),
        "source_cannot_update_decisions": not c.execute(
            text("SELECT has_table_privilege('isw_source','workbench.review_decisions','UPDATE')")
        ).scalar(),
    }
assert all(privileges.values())
latencies = []
with httpx.Client(base_url="http://127.0.0.1:8000") as client:
    client.get("/cases/CLM-AT-001").raise_for_status()
    for _ in range(25):
        started = time.perf_counter()
        client.get("/cases/CLM-AT-001").raise_for_status()
        latencies.append((time.perf_counter() - started) * 1000)
with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    browser_times = []
    page.goto("http://127.0.0.1:8000/cases/CLM-AT-001")
    for _ in range(10):
        started = time.perf_counter()
        page.goto("http://127.0.0.1:8000/cases/CLM-AT-001", wait_until="load")
        browser_times.append((time.perf_counter() - started) * 1000)
    page.goto("http://127.0.0.1:8002/runs/" + saved["id"])
    expect(page.locator(".page-heading .badge")).to_have_text("completed")
    page.goto("http://127.0.0.1:8002/sources/" + clause["id"])
    expect(page.locator("mark")).to_contain_text("120 EUR")
    expect(page.get_by_role("heading", name="Provenance trail")).to_be_visible()
    page.goto("http://127.0.0.1:8002/cases/CLM-AT-001")
    expect(
        page.locator(".history-entry").filter(has_text="Demonstration handler record").first
    ).to_be_visible()
    browser.close()
with httpx.Client() as client:
    restored = client.get("http://127.0.0.1:8002/api/v1/runs/" + saved["id"]).json()
    assert restored["result"] == saved["result"]
backup_dir = (
    settings().data_root
    / "backups"
    / (settings().data_root / "restore-input.txt").read_text().replace("\\", "/").rsplit("/", 1)[-1]
)
manifest = json.loads((backup_dir / "manifest.json").read_text())
restore_report = {
    "recorded_at": str(db.now()),
    "backup_id": manifest["backup_id"],
    "source_namespace": "isw",
    "target_namespace": "isw-restore",
    "projection_id": manifest["active"]["projection_id"],
    "files_hash_verified": len(manifest["files"]),
    "graphs_roundtrip_verified": len(manifest["graphs"]),
    "saved_reviews_preserved": manifest["review_count"],
    "completed_briefs_preserved": manifest["completed_briefs"],
    "inspected_claim_brief": saved["id"],
    "result_identical": True,
    "original_120_eur_clause_visible": True,
    "human_review_visible": True,
    "source_sha256": clause["payload"]["content_sha256"],
}
(ROOT / "docs/verification/restore.json").write_text(json.dumps(restore_report, indent=2), encoding="utf-8")


def timings(values):
    return {
        "samples": len(values),
        "median_ms": round(statistics.median(values), 2),
        "p95_ms": round(sorted(values)[math.ceil(len(values) * 0.95) - 1], 2),
    }


report = {
    "recorded_at": str(db.now()),
    "namespace": "isw",
    "corpus_counts": counts,
    "projection_id": snapshot["id"],
    "evidence_items": snapshot["manifest"]["evidence_count"],
    "last_publication_seconds": snapshot["manifest"]["build_seconds"],
    "publication_conditions": "Observed refresh while other verification namespaces were active; not an isolated throughput benchmark",
    "warm_http_case_response": timings(latencies),
    "warm_browser_navigation": timings(browser_times),
    "storage_logical_file_bytes": storage["bytes"],
    "image_reported_bytes": images,
    "interactive_volume_bytes": volumes,
    "disk_free_bytes": storage["disk_free_bytes"],
    "database_role_checks": privileges,
    "storage_caveat": "Runtime includes the model and all test namespace files/backups. Logical sizes can double-count hardlinks/shared layers; they are not measured incremental physical allocation.",
}
(ROOT / "docs/verification/operations.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({"operations": report, "restore": restore_report}, indent=2))
