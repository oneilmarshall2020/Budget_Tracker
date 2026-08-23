from fastapi import APIRouter, HTTPException
from sqlmodel import select

from database import SessionDep
from models import Budget

router = APIRouter()

@router.post("/budgets/")
def create_budget(budget: Budget, session: SessionDep) -> Budget:
    session.add(budget)
    session.commit()
    session.refresh(budget)
    return budget


@router.get("/budgets/")
def read_budgets(session: SessionDep) -> list[Budget]:
    return session.exec(select(Budget)).all()