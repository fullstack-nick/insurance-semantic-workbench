"""Relational contracts; Alembic alone creates or changes these tables."""

from datetime import UTC, datetime
from functools import lru_cache

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.dialects.postgresql import JSONB

from .config import settings

metadata = MetaData()
MAINTENANCE_LOCK = 91422073


def now():
    return datetime.now(UTC)


def table(name, *columns, schema="workbench", constraints=()):
    return Table(name, metadata, *columns, *constraints, schema=schema)


def key(name="id"):
    return Column(name, String, primary_key=True)


def js(name, default=None):
    return Column(name, JSONB, nullable=False, default=default or dict)


def stamp(name="created_at"):
    return Column(name, DateTime(timezone=True), nullable=False, default=now)


policies = table(
    "policies",
    key(),
    Column("country", String, nullable=False),
    Column("product", String, nullable=False),
    js("payload"),
    schema="source",
)
policy_versions = table(
    "policy_versions",
    key(),
    Column("policy_id", String, nullable=False),
    Column("valid_from", Date, nullable=False),
    Column("valid_to", Date),
    js("payload"),
    schema="source",
)
claims = table(
    "claims",
    key(),
    Column("country", String, nullable=False),
    Column("policy_id", String, nullable=False),
    Column("loss_date", Date),
    Column("revision", Integer, nullable=False),
    js("payload"),
    schema="source",
)
documents = table(
    "document_versions",
    key(),
    Column("document_id", String, nullable=False),
    Column("country", String, nullable=False),
    Column("sha256", String, nullable=False),
    js("payload"),
    schema="source",
)
snapshots = table(
    "source_snapshots",
    key(),
    Column("aggregate_id", String, nullable=False),
    Column("version", Integer, nullable=False),
    Column("kind", String, nullable=False),
    Column("country", String, nullable=False),
    Column("sha256", String, nullable=False),
    Column("tombstone", Boolean, nullable=False, default=False),
    js("payload"),
    stamp(),
    constraints=(UniqueConstraint("aggregate_id", "version"),),
    schema="source",
)
heads = table(
    "source_heads",
    key("aggregate_id"),
    Column("snapshot_id", String, nullable=False),
    Column("version", Integer, nullable=False),
    Column("kind", String, nullable=False),
    Column("country", String, nullable=False),
    schema="source",
)
outbox = table(
    "outbox_events",
    key("event_id"),
    Column("aggregate_id", String, nullable=False),
    Column("aggregate_version", Integer, nullable=False),
    Column("snapshot_id", String, nullable=False),
    Column("event_type", String, nullable=False),
    Column("schema_version", Integer, default=1),
    Column("country", String, nullable=False),
    Column("correlation_id", String, nullable=False),
    Column("state", String, default="queued", nullable=False),
    stamp("occurred_at"),
    schema="source",
)
receipts = table(
    "event_receipts",
    key("event_id"),
    Column("outcome", String, nullable=False),
    Column("projection_id", String),
    Column("attempts", Integer, default=1),
    stamp(),
)
releases = table(
    "semantic_releases",
    key(),
    Column("predecessor", String),
    Column("state", String, nullable=False),
    js("manifest"),
    Column("candidate_id", String),
    stamp(),
)
projections = table(
    "projection_snapshots",
    key(),
    Column("release_id", String, nullable=False),
    Column("state", String, nullable=False),
    js("source_cut"),
    js("cases"),
    js("validation", list),
    js("manifest"),
    Column("watermark", String, nullable=False),
    Column("epoch", Integer, nullable=False),
    Column("error", Text),
    stamp(),
)
active = table(
    "active_snapshot",
    Column("id", Integer, primary_key=True),
    Column("projection_id", String),
    Column("release_id", String, nullable=False),
    Column("epoch", Integer, nullable=False, default=0),
)
jobs = table(
    "projection_jobs",
    key(),
    Column("kind", String, nullable=False),
    Column("state", String, nullable=False),
    js("payload"),
    Column("attempts", Integer, default=0),
    Column("error", Text),
    Column("lease_until", DateTime(timezone=True)),
    stamp(),
)
embeddings = table(
    "embedding_cache",
    key(),
    Column("manifest_hash", String, nullable=False),
    Column("vector", Vector(384), nullable=False),
)
evidence = table(
    "evidence_items",
    key(),
    Column("projection_id", String, nullable=False, index=True),
    Column("case_id", String, nullable=False, index=True),
    Column("country", String, nullable=False),
    Column("group_id", String, nullable=False),
    Column("kind", String, nullable=False),
    Column("text", Text, nullable=False),
    Column("embedding_id", String, nullable=False),
    js("payload"),
)
bundles = table(
    "evidence_bundles",
    key(),
    Column("case_id", String, nullable=False),
    Column("projection_id", String, nullable=False),
    js("payload"),
    stamp(),
)
proposals = table(
    "mapping_proposals",
    key(),
    Column("country", String, nullable=False),
    Column("state", String, nullable=False),
    js("payload"),
    stamp(),
)
decisions = table(
    "review_decisions",
    key(),
    Column("case_id", String),
    Column("projection_id", String),
    Column("actor", String, nullable=False),
    Column("action", String, nullable=False),
    Column("rationale", Text, nullable=False),
    js("payload"),
    stamp(),
)
runs = table(
    "agent_runs",
    key(),
    Column("case_id", String),
    Column("projection_id", String, nullable=False),
    Column("role", String, nullable=False),
    Column("state", String, nullable=False),
    Column("token_hash", String, nullable=False),
    Column("expires_at", DateTime(timezone=True)),
    Column("thread_id", String),
    Column("turn_id", String),
    Column("model", String),
    Column("tool_count", Integer, default=0),
    Column("cancel_requested", Boolean, default=False),
    js("issued_ids", list),
    js("bundle_ids", list),
    js("result"),
    Column("error", Text),
    stamp(),
    Column("finished_at", DateTime(timezone=True)),
)
run_events = table(
    "run_events",
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("run_id", String, nullable=False, index=True),
    Column("kind", String, nullable=False),
    js("payload"),
    stamp(),
)
audits = table("audit_events", key(), Column("action", String, nullable=False), js("payload"), stamp())
state = table("local_state", key(), js("payload"), stamp())


@lru_cache
def engine(role="app"):
    result = create_engine(
        settings().role_url(role),
        pool_pre_ping=True,
        pool_size=8,
        max_overflow=4,
        hide_parameters=True,
        connect_args={"connect_timeout": 5},
    )

    @event.listens_for(result, "begin")
    def maintenance_fence(connection):
        connection.exec_driver_sql(f"SELECT pg_advisory_xact_lock_shared({MAINTENANCE_LOCK})")

    return result


def configure_roles():
    """Run only during setup with the migration identity; no passwords enter diagnostics."""
    from psycopg import sql

    with engine("migration").begin() as connection:
        cursor = connection.connection.driver_connection.cursor()
        for role in ["app", "source", "worker", "reader"]:
            name = "isw_" + role
            password = getattr(settings(), f"db_{role}_password")
            if not password:
                raise ValueError("Setup must generate all role passwords")
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (name,))
            statement = (
                "ALTER ROLE {} LOGIN PASSWORD {}" if cursor.fetchone() else "CREATE ROLE {} LOGIN PASSWORD {}"
            )
            cursor.execute(sql.SQL(statement).format(sql.Identifier(name), sql.Literal(password)))
            cursor.execute(
                sql.SQL("GRANT USAGE ON SCHEMA source,workbench TO {}").format(sql.Identifier(name))
            )
            cursor.execute(
                sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA source,workbench TO {}").format(
                    sql.Identifier(name)
                )
            )
            if role in {"app", "worker"}:
                cursor.execute(
                    sql.SQL("GRANT INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA workbench TO {}").format(
                        sql.Identifier(name)
                    )
                )
                cursor.execute(
                    sql.SQL("GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA workbench TO {}").format(
                        sql.Identifier(name)
                    )
                )
            if role == "source":
                cursor.execute(
                    sql.SQL("GRANT INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA source TO {}").format(
                        sql.Identifier(name)
                    )
                )
                cursor.execute(
                    sql.SQL("GRANT INSERT ON workbench.event_receipts TO {}").format(sql.Identifier(name))
                )
            if role == "worker":
                cursor.execute(
                    sql.SQL("GRANT UPDATE(state) ON source.outbox_events TO {}").format(sql.Identifier(name))
                )


def one(connection, statement):
    row = connection.execute(statement).mappings().first()
    return dict(row) if row else None


def many(connection, statement):
    return [dict(row) for row in connection.execute(statement).mappings()]
