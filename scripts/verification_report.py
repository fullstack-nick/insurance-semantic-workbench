"""Publish compact measured outcomes, never raw traces or machine-specific log paths."""

import json
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
report = {"recorded_at": datetime.now(UTC).isoformat(), "suites": []}
for name in ["e2e", "startup", "mcp", "live"]:
    path = ROOT / f"output/playwright/{name}-results.xml"
    if not path.exists():
        continue
    xml = ET.parse(path).getroot()
    cases = list(xml.iter("testcase"))
    report["suites"].append(
        {
            "name": name,
            "suite_started_at": [suite.get("timestamp") for suite in xml.iter("testsuite")],
            "tests": len(cases),
            "failures": len(list(xml.iter("failure"))),
            "errors": len(list(xml.iter("error"))),
            "skipped": len(list(xml.iter("skipped"))),
            "duration_seconds": round(sum(float(c.get("time", 0)) for c in cases), 3),
            "checks": [
                {
                    "name": c.get("name"),
                    "seconds": float(c.get("time", 0)),
                    "passed": not any(c.find(tag) is not None for tag in ["failure", "error", "skipped"]),
                }
                for c in cases
            ],
        }
    )
target = ROOT / "docs/verification/workflows.json"
target.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
