import datetime

from fastapi import APIRouter
from sqlalchemy import String, cast, func, or_
from sqlmodel import select

from auth import CurrentUser
from database import SessionDep
from helpers import check_account, get_owned_or_404, month_bounds, resolve_category, year_bounds
from models import Transaction, TransactionCreate, TransactionSource, TransactionType, TransactionUpdate

router = APIRouter(tags=["Transactions"])

SIMILAR_WINDOW_DAYS = 3

# Fields a transaction can never be without (category and account can be cleared).
REQUIRED_FIELDS = ("amount", "date", "description", "type")


def get_transaction_or_404(session, transaction_id: int, user) -> Transaction:
    return get_owned_or_404(session, Transaction, transaction_id, user, "Transaction")


@router.post("/transaction/")
def create_transaction(
    transaction_in: TransactionCreate, session: SessionDep, user: CurrentUser
) -> Transaction:
    data = transaction_in.model_dump()
    check_account(session, data["account_id"], user)
    data["category_id"] = resolve_category(session, data["category_id"], transaction_in.type, user)
    transaction = Transaction(**data, user_id=user.id)
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    return transaction


@router.get("/transaction/")
def read_transactions(
    session: SessionDep,
    user: CurrentUser,
    year: int | None = None,
    month: int | None = None,
    account_id: int | None = None,
    q: str | None = None,
) -> list[Transaction]:
    """List transactions, optionally filtered.

    /transaction/?year=2026&month=9      one month
    /transaction/?q=digicel              search every month (description or amount)
    """
    statement = select(Transaction).where(Transaction.user_id == user.id)
    if q and q.strip():
        term = q.strip().lower()
        amount_term = term.replace(",", "")  # "1,580" should find 1580.0
        statement = statement.where(
            or_(
                func.lower(Transaction.description).contains(term),
                cast(Transaction.amount, String).contains(amount_term),
            )
        )
    if year is not None and month is not None:
        start, end = month_bounds(year, month)
        statement = statement.where(Transaction.date >= start, Transaction.date < end)
    elif year is not None:
        start, end = year_bounds(year)
        statement = statement.where(Transaction.date >= start, Transaction.date < end)
    if account_id is not None:
        statement = statement.where(Transaction.account_id == account_id)
    statement = statement.order_by(Transaction.date.desc(), Transaction.id.desc())
    return session.exec(statement).all()


# Declared before /transaction/{transaction_id}, or FastAPI would read "similar" as an id.
@router.get("/transaction/similar")
def similar_imported(
    session: SessionDep, user: CurrentUser, amount: float, date: datetime.date, type: TransactionType
) -> list[Transaction]:
    """Imported statement rows that look like what you're about to log by hand:
    same type, same amount, within 3 days. The app asks before adding a double."""
    window = datetime.timedelta(days=SIMILAR_WINDOW_DAYS)
    candidates = session.exec(
        select(Transaction).where(
            Transaction.user_id == user.id,
            Transaction.source == TransactionSource.statement,
            Transaction.type == type,
            Transaction.date >= date - window,
            Transaction.date <= date + window,
        )
    ).all()
    matches = [t for t in candidates if abs(t.amount - amount) < 0.005]
    return sorted(matches, key=lambda t: abs((t.date - date).days))


@router.get("/transaction/{transaction_id}")
def read_transaction(transaction_id: int, session: SessionDep, user: CurrentUser) -> Transaction:
    return get_transaction_or_404(session, transaction_id, user)


@router.patch("/transaction/{transaction_id}")
def update_transaction(
    transaction_id: int, transaction_update: TransactionUpdate, session: SessionDep, user: CurrentUser
) -> Transaction:
    transaction = get_transaction_or_404(session, transaction_id, user)
    update_data = transaction_update.model_dump(exclude_unset=True)
    for field in REQUIRED_FIELDS:
        if field in update_data and update_data[field] is None:
            update_data.pop(field)

    if "account_id" in update_data:
        check_account(session, update_data["account_id"], user)

    # Re-check the category against the (possibly new) type.
    new_type = update_data.get("type", transaction.type)
    new_category = update_data.get("category_id", transaction.category_id)
    update_data["category_id"] = resolve_category(session, new_category, new_type, user)

    transaction.sqlmodel_update(update_data)
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    return transaction


@router.delete("/transaction/{transaction_id}")
def delete_transaction(transaction_id: int, session: SessionDep, user: CurrentUser):
    transaction = get_transaction_or_404(session, transaction_id, user)
    session.delete(transaction)
    session.commit()
    return {"ok": True}
