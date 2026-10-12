"""Full-snapshot source API and transactional outbox. No inference at ingest time."""

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, insert, select, text
from sqlalchemy.dialects.postgresql import insert as upsert

from . import db
from .config import ROOT, settings
from .source_contracts import CONTRACTS
from .util import digest, json_text, new_id, parse_date


class SourceEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    aggregate_id: str = Field(pattern=r"^[A-Z][A-Za-z0-9-]{1,100}$")
    kind: str = Field(pattern=r"^(claim|policy|document)$")
    version: int = Field(ge=1)
    country: str = Field(pattern=r"^(AT|CZ)$")
    payload: dict
    event_id: str | None = None
    correlation_id: str | None = None
    tombstone: bool = False


def ingest(envelope: SourceEnvelope, connection=None):
    if connection is None:
        with db.engine("source").begin() as transaction:
            return ingest(envelope, transaction)
    if db.one(connection, select(db.state).where(db.state.c.id == "maintenance")):
        raise ValueError("Source writes are paused for backup or restore")
    if (
        envelope.payload.get("id") != envelope.aggregate_id
        or envelope.payload.get("country") != envelope.country
    ):
        raise ValueError("Envelope identity/country must match the original source")
    if not envelope.tombstone:
        CONTRACTS[envelope.kind].model_validate(envelope.payload)
    # A row lock alone cannot serialize two first versions when no head row exists.
    connection.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:id, 0))"), {"id": envelope.aggregate_id}
    )
    event_id = envelope.event_id or new_id("evt")
    checksum = digest(envelope.payload)
    existing = db.one(connection, select(db.outbox).where(db.outbox.c.event_id == event_id))
    if existing:
        saved = db.one(connection, select(db.snapshots).where(db.snapshots.c.id == existing["snapshot_id"]))
        if (saved["aggregate_id"], saved["version"], saved["sha256"], saved["kind"], saved["tombstone"]) != (
            envelope.aggregate_id,
            envelope.version,
            checksum,
            envelope.kind,
            envelope.tombstone,
        ):
            raise ValueError("An event ID cannot be reused with different source contents")
        return {"event_id": event_id, "state": "duplicate", "snapshot_id": existing["snapshot_id"]}
    snapshot_id = (
        f"src-{digest([envelope.aggregate_id, envelope.version, checksum, envelope.tombstone])[:24]}"
    )
    old = db.one(
        connection,
        select(db.snapshots).where(
            db.snapshots.c.aggregate_id == envelope.aggregate_id, db.snapshots.c.version == envelope.version
        ),
    )
    if old and (old["sha256"] != checksum or old["tombstone"] != envelope.tombstone):
        raise ValueError("An immutable source version already exists with different contents")
    if not old:
        connection.execute(
            insert(db.snapshots).values(
                id=snapshot_id,
                aggregate_id=envelope.aggregate_id,
                version=envelope.version,
                kind=envelope.kind,
                country=envelope.country,
                sha256=checksum,
                payload=envelope.payload,
                tombstone=envelope.tombstone,
            )
        )
        directory = settings().data_root / "sources"
        (directory / f"{snapshot_id}.json").write_text(json_text(envelope.payload), encoding="utf-8")
        if envelope.kind == "document" and "text" in envelope.payload:
            (directory / f"{snapshot_id}.txt").write_bytes(envelope.payload["text"].encode("utf-8"))
    head = db.one(
        connection, select(db.heads).where(db.heads.c.aggregate_id == envelope.aggregate_id).with_for_update()
    )
    newer = head is None or envelope.version > head["version"]
    if newer:
        statement = upsert(db.heads).values(
            aggregate_id=envelope.aggregate_id,
            snapshot_id=snapshot_id,
            version=envelope.version,
            kind=envelope.kind,
            country=envelope.country,
        )
        connection.execute(
            statement.on_conflict_do_update(
                index_elements=[db.heads.c.aggregate_id],
                set_={
                    key: getattr(statement.excluded, key)
                    for key in ["snapshot_id", "version", "kind", "country"]
                },
            )
        )
        _sync_operational(connection, envelope)
    connection.execute(
        insert(db.outbox).values(
            event_id=event_id,
            aggregate_id=envelope.aggregate_id,
            aggregate_version=envelope.version,
            snapshot_id=snapshot_id,
            country=envelope.country,
            event_type="tombstone" if envelope.tombstone else "snapshot",
            correlation_id=envelope.correlation_id or event_id,
            state="queued" if newer else "superseded",
        )
    )
    if not newer:
        connection.execute(insert(db.receipts).values(event_id=event_id, outcome="superseded"))
    return {"event_id": event_id, "state": "queued" if newer else "superseded", "snapshot_id": snapshot_id}


def _sync_operational(connection, envelope):
    p = envelope.payload
    target = {"claim": db.claims, "policy": db.policies, "document": db.documents}[envelope.kind]
    connection.execute(delete(target).where(target.c.id == p["id"]))
    if envelope.kind == "policy":
        connection.execute(delete(db.policy_versions).where(db.policy_versions.c.policy_id == p["id"]))
    if envelope.tombstone:
        return
    if envelope.kind == "claim":
        connection.execute(
            insert(target).values(
                id=p["id"],
                country=p["country"],
                policy_id=p["policy_id"],
                loss_date=parse_date(p.get("loss_date")),
                revision=envelope.version,
                payload=p,
            )
        )
    elif envelope.kind == "document":
        connection.execute(
            insert(target).values(
                id=p["id"],
                document_id=p["document_id"],
                country=p["country"],
                sha256=digest(p["text"].encode("utf-8")),
                payload=p,
            )
        )
    else:
        connection.execute(
            insert(target).values(id=p["id"], country=p["country"], product=p["product"], payload=p)
        )
        for version in p["versions"]:
            connection.execute(
                insert(db.policy_versions).values(
                    id=version["id"],
                    policy_id=p["id"],
                    valid_from=parse_date(version["valid_from"]),
                    valid_to=parse_date(version.get("valid_to")),
                    payload=version,
                )
            )


def seed():
    import json

    corpus = json.loads((ROOT / "fixtures/corpus.json").read_text(encoding="utf-8"))
    with db.engine("source").begin() as connection:
        for plural, kind in [("documents", "document"), ("policies", "policy"), ("claims", "claim")]:
            for payload in corpus[plural]:
                ingest(
                    SourceEnvelope(
                        aggregate_id=payload["id"],
                        kind=kind,
                        version=1,
                        country=payload["country"],
                        payload=payload,
                        event_id=f"seed-{payload['id']}",
                    ),
                    connection,
                )
    return {key: len(value) for key, value in corpus.items()}


def correct(aggregate_id, patch):
    with db.engine("source").begin() as connection:
        row = db.one(
            connection,
            select(db.snapshots)
            .join(db.heads, db.heads.c.snapshot_id == db.snapshots.c.id)
            .where(db.heads.c.aggregate_id == aggregate_id),
        )
        if row is None:
            raise ValueError("Unknown source")
        payload = {**row["payload"], **patch}
        return ingest(
            SourceEnvelope(
                aggregate_id=aggregate_id,
                kind=row["kind"],
                country=row["country"],
                version=row["version"] + 1,
                payload=payload,
            ),
            connection,
        )


def source_cut(connection):
    return {
        row["aggregate_id"]: row["snapshot_id"]
        for row in db.many(connection, select(db.heads).order_by(db.heads.c.aggregate_id))
    }


def load_cut(connection, cut):
    rows = db.many(connection, select(db.snapshots).where(db.snapshots.c.id.in_(list(cut.values()))))
    return {row["aggregate_id"]: row for row in rows if not row["tombstone"]}
