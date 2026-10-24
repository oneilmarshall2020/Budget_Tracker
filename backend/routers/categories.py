from fastapi import APIRouter, HTTPException
from sqlmodel import select

from auth import CurrentUser
from database import SessionDep
from helpers import get_owned_or_404
from models import Budget, Category, CategoryCreate, CategoryRule, CategoryUpdate, Transaction

router = APIRouter(tags=["Categories"])


def get_category_or_404(session, category_id: int, user) -> Category:
    return get_owned_or_404(session, Category, category_id, user, "Category")


@router.post("/categories/")
def create_category(category_in: CategoryCreate, session: SessionDep, user: CurrentUser) -> Category:
    category = Category(**category_in.model_dump(), user_id=user.id)
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


@router.get("/categories/")
def read_categories(session: SessionDep, user: CurrentUser) -> list[Category]:
    return session.exec(
        select(Category).where(Category.user_id == user.id).order_by(Category.name)
    ).all()


@router.patch("/categories/{category_id}")
def update_category(
    category_id: int, category_update: CategoryUpdate, session: SessionDep, user: CurrentUser
) -> Category:
    category = get_category_or_404(session, category_id, user)
    update_data = category_update.model_dump(exclude_unset=True, exclude_none=True)

    # Switching income <-> expense would leave existing transactions and budgets mismatched.
    if "kind" in update_data and update_data["kind"] != category.kind:
        used_by_transaction = session.exec(
            select(Transaction.id).where(Transaction.category_id == category_id)
        ).first()
        used_by_budget = session.exec(
            select(Budget.id).where(Budget.category_id == category_id)
        ).first()
        if used_by_transaction is not None or used_by_budget is not None:
            raise HTTPException(
                status_code=400,
                detail="Can't change the kind of a category that already has transactions or budgets",
            )

    category.sqlmodel_update(update_data)
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


@router.delete("/categories/{category_id}")
def delete_category(category_id: int, session: SessionDep, user: CurrentUser):
    category = get_category_or_404(session, category_id, user)

    # A budget for a category that no longer exists is meaningless: delete it.
    budgets = session.exec(select(Budget).where(Budget.category_id == category_id)).all()
    for budget in budgets:
        session.delete(budget)

    # Its keywords point nowhere once it's gone: delete them too.
    rules = session.exec(select(CategoryRule).where(CategoryRule.category_id == category_id)).all()
    for rule in rules:
        session.delete(rule)

    # Transactions are your real money history: keep them, just uncategorize them.
    transactions = session.exec(
        select(Transaction).where(Transaction.category_id == category_id)
    ).all()
    for transaction in transactions:
        transaction.category_id = None
        session.add(transaction)

    session.flush()  # push the child changes to the DB before deleting the parent
    session.delete(category)
    session.commit()
    return {"ok": True}
