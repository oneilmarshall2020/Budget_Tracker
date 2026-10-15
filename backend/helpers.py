"""Small helpers shared by several routers."""
import datetime

from fastapi import HTTPException
from sqlmodel import Session

from models import Account, Category, CategoryKind, TransactionType


def month_bounds(year: int, month: int) -> tuple[datetime.date, datetime.date]:
    """First day of the month, and first day of the next month (exclusive end)."""
    start = datetime.date(year, month, 1)
    if month == 12:
        end = datetime.date(year + 1, 1, 1)
    else:
        end = datetime.date(year, month + 1, 1)
    return start, end


def year_bounds(year: int) -> tuple[datetime.date, datetime.date]:
    return datetime.date(year, 1, 1), datetime.date(year + 1, 1, 1)


def get_account_or_404(session: Session, account_id: int) -> Account:
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


def check_account(session: Session, account_id: int | None) -> None:
    if account_id is not None:
        get_account_or_404(session, account_id)


def category_fits(category: Category | None, tx_type: TransactionType) -> bool:
    """Income uses income categories; expenses and refunds use expense categories."""
    if category is None or tx_type == TransactionType.transfer:
        return False
    expected = CategoryKind.income if tx_type == TransactionType.income else CategoryKind.expense
    return category.kind == expected


def resolve_category(
    session: Session, category_id: int | None, tx_type: TransactionType
) -> int | None:
    """Validate a transaction's category against its type.

    Transfers never have a category, so theirs is cleared.
    """
    if category_id is None or tx_type == TransactionType.transfer:
        return None
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    if not category_fits(category, tx_type):
        raise HTTPException(
            status_code=400,
            detail=f"A {tx_type.value} can't use the {category.kind.value} category '{category.name}'",
        )
    return category_id
