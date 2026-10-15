from fastapi import APIRouter, HTTPException
from sqlmodel import select

from database import SessionDep
from models import Budget, Category, CategoryCreate, CategoryUpdate, Transaction

router = APIRouter(tags=["Categories"])


def get_category_or_404(session, category_id: int) -> Category:
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@router.post("/categories/")
def create_category(category_in: CategoryCreate, session: SessionDep) -> Category:
    category = Category(**category_in.model_dump())
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


@router.get("/categories/")
def read_categories(session: SessionDep) -> list[Category]:
    return session.exec(select(Category).order_by(Category.name)).all()


@router.patch("/categories/{category_id}")
def update_category(
    category_id: int, category_update: CategoryUpdate, session: SessionDep) -> Category:
    category = get_category_or_404(session, category_id)
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
def delete_category(category_id: int, session: SessionDep):
    category = get_category_or_404(session, category_id)

    # A budget for a category that no longer exists is meaningless: delete it.
    budgets = session.exec(select(Budget).where(Budget.category_id == category_id)).all()
    for budget in budgets:
        session.delete(budget)

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
