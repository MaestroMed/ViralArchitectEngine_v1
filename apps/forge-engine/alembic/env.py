"""Alembic migration environment for FORGE Engine.

Migrations run against a *synchronous* SQLite engine (the app uses aiosqlite at
runtime, but Alembic does its DDL synchronously — simpler and avoids an async
event loop here). The target metadata is the app's ``Base.metadata`` with every
model imported, so ``--autogenerate`` and the no-drift test see the full schema.

The DB URL defaults to the app's configured ``DATABASE_PATH`` and can be
overridden with the ``FORGE_DATABASE_URL`` env var (used by tests to point at a
throwaway file).
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# Make the app importable when alembic is invoked from apps/forge-engine.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from forge_engine.core.config import settings  # noqa: E402
from forge_engine.core.database import Base  # noqa: E402

# Import every model so its table is registered on Base.metadata.
from forge_engine.models import (  # noqa: E402,F401
    api_key,
    artifact,
    channel,
    job,
    profile,
    project,
    review,
    segment,
    template,
    training_data,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    """Resolve the sync SQLite URL (env override > app settings)."""
    override = os.environ.get("FORGE_DATABASE_URL")
    if override:
        return override
    return f"sqlite:///{settings.DATABASE_PATH}"


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live DB connection."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite needs batch mode for ALTER TABLE.
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live (sync) engine."""
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite batch mode for safe ALTERs.
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
