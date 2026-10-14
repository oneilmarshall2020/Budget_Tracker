from fastapi import APIRouter, HTTPException
from sqlmodel import select

from database import SessionDep
from models import Budget, BudgetCreate

router = APIRouter()

@router.post("/budget/")
def create_budget(budget_in: BudgetCreate, session: SessionDep) -> Budget:
    budget = Budget(**budget_in.model_dump())
    session.add(budget)
    session.commit()
    session.refresh(budget)
    return budget


@router.get("/budget/")
def read_budgets(session: SessionDep) -> list[Budget]:
    return session.exec(select(Budget)).all()