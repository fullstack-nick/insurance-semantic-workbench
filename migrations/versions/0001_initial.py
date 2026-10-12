"""Immutable evidence and publication contracts."""

from alembic import op
from insurance_workbench.db import metadata

revision = "0001"
down_revision = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE SCHEMA IF NOT EXISTS source")
    op.execute("CREATE SCHEMA IF NOT EXISTS workbench")
    metadata.create_all(op.get_bind())


def downgrade():
    raise RuntimeError("Use a verified backup restore; destructive schema downgrade is unsupported")
