"""Demo accounts: a private, throwaway account full of made-up money, so people can try
Ledger without typing in anything real.

  - "Try the demo" on the login page creates one and logs straight in.
  - It starts with two accounts, the suggested categories and keywords, budgets, and
    everyday spending for last month and this month. samples/ncb_sample_statement.pdf
    is a made-up NCB statement for September 2026: importing it fills that month and
    shows the review screen at work (one row is already logged by hand, one is a
    transfer from the demo's savings account).
  - Each demo is deleted after DEMO_DAYS, or straight away with "End demo".

Settings (environment variables):
  DEMO_CODE     if set, starting a demo needs this code. Send people the link
                https://<your site>/?demo=<the code> and the button does the rest.
                Not set: demos are open on your laptop, and off once deployed.
"""
import datetime
import os
import secrets
from pathlib import Path

from sqlmodel import Session, delete, select

from auth import as_utc
from models import (
    Account,
    AccountType,
    Budget,
    Category,
    CategoryRule,
    LoginSession,
    StatementImport,
    Transaction,
    TransactionType,
    User,
    utc_now,
)

DEMO_DAYS = 7  # a demo deletes itself after a week
MAX_DEMOS = 200  # at most this many demos at once, so nobody can fill the database
SAMPLE_STATEMENT = Path(__file__).resolve().parent / "samples" / "ncb_sample_statement.pdf"
SAMPLE_MONTH = (2026, 9)  # the month the sample statement covers

# The everyday spending a demo month starts with: (day, description, amount, type, category).
# Pay comes first, so a demo opened on any day of the month doesn't start "overspent".
EVERYDAY = [
    (1, "Salary", 85000, TransactionType.income, "Salary"),
    (1, "JPS electricity bill", 6850, TransactionType.expense, "Utilities"),
    (2, "Hi-Lo groceries", 7420, TransactionType.expense, "Groceries"),
    (3, "Taxi to campus", 600, TransactionType.expense, "Transport & Gas"),
    (5, "Digicel top-up", 1500, TransactionType.expense, "Phone & Internet"),
    (6, "Juici Patties lunch", 950, TransactionType.expense, "Food & Dining"),
    (8, "Netflix", 1650, TransactionType.expense, "Subscriptions"),
    (10, "Total gas station", 4000, TransactionType.expense, "Transport & Gas"),
    (12, "Campus Foods snacks", 480, TransactionType.expense, "Food & Dining"),
    (14, "NWC water bill", 2300, TransactionType.expense, "Utilities"),
    (15, "Moving money to savings", 10000, TransactionType.transfer, None),
    (17, "Megamart groceries", 9850, TransactionType.expense, "Groceries"),
    (19, "KFC dinner", 2100, TransactionType.expense, "Food & Dining"),
    (22, "Pharmacy", 1850, TransactionType.expense, "Health"),
    (27, "Island Grill", 1600, TransactionType.expense, "Food & Dining"),
    (28, "Bus fare", 300, TransactionType.expense, "Transport & Gas"),
]
# Groceries goes over by the 17th, so there's an "over budget" to see. The rest stay under.
BUDGETS = {
    "Food & Dining": 12000,
    "Groceries": 15000,
    "Transport & Gas": 8000,
    "Phone & Internet": 3000,
    "Subscriptions": 3500,
    "Utilities": 10000,
}


def demo_code() -> str:
    return os.environ.get("DEMO_CODE", "").strip()


def demo_mode() -> str:
    """"code" = needs DEMO_CODE, "open" = anyone (only on your laptop), "off"."""
    if demo_code():
        return "code"
    return "off" if os.environ.get("VERCEL") else "open"


def delete_user_data(session: Session, user: User) -> None:
    """Remove a user and everything they own. Children first: transactions point at
    imports, categories and accounts, so they go before those. The caller commits."""
    for model in (Transaction, StatementImport, Budget, CategoryRule, Category, Account, LoginSession):
        session.exec(delete(model).where(model.user_id == user.id))
    session.delete(user)


def remove_old_demos(session: Session) -> int:
    """Delete demos older than DEMO_DAYS. Runs whenever a new demo starts."""
    cutoff = utc_now() - datetime.timedelta(days=DEMO_DAYS)
    old = [u for u in session.exec(select(User).where(User.is_demo)).all() if as_utc(u.created_at) < cutoff]
    for user in old:
        delete_user_data(session, user)
    session.commit()
    return len(old)


def count_demos(session: Session) -> int:
    return len(session.exec(select(User.id).where(User.is_demo)).all())


def months_to_fill(today: datetime.date) -> list[tuple[int, int]]:
    """Last month and this month."""
    last = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
    return [last, (today.year, today.month)]


def create_demo(session: Session, today: datetime.date | None = None) -> User:
    """A new demo user with its made-up data. The caller starts the session."""
    from routers.rules import add_suggested_set  # here, not at the top: routers import this module

    today = today or datetime.date.today()
    user = User(username=f"demo-{secrets.token_hex(3)}", password_hash="", is_demo=True)
    session.add(user)
    session.flush()  # gives the user an id for everything below

    chequing = Account(user_id=user.id, nickname="NCB Chequing", bank_name="NCB",
                       account_type=AccountType.chequing, last_four="0042")
    savings = Account(user_id=user.id, nickname="NCB Savings", bank_name="NCB",
                      account_type=AccountType.savings, last_four="9988")
    session.add_all([chequing, savings])
    add_suggested_set(session, user)
    session.flush()
    category = {c.name: c.id for c in session.exec(select(Category).where(Category.user_id == user.id)).all()}

    # Budgets for the months below, and for the sample statement's month.
    for year, month in {*months_to_fill(today), SAMPLE_MONTH}:
        for name, amount in BUDGETS.items():
            session.add(Budget(user_id=user.id, category_id=category[name], year=year, month=month, amount=amount))

    for year, month in months_to_fill(today):
        if (year, month) == SAMPLE_MONTH:
            continue  # that month is filled by importing the sample statement
        for day, description, amount, tx_type, category_name in EVERYDAY:
            date = datetime.date(year, month, day)
            if date > today:
                continue  # nothing from the future
            session.add(Transaction(
                user_id=user.id, amount=amount, date=date, description=description, type=tx_type,
                category_id=category.get(category_name), account_id=chequing.id,
            ))

    # Logged by hand, and also on the sample statement: importing it shows "Already logged".
    session.add(Transaction(
        user_id=user.id, amount=1580, date=datetime.date(2026, 9, 21), description="Lunch at Juici",
        type=TransactionType.expense, category_id=category["Food & Dining"],
    ))
    session.commit()
    session.refresh(user)
    return user
