"""Copy your database into backups/ (safe even while the app is running).

Usage, from the backend folder with the venv active:
    python backup.py

To restore a backup:
    1. Stop the backend (Ctrl + C).
    2. Copy the backup over the live file:   cp backups/<the file>.db database.db
    3. Start the backend again.

The app also makes a backup by itself right before it changes your tables (see migrate.py).
"""
import datetime
from contextlib import closing
from pathlib import Path

import sqlite3

import database

KEEP = 30  # keep the newest 30 backups, delete older ones


def database_path() -> Path:
    """The same file the app uses (database.py decides where it is)."""
    return Path(database.engine.url.database).resolve()


def backup_database(reason: str = "manual") -> Path:
    if database.engine.dialect.name != "sqlite":
        raise RuntimeError("backup.py copies SQLite files. For Postgres, use your host's backups.")
    source = database_path()
    folder = source.parent / "backups"
    folder.mkdir(exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    target = folder / f"database_{stamp}_{reason}.db"

    # SQLite's own backup copies a consistent snapshot, even if the app is writing.
    with closing(sqlite3.connect(source)) as live, closing(sqlite3.connect(target)) as copy:
        live.backup(copy)

    for old in sorted(folder.glob("database_*.db"))[:-KEEP]:
        old.unlink()
    return target


if __name__ == "__main__":
    if not database_path().exists():
        print("There's no database.db yet, so there's nothing to back up.")
    else:
        print(f"Saved a backup: {backup_database()}")
