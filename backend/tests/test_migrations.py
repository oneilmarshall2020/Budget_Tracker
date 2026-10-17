"""Migrations and backups: new databases, databases made before migrations, and backups."""
import datetime

import sqlite3
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlmodel import Session, SQLModel

import database
import models
from backup import backup_database
from migrate import BASELINE, run_migrations


def version_of(engine):
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def test_a_new_database_gets_every_table_and_the_newest_version(client):
    assert version_of(database.engine) is not None


def test_models_and_migrations_agree(client):
    """If this fails, you changed models.py without making a migration:
    run  alembic revision --autogenerate -m "what changed"  """
    with database.engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), SQLModel.metadata)
    assert differences == []


def test_a_database_made_before_migrations_is_kept_and_marked(tmp_path, monkeypatch):
    engine = database.make_engine(f"sqlite:///{tmp_path / 'old.db'}")
    monkeypatch.setattr(database, "engine", engine)
    SQLModel.metadata.create_all(engine)  # how the app used to build its tables
    with Session(engine) as session:
        session.add(models.Transaction(amount=100, date=datetime.date(2026, 9, 1), description="Old row", type="expense"))
        session.commit()

    run_migrations()

    assert version_of(engine) == BASELINE, "marked as the starting point, not rebuilt"
    with engine.connect() as connection:
        assert connection.exec_driver_sql("select description from transactions").scalars().all() == ["Old row"]
    assert not (tmp_path / "backups").exists(), "nothing changed, so no backup was needed"
    engine.dispose()


def test_backup_is_a_full_copy(tmp_path, monkeypatch, api):
    api.log(250, "2026-09-01", "Backed up row")
    monkeypatch.setattr(database, "engine", database.engine)  # the test database from `api`

    saved = backup_database(reason="test")

    assert saved.parent.name == "backups" and saved.exists()
    with sqlite3.connect(saved) as copy:
        assert copy.execute("select description from transactions").fetchall() == [("Backed up row",)]
