import os
from typing import Annotated

from fastapi import Depends
from sqlalchemy import event
from sqlmodel import Session, create_engine

# Where the database lives. Locally that's database.db in the backend folder.
# Anywhere else (tests, or a host when you deploy) set the DATABASE_URL environment
# variable instead, e.g. a temporary file for tests or a Postgres address in production.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///database.db")

# Print every SQL statement in the terminal (handy while learning). ECHO_SQL=0 turns it off.
ECHO_SQL = os.environ.get("ECHO_SQL", "1") == "1"


def make_engine(url: str, echo: bool = False):
    """Create the connection to a database. Tests use this to make throwaway databases."""
    engine = create_engine(url, echo=echo)

    if url.startswith("sqlite"):
        # SQLite ignores foreign keys unless told otherwise, on every new connection.
        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine = make_engine(DATABASE_URL, echo=ECHO_SQL)


def get_session():
    # `engine` is looked up when a request comes in, so tests can swap it for a test database.
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
