from collections import defaultdict

from fastapi import APIRouter, HTTPException
from sqlalchemy import case, extract, func
from sqlmodel import select

from database import SessionDep
from helpers import month_bounds, year_bounds
from models import Budget, Category, CategoryKind, Transaction, TransactionType

router = APIRouter(tags=["Reports"])

# Spending = expenses minus refunds. CASE flips refunds negative inside the SUM.
SPENT = func.sum(
    case(
        (Transaction.type == TransactionType.refund, -Transaction.amount),
        else_=Transaction.amount,
    )
)
SPENDING_TYPES = (TransactionType.expense, TransactionType.refund)
UNCATEGORIZED = "Uncategorized"


def money(value) -> float:
    return round(value or 0, 2)


def category_names(session) -> dict[int, str]:
    return {c.id: c.name for c in session.exec(select(Category)).all()}


def ranked(totals: dict, names: dict) -> list[dict]:
    """[{category, amount}] sorted most to least, skipping zeros."""
    rows = [
        {"category": names.get(cid, UNCATEGORIZED) if cid is not None else UNCATEGORIZED,
         "amount": money(total)}
        for cid, total in totals.items()
        if money(total) != 0
    ]
    return sorted(rows, key=lambda row: row["amount"], reverse=True)


@router.get("/summary/{year}/{month}")
def monthly_summary(year: int, month: int, session: SessionDep):
    if not 1 <= month <= 12:
        raise HTTPException(status_code=400, detail="Month must be between 1 and 12")
    start, end = month_bounds(year, month)
    in_month = (Transaction.date >= start, Transaction.date < end)

    # One GROUP BY query instead of one query per category.
    spent_rows = session.exec(
        select(Transaction.category_id, SPENT)
        .where(Transaction.type.in_(SPENDING_TYPES), *in_month)
        .group_by(Transaction.category_id)
    ).all()
    spent = {category_id: total or 0 for category_id, total in spent_rows}

    income_rows = session.exec(
        select(Transaction.category_id, func.sum(Transaction.amount))
        .where(Transaction.type == TransactionType.income, *in_month)
        .group_by(Transaction.category_id)
    ).all()
    income_by_category = {category_id: total or 0 for category_id, total in income_rows}

    budgets = {
        b.category_id: b.amount
        for b in session.exec(select(Budget).where(Budget.year == year, Budget.month == month)).all()
    }

    # Budget vs actual for every expense category.
    lines = []
    for category in session.exec(select(Category).order_by(Category.name)).all():
        if category.kind != CategoryKind.expense:
            continue
        budgeted = money(budgets.get(category.id))
        actual = money(spent.get(category.id))
        if budgeted == 0 and actual == 0:
            continue  # nothing to show for this category this month
        lines.append({
            "category_id": category.id,
            "category": category.name,
            "budgeted": budgeted,
            "actual": actual,
            "remaining": money(budgeted - actual),
        })

    names = category_names(session)
    income = money(sum(income_by_category.values()))
    spending = money(sum(spent.values()))
    total_budgeted = money(sum(line["budgeted"] for line in lines))
    total_actual = money(sum(line["actual"] for line in lines if line["budgeted"] > 0))

    return {
        "year": year,
        "month": month,
        "income": income,
        "spending": spending,
        "net": money(income - spending),
        "categories": lines,
        "total_budgeted": total_budgeted,
        "total_actual": total_actual,  # spending in budgeted categories only
        "total_remaining": money(total_budgeted - total_actual),
        "spending_by_category": ranked(spent, names),
        "income_by_category": ranked(income_by_category, names),
    }


@router.get("/summary/{year}")
def yearly_summary(year: int, session: SessionDep):
    start, end = year_bounds(year)
    in_year = (Transaction.date >= start, Transaction.date < end)
    month_of = extract("month", Transaction.date)  # works on SQLite and Postgres

    income_rows = session.exec(
        select(month_of, func.sum(Transaction.amount))
        .where(Transaction.type == TransactionType.income, *in_year)
        .group_by(month_of)
    ).all()
    income_by_month = {int(m): total or 0 for m, total in income_rows}

    spent_rows = session.exec(
        select(Transaction.category_id, month_of, SPENT)
        .where(Transaction.type.in_(SPENDING_TYPES), *in_year)
        .group_by(Transaction.category_id, month_of)
    ).all()
    spent_by_month = defaultdict(float)
    spent_by_category = defaultdict(float)
    spent_by_category_month = {}
    for category_id, m, total in spent_rows:
        spent_by_month[int(m)] += total or 0
        spent_by_category[category_id] += total or 0
        spent_by_category_month[(category_id, int(m))] = total or 0

    months = []
    for m in range(1, 13):
        month_income = money(income_by_month.get(m))
        month_spent = money(spent_by_month.get(m))
        months.append({
            "month": m,
            "income": month_income,
            "spending": month_spent,
            "net": money(month_income - month_spent),
        })

    # Habits: in how many budgeted months did each category go over?
    names = category_names(session)
    budgets = session.exec(select(Budget).where(Budget.year == year)).all()
    months_budgeted = defaultdict(int)
    months_over = defaultdict(int)
    for budget in budgets:
        months_budgeted[budget.category_id] += 1
        actual = spent_by_category_month.get((budget.category_id, budget.month), 0)
        if money(actual) > money(budget.amount):
            months_over[budget.category_id] += 1
    over_budget = sorted(
        (
            {
                "category": names.get(category_id, UNCATEGORIZED),
                "months_over": count,
                "months_budgeted": months_budgeted[category_id],
            }
            for category_id, count in months_over.items()
        ),
        key=lambda row: row["months_over"],
        reverse=True,
    )

    income = money(sum(income_by_month.values()))
    spending = money(sum(spent_by_month.values()))
    net = money(income - spending)
    return {
        "year": year,
        "income": income,
        "spending": spending,
        "net": net,
        "savings_rate": round(net / income * 100, 1) if income > 0 else None,
        "total_budgeted": money(sum(b.amount for b in budgets)),
        "months": months,
        "spending_by_category": ranked(spent_by_category, names),
        "over_budget": over_budget,
    }
