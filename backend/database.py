import os
from typing import Annotated

from fastapi import Depends
from sqlalchemy import event
from sqlmodel import Session, create_engine


def postgres_url(url: str) -> str:
    """Neon (and most hosts) hand out addresses starting postgres:// or postgresql://.
    SQLAlchemy needs to be told which driver to use, and ours is psycopg (version 3)."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


# Where the database lives. Locally that's database.db in the backend folder.
# Anywhere else (tests, or a host when you deploy) set the DATABASE_URL environment
# variable instead, e.g. a temporary file for tests or a Postgres address in production.
if os.environ.get("VERCEL") and not os.environ.get("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL isn't set. Add it in the Vercel project's Environment Variables.")
DATABASE_URL = postgres_url(os.environ.get("DATABASE_URL", "sqlite:///database.db"))

# Print every SQL statement in the terminal: on by default for your local database.db
# (handy while learning), off elsewhere, because the printout includes everyone's data.
# ECHO_SQL=1 or ECHO_SQL=0 overrides it.
ECHO_SQL = os.environ.get("ECHO_SQL", "1" if DATABASE_URL.startswith("sqlite") else "0") == "1"


def make_engine(url: str, echo: bool = False):
    """Create the connection to a database. Tests use this to make throwaway databases."""
    url = postgres_url(url)
    if url.startswith("sqlite"):
        engine = create_engine(url, echo=echo)

        # SQLite ignores foreign keys unless told otherwise, on every new connection.
        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine

    return create_engine(
        url,
        echo=echo,
        # Neon puts the database to sleep when nobody's using it, which quietly closes any
        # connections we were keeping. Check each one still works before using it.
        pool_pre_ping=True,
        # Don't keep "prepared" queries on the server: Neon's connection pooler can hand
        # the next query to a different server connection, which wouldn't have them.
        connect_args={"prepare_threshold": None},
    )


engine = make_engine(DATABASE_URL, echo=ECHO_SQL)


def get_session():
    # `engine` is looked up when a request comes in, so tests can swap it for a test database.
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
