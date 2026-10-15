from fastapi import APIRouter, HTTPException
from sqlmodel import select

from database import SessionDep
from helpers import check_account, month_bounds, resolve_category, year_bounds
from models import Transaction, TransactionCreate, TransactionUpdate

router = APIRouter(tags=["Transactions"])

# Fields a transaction can never be without (category and account can be cleared).
REQUIRED_FIELDS = ("amount", "date", "description", "type")

def get_transaction_or_404(session, transaction_id: int) -> Transaction:
    transaction = session.get(Transaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@router.post("/transaction/")
def create_transaction(transaction_in: TransactionCreate, session: SessionDep) -> Transaction:
    data = transaction_in.model_dump()
    check_account(session, data["account_id"])
    data["category_id"] = resolve_category(session, data["category_id"], transaction_in.type)
    transaction = Transaction(**data)
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    return transaction


@router.get("/transaction/")
def read_transactions(
    session: SessionDep,
    year: int | None = None,
    month: int | None = None,
    account_id: int | None = None,
) -> list[Transaction]:
    """List transactions, optionally filtered: /transaction/?year=2026&month=9"""
    statement = select(Transaction)
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


@router.get("/transaction/{transaction_id}")
def read_transaction(transaction_id: int, session: SessionDep) -> Transaction:
    return get_transaction_or_404(session, transaction_id)


@router.patch("/transaction/{transaction_id}")
def update_transaction(
    transaction_id: int, transaction_update: TransactionUpdate, session: SessionDep
) -> Transaction:
    transaction = get_transaction_or_404(session, transaction_id)
    update_data = transaction_update.model_dump(exclude_unset=True)
    for field in REQUIRED_FIELDS:
        if field in update_data and update_data[field] is None:
            update_data.pop(field)

    if "account_id" in update_data:
        check_account(session, update_data["account_id"])

    new_type = update_data.get("type", transaction.type)
    new_category = update_data.get("category_id", transaction.category_id)
    update_data["category_id"] = resolve_category(session, new_category, new_type)

    transaction.sqlmodel_update(update_data)
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    return transaction


@router.delete("/transaction/{transaction_id}")
def delete_transaction(transaction_id: int, session: SessionDep):
    transaction = get_transaction_or_404(session, transaction_id)
    session.delete(transaction)
    session.commit()
    return {"ok": True}
