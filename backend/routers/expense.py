from fastapi import APIRouter, HTTPException
from sqlmodel import select

from database import SessionDep
from models import Expense, ExpenseUpdate, ExpenseCreate

router = APIRouter()

@router.post("/expense/")
def create_expense(expense_in: ExpenseCreate, session: SessionDep) -> Expense:
    expense = Expense(**expense_in.model_dump())
    session.add(expense)
    session.commit()
    session.refresh(expense)
    return expense


@router.get("/expense/")
def read_expenses(session: SessionDep) -> list[Expense]:
    expenses = session.exec(select(Expense)).all()
    return expenses


@router.get("/expense/{expense_id}")
def read_expense(expense_id: int, session: SessionDep) -> Expense:
    expense = session.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense


@router.patch("/expense/{expense_id}")
def update_expense(
    expense_id: int, expense_update: ExpenseUpdate, session: SessionDep) -> Expense:
    expense = session.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    update_data = expense_update.model_dump(exclude_unset=True)
    expense.sqlmodel_update(update_data)
    session.add(expense)
    session.commit()
    session.refresh(expense)
    return expense


@router.delete("/expense/{expense_id}")
def delete_expense(expense_id: int, session: SessionDep):
    expense = session.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    session.delete(expense)
    session.commit()
    return {"ok": True}