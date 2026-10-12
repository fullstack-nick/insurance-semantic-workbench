"""Project-scoped backup, restore, asset setup and storage inventory."""

import json
import shutil
import subprocess
from pathlib import Path

from sqlalchemy import delete, insert, select, text
from sqlalchemy.dialects.postgresql import insert as upsert

from . import db, publication
from .config import ROOT, settings
from .util import digest, new_id


def compose(*args, **kwargs):
    return subprocess.run(
        ["docker", "compose", "-p", settings().namespace, *args], cwd=ROOT, check=True, **kwargs
    )


def fetch_assets():
    from huggingface_hub import snapshot_download

    from .embedding import MANIFEST

    snapshot_download(
        MANIFEST["model"],
        revision=MANIFEST["revision"],
        local_dir=settings().model_dir,
        allow_patterns=["*.json", "*.safetensors", "sentencepiece.bpe.model", "1_Pooling/*"],
        ignore_patterns=["onnx/*", "openvino/*"],
    )
    from .embedding import encode

    encode(["English evidence", "Deutsche Nachweise", "České podklady"], query=True)


def backup():
    s = settings()
    backup_id = new_id("backup")
    directory = s.data_root / "backups" / backup_id
    directory.mkdir(parents=True, exist_ok=False)
    with db.engine().begin() as c:
        if db.one(c, select(db.runs).where(db.runs.c.state.in_(["queued", "running"]))):
            raise ValueError("Finish or cancel the active assistant run before backup")
        c.execute(insert(db.state).values(id="maintenance", payload={"reason": "backup", "id": backup_id}))
    with db.engine().connect() as lock:
        lock.execute(text("SELECT pg_advisory_lock(:key)"), {"key": publication.LOCK})
        lock.commit()
        lock.execute(text("SELECT pg_advisory_lock(:key)"), {"key": db.MAINTENANCE_LOCK})
        lock.commit()
        try:
            pointer = db.one(lock, select(db.active).where(db.active.c.id == 1))
            complete = db.many(
                lock, select(db.projections).where(db.projections.c.state.in_(["ready", "active"]))
            )
            runs = db.many(lock, select(db.runs).where(db.runs.c.state == "completed"))
            review_count = len(db.many(lock, select(db.decisions)))
            lock.commit()
            with (directory / "database.dump").open("wb") as stream:
                compose(
                    "exec", "-T", "postgres", "pg_dump", "-U", "isw", "-d", "workbench", "-Fc", stdout=stream
                )
            for name in ["sources", "graphs", "reports", "releases"]:
                if (s.data_root / name).exists():
                    shutil.copytree(s.data_root / name, directory / name)
            graphs = []
            for p in complete:
                for parts in p["manifest"]["graphs"].values():
                    graphs.extend(parts.values())
            for run in runs:
                if run["role"] != "claim":
                    continue
                uri = "https://example.org/isw/brief/" + run["id"]
                file = digest(uri)[:24] + ".nt"
                if (directory / "graphs" / file).exists():
                    snapshot = next((p for p in complete if p["id"] == run["projection_id"]), None)
                    if snapshot:
                        graphs.append(
                            {
                                "uri": uri,
                                "file": file,
                                "country": snapshot["cases"][run["case_id"]]["country"],
                            }
                        )
            manifest = {
                "schema_version": 1,
                "backup_id": backup_id,
                "source_namespace": s.namespace,
                "source_db_port": s.db_port,
                "active": pointer,
                "graphs": graphs,
                "review_count": review_count,
                "completed_briefs": len(runs),
                "created_at": str(db.now()),
                "files": {
                    str(path.relative_to(directory)).replace("\\", "/"): digest(path.read_bytes())
                    for path in directory.rglob("*")
                    if path.is_file()
                },
            }
            (directory / "manifest.json").write_text(
                json.dumps(manifest, indent=2, default=str), encoding="utf-8"
            )
        finally:
            lock.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": db.MAINTENANCE_LOCK})
            lock.commit()
            lock.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": publication.LOCK})
            lock.commit()
            with db.engine().begin() as c:
                c.execute(delete(db.state).where(db.state.c.id == "maintenance"))
    with db.engine().begin() as c:
        stmt = upsert(db.state).values(
            id="last-backup",
            payload={
                "backup_id": backup_id,
                "created_at": str(db.now()),
                "verified_files": len(manifest["files"]),
                "review_count": review_count,
            },
        )
        c.execute(
            stmt.on_conflict_do_update(
                index_elements=[db.state.c.id], set_={"payload": stmt.excluded.payload}
            )
        )
    return str(directory)


def restore(directory):
    from rdflib import Graph

    s = settings()
    directory = Path(directory).resolve()
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if (
        s.namespace not in {"isw-restore", "isw-e2e-restore"}
        or s.namespace == manifest["source_namespace"]
        or s.db_port == manifest["source_db_port"]
    ):
        raise ValueError("Restore is permitted only into a distinct fresh restore namespace and port")
    for name, checksum in manifest["files"].items():
        path = (directory / name).resolve()
        if not path.is_relative_to(directory) or digest(path.read_bytes()) != checksum:
            raise ValueError("Backup artifact path or checksum is invalid")
    with db.engine("migration").connect() as c:
        occupied = c.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema IN ('source','workbench')"
            )
        ).scalar()
        if occupied:
            raise ValueError("Restore target is not fresh; existing project tables will not be overwritten")
    with (directory / "database.dump").open("rb") as stream:
        compose(
            "exec",
            "-T",
            "postgres",
            "pg_restore",
            "-U",
            "isw",
            "--no-owner",
            "--no-acl",
            "--exit-on-error",
            "-d",
            "workbench",
            stdin=stream,
        )
    db.configure_roles()
    for name in ["sources", "graphs", "reports", "releases"]:
        if (directory / name).exists():
            shutil.copytree(directory / name, s.data_root / name, dirs_exist_ok=True)
    with db.engine().begin() as c:
        c.execute(delete(db.state).where(db.state.c.id == "maintenance"))
        # Restored tokens are intentionally unusable; authentication is never backed up.
        c.execute(db.runs.update().values(expires_at=db.now()))
    for artifact in manifest["graphs"]:
        graph = Graph().parse(s.data_root / "graphs" / artifact["file"], format="nt")
        publication.upload(artifact["country"], artifact["uri"], graph)
    snapshot = publication.current()
    if not snapshot or snapshot["id"] != manifest["active"]["projection_id"]:
        raise RuntimeError("Restored active snapshot differs from the backup")
    with db.engine().connect() as c:
        restored_reviews = len(db.many(c, select(db.decisions)))
        restored_briefs = len(db.many(c, select(db.runs).where(db.runs.c.state == "completed")))
    if restored_reviews != manifest["review_count"] or restored_briefs != manifest["completed_briefs"]:
        raise RuntimeError("Restored review/audit counts differ from the backup")
    return {
        "backup_id": manifest["backup_id"],
        "projection_id": snapshot["id"],
        "case_count": len(snapshot["cases"]),
        "restored_reviews": restored_reviews,
        "restored_briefs": restored_briefs,
        "graphs_verified": len(manifest["graphs"]),
        "files_verified": len(manifest["files"]),
    }


def storage():
    s = settings()

    def size(path):
        return sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) if path.exists() else 0

    paths = {"environment": ROOT / ".venv", "runtime": s.data_root, "model": s.model_dir}
    return {
        "namespace": s.namespace,
        "bytes": {name: size(path) for name, path in paths.items()},
        "paths": {name: str(path) for name, path in paths.items()},
        "disk_free_bytes": shutil.disk_usage(ROOT).free,
        "note": "Runtime includes model when using the default data root. Shared Docker VHDX size is not project usage.",
    }
