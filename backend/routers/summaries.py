from fastapi import APIRouter, HTTPException
from sqlmodel import select
from sqlalchemy import func

import datetime

from database import SessionDep
from models import Category, Budget, Expense

router = APIRouter()

@router.get("/summary/{category_id}/{year}/{month}")
def category_summary(category_id: int, year: int, month: int, session: SessionDep):
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    # Budgeted: the target you declared, read straight from the Budget table
    budget = session.exec(
        select(Budget).where(
            Budget.category_id == category_id,
            Budget.year == year,
            Budget.month == month
        )
    ).first()
    budgeted = budget.amount if budget else 0

    # Actual: sum every expense in this category during this month
    start = datetime.date(year, month, 1)
    if month == 12:
        end = datetime.date(year + 1, 1, 1)
    else:
        end = datetime.date(year, month + 1, 1)

    total = session.exec(
        select(func.sum(Expense.amount)).where(
            Expense.category_id == category_id,
            Expense.date >= start,
            Expense.date < end
        )
    ).one()
    actual = total or 0

    return {
        "category": category.name,
        "year": year,
        "month": month,
        "budgeted": budgeted,
        "actual": actual,
        "remaining": budgeted - actual
    }


def month_bounds(year: int, month: int):
    start = datetime.date(year, month, 1)
    if month == 12:
        end = datetime.date(year + 1, 1, 1)
    else:
        end = datetime.date(year, month + 1, 1)
    return start, end


@router.get("/summary/{year}/{month}")
def monthly_summary(year: int, month: int, session: SessionDep):
    categories = session.exec(select(Category)).all()
    start, end = month_bounds(year, month)

    lines = []
    total_budgeted = 0
    total_actual = 0

    for category in categories:
        budget = session.exec(
            select(Budget).where(
                Budget.category_id == category.id,
                Budget.year == year,
                Budget.month == month
            )
        ).first()
        budgeted = budget.amount if budget else 0

        total = session.exec(
            select(func.sum(Expense.amount)).where(
                Expense.category_id == category.id,
                Expense.date >= start,
                Expense.date < end
            )
        ).one()
        actual = total or 0

        lines.append({
            "category": category.name,
            "budgeted": budgeted,
            "actual": actual,
            "remaining": budgeted - actual
        })
        total_budgeted += budgeted
        total_actual += actual

    return {
        "year": year,
        "month": month,
        "categories": lines,
        "total_budgeted": total_budgeted,
        "total_actual": total_actual,
        "total_remaining": total_budgeted - total_actual
    }


@router.get("/summary/{year}")
def yearly_summary(year: int, session: SessionDep):
    year_start = datetime.date(year, 1, 1)
    year_end = datetime.date(year + 1, 1, 1)

    total_budgeted = session.exec(
        select(func.sum(Budget.amount)).where(Budget.year == year)
    ).one() or 0

    total_actual = session.exec(
        select(func.sum(Expense.amount)).where(
            Expense.date >= year_start,
            Expense.date < year_end
        )
    ).one() or 0

    return {
        "year": year,
        "total_budgeted": total_budgeted,
        "total_actual": total_actual,
        "total_remaining": total_budgeted - total_actual
    }