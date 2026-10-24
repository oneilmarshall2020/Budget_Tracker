"""Copy everything in your local database.db into your deployed Postgres database. Once.

From the backend folder, venv active, with the backend stopped:

    DATABASE_URL="postgresql://...your Neon address..." python copy_to_postgres.py

What it does:
  1. Builds the tables in Postgres (the same migrations the app runs).
  2. Copies every user, account, category, keyword, budget, import and transaction,
     keeping their ids so everything still points at the right thing.
  3. Leaves out logins (the login_session table): you just log in again on the new site.

It refuses to run if the Postgres database already has users in it, so running it twice
can't make duplicates. Your database.db isn't changed.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("ECHO_SQL", "0")

from sqlalchemy import func, select, text  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

import database  # noqa: E402
import models  # noqa: E402,F401  registers every table on SQLModel.metadata
from migrate import run_migrations  # noqa: E402

LOCAL_FILE = Path(__file__).resolve().parent / "database.db"
SKIP = {"login_session"}  # logins stay behind


def copy(source_engine, target_engine) -> dict[str, int]:
    """Copy every table, parents before children (accounts before their transactions)."""
    tables = [t for t in SQLModel.metadata.sorted_tables if t.name not in SKIP]
    copied = {}
    with source_engine.connect() as source, target_engine.begin() as target:
        if target.execute(select(func.count()).select_from(models.User.__table__)).scalar():
            raise RuntimeError("The Postgres database already has users in it. Nothing was copied.")
        if source.execute(
            select(func.count()).select_from(models.User.__table__).where(models.User.password_hash == "")
        ).scalar():
            raise RuntimeError("Your data is still unclaimed. Run  python users.py claim  first.")

        for table in tables:
            rows = [dict(row) for row in source.execute(select(table)).mappings()]
            if rows:
                target.execute(table.insert(), rows)
            copied[table.name] = len(rows)

        # Postgres hands out new ids from a counter per table. Move each counter past the
        # ids we just copied, or the next new row would try to reuse id 1.
        for table in tables:
            target.execute(text(
                f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {table.name}), 0) + 1, false)"
            ))
    return copied


def main() -> int:
    target_engine = database.engine
    if target_engine.dialect.name != "postgresql":
        print('Set DATABASE_URL to your Neon address first, e.g.\n'
              '    DATABASE_URL="postgresql://..." python copy_to_postgres.py')
        return 1
    if not LOCAL_FILE.exists():
        print(f"There's no {LOCAL_FILE.name} here to copy from.")
        return 1

    try:
        with target_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError as error:
        print("Couldn't connect to the Postgres database. Copy the address from Neon again and")
        print("check it's inside the quotes. What Postgres said:")
        print("   ", str(error.orig).strip().splitlines()[0])
        return 1

    source_engine = database.make_engine(f"sqlite:///{LOCAL_FILE}")

    # Bring both databases to the newest tables: database.db (backed up first, as always)
    # and Postgres (built from scratch the first time).
    database.engine = source_engine
    run_migrations()
    database.engine = target_engine
    run_migrations()

    try:
        copied = copy(source_engine, target_engine)
    except RuntimeError as error:
        print(error)
        return 1
    finally:
        source_engine.dispose()

    print("Copied:")
    for name, count in copied.items():
        print(f"  {count:>5}  {name}")
    print("Done. Log in on your deployed site with the same username and password.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
