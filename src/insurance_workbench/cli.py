"""Thin, explicit command line for reproducible local operations."""

import argparse
import asyncio
import json
import subprocess
import time
import webbrowser

from .config import ROOT, settings


def main():
    parser = argparse.ArgumentParser(prog="isw")
    parser.add_argument(
        "command",
        choices=[
            "init",
            "assets",
            "seed",
            "publish",
            "worker",
            "agent-runner",
            "serve",
            "signin",
            "account",
            "backup",
            "restore",
            "storage",
            "wait-ready",
            "evaluate",
            "semantic-check",
        ],
    )
    parser.add_argument("--path")
    args = parser.parse_args()
    from . import agents, operations, publication, sources

    result = None
    if args.command == "init":
        subprocess.run(
            [str(ROOT / ".venv/Scripts/python.exe"), "-m", "alembic", "upgrade", "head"], cwd=ROOT, check=True
        )
        from . import db

        db.configure_roles()
        publication.initialize()
        result = "Schema, database roles and baseline initialized"
    elif args.command == "assets":
        operations.fetch_assets()
        result = "Pinned model loaded offline successfully"
    elif args.command == "seed":
        result = sources.seed()
        publication.enqueue()
    elif args.command == "publish":
        result = publication.enqueue()
    elif args.command == "worker":
        publication.worker()
    elif args.command == "agent-runner":
        asyncio.run(agents.runner())
    elif args.command == "serve":
        import uvicorn

        uvicorn.run(
            "insurance_workbench.web:app", host="127.0.0.1", port=settings().web_port, log_level="warning"
        )
    elif args.command == "signin":
        from openai_codex import Codex

        from .codex_gateway import config

        with Codex(config()) as codex:
            handle = codex.login_chatgpt()
            webbrowser.open(handle.auth_url)
            print("Complete ChatGPT sign-in in the opened browser. API keys are not accepted.", flush=True)
            response = handle.wait()
            if not response.success:
                raise RuntimeError(response.error or "Sign-in did not complete")
            result = "ChatGPT sign-in completed"
    elif args.command == "account":
        from .codex_gateway import account_state

        state = account_state()
        result = {key: value for key, value in state.items() if key != "limits"}
    elif args.command == "backup":
        result = operations.backup()
    elif args.command == "restore":
        if not args.path:
            parser.error("restore requires --path")
        result = operations.restore(args.path)
    elif args.command == "storage":
        result = operations.storage()
    elif args.command == "wait-ready":
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            snapshot = publication.current()
            if snapshot and snapshot["freshness"] == "current":
                result = {"projection_id": snapshot["id"], "state": "current"}
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("No current snapshot before the deadline; inspect publication jobs")
    elif args.command == "evaluate":
        from .evaluation import evaluate

        result = evaluate()
    elif args.command == "semantic-check":
        from .verification import semantic_check

        result = semantic_check()
    if result is not None:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
