"""The suite refuses the interactive namespace and uses actual local services."""

import json
import re
import time

import httpx
import pytest
from sqlalchemy import select

from insurance_workbench import db, publication
from insurance_workbench.config import settings


def pytest_addoption(parser):
    parser.addoption("--live-codex", action="store_true", help="Explicitly use the signed-in Codex allowance")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--live-codex"):
        for item in items:
            if "live_codex" in item.keywords:
                item.add_marker(pytest.mark.skip(reason="Inference is opt-in: --live-codex"))


@pytest.fixture(scope="session", autouse=True)
def isolated_namespace():
    assert settings().namespace == "isw-e2e", "E2E requires the isw-e2e namespace; use Verify-Lab.ps1"
    assert settings().db_port == 54321 and settings().web_port == 8001


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "viewport": {"width": 1440, "height": 1000}}


@pytest.fixture
def api():
    with httpx.Client(base_url="http://127.0.0.1:8001", timeout=30) as client:
        response = client.get("/cases")
        response.raise_for_status()
        token = re.search(r'name="csrf-token" content="([^"]+)"', response.text).group(1)
        client.headers["x-csrf-token"] = token
        yield client


@pytest.fixture(scope="session")
def base_url():
    return "http://127.0.0.1:8001"


def poll(fn, timeout=150):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = fn()
        if value:
            return value
        time.sleep(0.3)
    with db.engine().connect() as c:
        jobs = db.many(c, select(db.jobs).order_by(db.jobs.c.created_at.desc()).limit(3))
    raise AssertionError("Timed out waiting for observable state: " + json.dumps(jobs, default=str))


def current_after(previous):
    def ready():
        snapshot = publication.current()
        return (
            snapshot
            if snapshot and snapshot["id"] != previous and snapshot["freshness"] == "current"
            else None
        )

    return poll(ready)
