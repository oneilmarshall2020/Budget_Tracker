# Changing the tables (migrations) and backups

Your database now has a version history. `migrations/versions/` holds numbered steps
(`0001_baseline.py`, then one file per change). On startup the backend applies any step
your database hasn't had yet, **after backing it up**. You never delete `database.db` again.

| Step | What it changed |
|---|---|
| `0001_baseline.py` | The six tables as they were before migrations existed |
| `0002_users.py` | Logins: the `users` and `login_session` tables, and a `user_id` on every data table. Data that existed before goes to a user called `owner` (see `ACCOUNTS.md`) |

## Every time you change `models.py`

Run these from the `backend` folder with the venv active.

1. **Edit `models.py`**, e.g. add `note: str | None = None` to `Transaction`.
2. **Generate the step:**
   ```bash
   alembic revision --autogenerate -m "add note to transactions"
   ```
   Alembic compares your models with the database and writes a new file in
   `migrations/versions/`.
3. **Read the new file's `upgrade()`** and check that it does what you meant (see the gotchas below).
4. **Restart the backend.** It backs up `database.db` into `backups/`, then applies the step.
   You'll see `Your tables need updating. Backed up the database first: ...` in the terminal.
5. **Commit `models.py` and the new migration file together.** They belong to each other.

## Gotchas

- **New required column on a table that has rows:** the existing rows have no value for it, so the
  upgrade fails. Either make it optional (`str | None = None`) or give the database a default:
  `Field(default="JMD", sa_column_kwargs={"server_default": "JMD"})`.
- **Renaming a column:** autogenerate sees "drop the old one, add a new one", which **loses the data**.
  Edit the file to `batch_op.alter_column("old_name", new_column_name="new_name")` instead.
- **Never edit a migration that already ran on your real database.** Make a new one that fixes it.
- **Not sure what a step will do?** `alembic upgrade head --sql` prints the SQL without running it.
- **A new data table needs a `user_id`** like the others (`Field(foreign_key="users.id", index=True)`),
  and every query on it needs `.where(Model.user_id == user.id)`. Otherwise everyone sees everyone's rows.

## Handy commands

| Command | What it does |
|---|---|
| `alembic current` | Which step your database is at |
| `alembic history` | All the steps, newest first |
| `alembic check` | Do the models and the migrations agree? ("No new upgrade operations detected" = yes) |
| `alembic upgrade head` | Apply waiting steps now (the backend does this on startup anyway) |

## Backups

- **Automatic:** right before any table change, into `backups/`.
- **Anytime:** `python backup.py`
- **Restore:**
  1. Stop the backend (Ctrl + C).
  2. `cp backups/<the file you want>.db database.db`
  3. Start the backend again.
- Only the newest 30 are kept. `backups/` holds `.db` files, so your `.gitignore` (`*.db`)
  already keeps them out of GitHub.
