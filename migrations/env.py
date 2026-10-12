from alembic import context
from insurance_workbench.db import engine, metadata

with engine("migration").connect() as connection:
    context.configure(connection=connection, target_metadata=metadata, include_schemas=True)
    with context.begin_transaction():
        context.run_migrations()
