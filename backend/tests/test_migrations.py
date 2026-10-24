"""Migrations and backups: new databases, databases made before migrations, and backups."""
import sqlite3

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, select

import database
import models
import users
from backup import backup_database
from main import app
from migrate import BASELINE, alembic_config, run_migrations


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


def old_database(tmp_path, monkeypatch, name="old.db"):
    """A database as the app built it before logins existed (migration 0001 only)."""
    engine = database.make_engine(f"sqlite:///{tmp_path / name}")
    monkeypatch.setattr(database, "engine", engine)
    command.upgrade(alembic_config(), BASELINE)
    return engine


def newest_version():
    return ScriptDirectory.from_config(alembic_config()).get_current_head()


def test_a_database_made_before_migrations_is_kept_and_marked(tmp_path, monkeypatch):
    engine = old_database(tmp_path, monkeypatch)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE alembic_version")  # made before migrations existed
        connection.exec_driver_sql(
            "INSERT INTO transactions (amount, date, description, type, source) "
            "VALUES (100, '2026-09-01', 'Old row', 'expense', 'manual')"
        )

    run_migrations()

    assert version_of(engine) == newest_version(), "marked as the starting point, then updated"
    with engine.connect() as connection:
        assert connection.exec_driver_sql("select description from transactions").scalars().all() == ["Old row"]
    assert (tmp_path / "backups").exists(), "tables changed, so it backed up first"
    engine.dispose()


def test_data_from_before_logins_goes_to_one_owner_who_can_claim_it(tmp_path, monkeypatch):
    engine = old_database(tmp_path, monkeypatch)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO account (nickname, bank_name, account_type, last_four, currency) "
            "VALUES ('NCB Savings', 'NCB', 'savings', '0042', 'JMD')"
        )
        connection.exec_driver_sql("INSERT INTO category (name, kind) VALUES ('Food', 'expense')")
        connection.exec_driver_sql("INSERT INTO category_rule (keyword, category_id) VALUES ('JUICI', 1)")
        connection.exec_driver_sql(
            "INSERT INTO transactions (amount, date, description, type, source, category_id, account_id) "
            "VALUES (1580, '2026-09-21', 'Lunch at Juici', 'expense', 'manual', 1, 1)"
        )

    run_migrations()
    with Session(engine) as session:
        owner = session.exec(select(models.User)).one()
        assert (owner.username, owner.password_hash) == ("owner", "")
        assert session.exec(select(models.Transaction)).one().user_id == owner.id

    with TestClient(app) as browser:
        tried = browser.post("/auth/login", json={"username": "owner", "password": "anything at all"})
        assert tried.status_code == 401, "nobody can log in as the placeholder"

        with Session(engine) as session:
            users.claim(session, "oj", "my long password")
        assert browser.post("/auth/login", json={"username": "oj", "password": "my long password"}).status_code == 200
        assert [t["description"] for t in browser.get("/transaction/").json()] == ["Lunch at Juici"]
        assert [r["keyword"] for r in browser.get("/rules/").json()] == ["JUICI"]
    engine.dispose()


def test_an_empty_database_gets_no_placeholder(tmp_path, monkeypatch):
    engine = old_database(tmp_path, monkeypatch)
    run_migrations()
    with Session(engine) as session:
        assert session.exec(select(models.User)).all() == []
        with pytest.raises(LookupError):
            users.claim(session, "oj", "my long password")
    engine.dispose()


def test_backup_is_a_full_copy(tmp_path, monkeypatch, api):
    api.log(250, "2026-09-01", "Backed up row")
    monkeypatch.setattr(database, "engine", database.engine)  # the test database from `api`

    saved = backup_database(reason="test")

    assert saved.parent.name == "backups" and saved.exists()
    with sqlite3.connect(saved) as copy:
        assert copy.execute("select description from transactions").fetchall() == [("Backed up row",)]
