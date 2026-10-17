"""Keep the database's tables in step with models.py, automatically, on startup.

How it works:
  - migrations/versions/ holds numbered steps (0001, 0002, ...), each one a change to the tables.
  - The database remembers the last step it got (in a small table called alembic_version).
  - On startup we run any steps it hasn't had yet, after backing it up.

You make a new step when you change models.py:
    alembic revision --autogenerate -m "what changed"
Then restart the backend. (MIGRATIONS.md has the full walkthrough.)
"""
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

import database
from backup import backup_database

BACKEND = Path(__file__).resolve().parent
BASELINE = "0001"  # the first step: the tables as they were before migrations existed


def alembic_config() -> Config:
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "migrations"))
    config.attributes["configure_logger"] = False  # keep the app's own logging
    return config


def run_migrations() -> None:
    config = alembic_config()
    newest = ScriptDirectory.from_config(config).get_current_head()

    with database.engine.connect() as connection:
        tables = inspect(connection).get_table_names()
        current = MigrationContext.configure(connection).get_current_revision()

    if not tables:
        command.upgrade(config, "head")  # brand-new database: build every table
        return

    if current is None:
        # Made before migrations existed (by the old create_all): it already has the
        # baseline tables, so just record that instead of creating them again.
        command.stamp(config, BASELINE)
        current = BASELINE

    if current != newest:
        if database.engine.dialect.name == "sqlite":
            saved = backup_database(reason=f"before-update-to-{newest}")
            print(f"Your tables need updating. Backed up the database first: {saved}")
        command.upgrade(config, "head")
