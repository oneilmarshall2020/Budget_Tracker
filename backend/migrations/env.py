"""How Alembic connects to the database and knows what the tables should look like.

You don't run this file yourself: the `alembic` command and migrate.py use it.
"""
from logging.config import fileConfig

from alembic import context
from sqlmodel import SQLModel

import database
import models  # noqa: F401  importing the models registers every table on SQLModel.metadata

config = context.config

# Logging setup, only when you run the `alembic` command (the app has its own logging).
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# "What the tables should look like" = your models. Autogenerate compares this to the database.
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Print the SQL instead of running it:  alembic upgrade head --sql"""
    context.configure(
        url=str(database.engine.url),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run the migrations against database.db (same engine as the app)."""
    with database.engine.connect() as connection:
        sqlite = connection.dialect.name == "sqlite"
        if sqlite:
            # SQLite can't change most columns in place, so Alembic rebuilds the table
            # ("batch" mode): create a new one, copy the rows over, drop the old one.
            # Foreign-key checks would refuse that drop, so they're off during migrations
            # (database.py turns them back on for every normal connection).
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            # Running that statement quietly opened a transaction. Close it, otherwise
            # Alembic thinks someone else owns it and never commits the migration.
            connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()
        if sqlite:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
