"""Manage logins from the terminal. From the backend folder, with the venv active:

    python users.py list                  who has an account
    python users.py claim                 make the data from before logins existed yours
    python users.py create                make a new account (no sign-up code needed)
    python users.py set-password NAME     choose a new password for NAME (forgot it?)

These work on whichever database the app uses: database.db, or the one DATABASE_URL
points to (so the same commands work on your deployed database).
"""
import getpass
import os
import sys

os.environ.setdefault("ECHO_SQL", "0")  # keep the terminal readable: no SQL printout

from sqlmodel import Session, func, select  # noqa: E402

import database  # noqa: E402
from auth import hash_password  # noqa: E402
from migrate import run_migrations  # noqa: E402
from models import (  # noqa: E402
    Account,
    Category,
    CategoryRule,
    LoginSession,
    StatementImport,
    Transaction,
    User,
    check_password,
    clean_username,
)

PLACEHOLDER = "owner"  # who the data from before logins belongs to (migration 0002)


# ---------------------------------------------------------------- the actual work
def find_user(session: Session, username: str) -> User | None:
    return session.exec(select(User).where(User.username == username)).first()


def unclaimed_owner(session: Session) -> User | None:
    return session.exec(
        select(User).where(User.username == PLACEHOLDER, User.password_hash == "")
    ).first()


def claim(session: Session, username: str, password: str) -> User:
    """Give the placeholder "owner" (and so all its data) a real username and password."""
    username, password = clean_username(username), check_password(password)
    owner = unclaimed_owner(session)
    if owner is None:
        raise LookupError("There's no unclaimed data. (Already claimed, or the database was empty.)")
    taken = find_user(session, username)
    if taken and taken.id != owner.id:
        raise ValueError("That username is taken")
    owner.username = username
    owner.password_hash = hash_password(password)
    session.add(owner)
    session.commit()
    return owner


def create(session: Session, username: str, password: str) -> User:
    username, password = clean_username(username), check_password(password)
    if find_user(session, username):
        raise ValueError("That username is taken")
    user = User(username=username, password_hash=hash_password(password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def set_password(session: Session, username: str, password: str) -> User:
    """New password, unlock the account, and log it out everywhere."""
    user = find_user(session, username.strip().lower())
    if user is None:
        raise LookupError(f"There's no user called {username}")
    user.password_hash = hash_password(check_password(password))
    user.failed_logins, user.locked_until = 0, None
    session.add(user)
    for login in session.exec(select(LoginSession).where(LoginSession.user_id == user.id)).all():
        session.delete(login)  # logged out everywhere
    session.commit()
    return user


def counts(session: Session, user: User) -> str:
    def count(model):
        return session.exec(select(func.count()).select_from(model).where(model.user_id == user.id)).one()

    return (
        f"{count(Transaction)} transactions, {count(Account)} accounts, {count(Category)} categories, "
        f"{count(CategoryRule)} keywords, {count(StatementImport)} imports"
    )


# ---------------------------------------------------------------- asking in the terminal
def ask_username(prompt: str = "Username: ") -> str:
    while True:
        try:
            return clean_username(input(prompt))
        except ValueError as error:
            print(error)


def ask_password() -> str:
    while True:
        first = getpass.getpass("Password (at least 8 characters, typing stays hidden): ")
        try:
            check_password(first)
        except ValueError as error:
            print(error)
            continue
        if getpass.getpass("Same password again: ") != first:
            print("Those didn't match. Try again.")
            continue
        return first


def main(args: list[str]) -> int:
    command = args[0] if args else "help"
    run_migrations()  # make sure the users table exists before we touch it

    with Session(database.engine) as session:
        if command == "list":
            users = session.exec(select(User).order_by(User.username)).all()
            if not users:
                print("No accounts yet.")
            for user in users:
                note = "  (unclaimed: run  python users.py claim)" if user.password_hash == "" else ""
                print(f"{user.username}: {counts(session, user)}{note}")
            return 0

        if command == "claim":
            if unclaimed_owner(session) is None:
                print("There's no unclaimed data. (Already claimed, or the database was empty.)")
                return 1
            print("Pick the username and password you'll log in with. All your existing data goes to it.")
            while True:
                try:
                    user = claim(session, ask_username(), ask_password())
                    break
                except ValueError as error:
                    print(error)
            print(f"Done. {user.username} now has {counts(session, user)}.")
            return 0

        if command == "create":
            while True:
                try:
                    user = create(session, ask_username(), ask_password())
                    break
                except ValueError as error:
                    print(error)
            print(f"Created {user.username}. They can log in now.")
            return 0

        if command == "set-password" and len(args) == 2:
            username = args[1].strip().lower()
            if find_user(session, username) is None:
                print(f"There's no user called {username}. Try:  python users.py list")
                return 1
            set_password(session, username, ask_password())
            print(f"New password saved for {username}. They're logged out everywhere, so log in again.")
            return 0

    print(__doc__)
    return 0 if command == "help" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
