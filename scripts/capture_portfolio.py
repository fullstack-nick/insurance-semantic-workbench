"""Capture genuine application states, without browser chrome or account details."""

from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
out = ROOT / "docs/screenshots"
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 1050}, device_scale_factor=1)
    for name, route in [
        ("case-review", "/cases/CLM-AT-001"),
        ("terminology", "/terminology?q=water"),
        (
            "retrieval-comparison",
            "/compare?case_id=CLM-AT-002&question=Which+policy+terms+and+pipe+clause+apply%3F",
        ),
        ("release-impact", "/releases"),
    ]:
        page.goto("http://127.0.0.1:8000" + route, wait_until="load", timeout=90000)
        page.screenshot(path=str(out / (name + ".png")))
    browser.close()
print("Captured four real application screenshots in docs/screenshots")
