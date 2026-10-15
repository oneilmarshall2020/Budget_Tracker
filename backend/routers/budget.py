from fastapi import APIRouter, HTTPException
from sqlmodel import select

from database import SessionDep
from models import Budget, BudgetCreate, BudgetUpdate, Category, CategoryKind

router = APIRouter(tags=["Budgets"])


def check_budget_category(session, category_id: int) -> None:
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    if category.kind != CategoryKind.expense:
        raise HTTPException(status_code=400, detail="Budgets are only for expense categories")


def check_one_per_month(session, category_id: int, year: int, month: int, ignore_id=None) -> None:
    """A category gets at most one budget per month."""
    existing = session.exec(
        select(Budget).where(
            Budget.category_id == category_id,
            Budget.year == year,
            Budget.month == month,
        )
    ).first()
    if existing and existing.id != ignore_id:
        raise HTTPException(
            status_code=400,
            detail="That category already has a budget for this month. Edit it instead.",
        )


@router.post("/budget/")
def create_budget(budget_in: BudgetCreate, session: SessionDep) -> Budget:
    check_budget_category(session, budget_in.category_id)
    check_one_per_month(session, budget_in.category_id, budget_in.year, budget_in.month)
    budget = Budget(**budget_in.model_dump())
    session.add(budget)
    session.commit()
    session.refresh(budget)
    return budget


@router.get("/budget/")
def read_budgets(
    session: SessionDep, year: int | None = None, month: int | None = None
) -> list[Budget]:
    statement = select(Budget)
    if year is not None:
        statement = statement.where(Budget.year == year)
    if month is not None:
        statement = statement.where(Budget.month == month)
    return session.exec(statement.order_by(Budget.year, Budget.month)).all()


@router.patch("/budget/{budget_id}")
def update_budget(budget_id: int, budget_update: BudgetUpdate, session: SessionDep) -> Budget:
    budget = session.get(Budget, budget_id)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    update_data = budget_update.model_dump(exclude_unset=True, exclude_none=True)
    category_id = update_data.get("category_id", budget.category_id)
    year = update_data.get("year", budget.year)
    month = update_data.get("month", budget.month)
    check_budget_category(session, category_id)
    check_one_per_month(session, category_id, year, month, ignore_id=budget.id)

    budget.sqlmodel_update(update_data)
    session.add(budget)
    session.commit()
    session.refresh(budget)
    return budget


@router.delete("/budget/{budget_id}")
def delete_budget(budget_id: int, session: SessionDep):
    budget = session.get(Budget, budget_id)
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")
    session.delete(budget)
    session.commit()
    return {"ok": True}
