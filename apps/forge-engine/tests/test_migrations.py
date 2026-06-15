"""Alembic migration tests.

Two guarantees:
1. `alembic upgrade head` builds a database from scratch containing every table
   the app models declare (no model is left out of the migrations).
2. After upgrading, there is ZERO schema drift between the migrations and
   `Base.metadata` — i.e. the moment someone adds/changes a model without a
   matching migration, this test fails. This is the safety net that replaces
   relying on `create_all`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from forge_engine.core.database import Base

# Import every model so Base.metadata is fully populated for the drift check.
from forge_engine.models import (  # noqa: F401
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

ENGINE_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = ENGINE_ROOT / "alembic.ini"


@pytest.fixture
def alembic_config(tmp_path, monkeypatch) -> Config:
    """Alembic config pointed at a throwaway SQLite file via FORGE_DATABASE_URL."""
    db_url = f"sqlite:///{tmp_path / 'forge.db'}"
    monkeypatch.setenv("FORGE_DATABASE_URL", db_url)
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ENGINE_ROOT / "alembic"))
    # Stash for assertions.
    cfg.attributes["db_url"] = db_url
    return cfg


def test_upgrade_head_creates_all_model_tables(alembic_config):
    command.upgrade(alembic_config, "head")

    engine = create_engine(alembic_config.attributes["db_url"])
    tables = set(inspect(engine).get_table_names())
    engine.dispose()

    expected = set(Base.metadata.tables.keys())
    missing = expected - tables
    assert not missing, f"Migration head is missing tables: {sorted(missing)}"
    # alembic's own bookkeeping table is present too.
    assert "alembic_version" in tables


def test_no_drift_between_models_and_migrations(alembic_config):
    """models == migrations: autogenerate would produce no changes."""
    command.upgrade(alembic_config, "head")

    engine = create_engine(alembic_config.attributes["db_url"])
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"render_as_batch": True})
        diffs = compare_metadata(ctx, Base.metadata)
    engine.dispose()

    assert diffs == [], (
        "Schema drift between models and migrations. Run:\n"
        "  PYTHONPATH=src alembic revision --autogenerate -m '<change>'\n"
        f"Pending diffs: {diffs}"
    )


def test_downgrade_base_is_reversible(alembic_config):
    """upgrade→downgrade round-trips without error and drops the schema."""
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "base")

    engine = create_engine(alembic_config.attributes["db_url"])
    tables = set(inspect(engine).get_table_names())
    engine.dispose()

    # Only alembic's version table may remain after a full downgrade.
    assert tables <= {"alembic_version"}
