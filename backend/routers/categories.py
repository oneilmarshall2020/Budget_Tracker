from fastapi import APIRouter, HTTPException
from sqlmodel import select

from database import SessionDep
from models import Category

router = APIRouter()


@router.post("/categories/")
def create_category(category: Category, session: SessionDep) -> Category:
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


@router.get("/categories/")
def read_categories(session: SessionDep) -> list[Category]:
    return session.exec(select(Category)).all()


@router.delete("/categories/{category_id}")
def delete_category(category_id: int, session: SessionDep):
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    session.delete(category)
    session.commit()
    return {"ok": True}