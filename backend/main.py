from contextlib import asynccontextmanager
import datetime
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import event, func
from sqlmodel import Field, Session, SQLModel, create_engine, select


# --- Database models ---
class Category(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str


class Budget(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    category_id: int = Field(foreign_key="category.id")
    year: int
    month: int
    amount: float


class Expense(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    amount: float
    date: datetime.date
    description: str
    category_id: int | None = Field(default=None, foreign_key="category.id")


class ExpenseUpdate(SQLModel):
    amount: float | None = None
    date: datetime.date | None = None
    description: str | None = None
    category_id: int | None = None


# --- Database setup ---
sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
engine = create_engine(sqlite_url, echo=True)


@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


# --- App setup ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.get("/")
def read_root():
    return {"message": "Yeah I Built This Shxt Gng"}


# --- Category endpoints ---
@app.post("/categories/")
def create_category(category: Category, session: SessionDep) -> Category:
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


@app.get("/categories/") 
def read_categories(session: SessionDep) -> list[Category]:
    categories = session.exec(select(Category)).all()
    return categories


# --- Expense endpoints ---
@app.post("/expenses/")
def create_expense(expense: Expense, session: SessionDep) -> Expense:
    session.add(expense)
    session.commit()
    session.refresh(expense)
    return expense


@app.get("/expenses/")
def read_expenses(session: SessionDep) -> list[Expense]:
    expenses = session.exec(select(Expense)).all()
    return expenses


@app.get("/expenses/{expense_id}")
def read_expense(expense_id: int, session: SessionDep) -> Expense:
    expense = session.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense


@app.patch("/expenses/{expense_id}")
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


@app.delete("/expenses/{expense_id}")
def delete_expense(expense_id: int, session: SessionDep):
    expense = session.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    session.delete(expense)
    session.commit()
    return {"ok": True}


@app.post("/budgets/")
def create_budget(budget: Budget, session: SessionDep) -> Budget:
    session.add(budget)
    session.commit()
    session.refresh(budget)
    return budget


@app.get("/budgets/")
def read_budgets(session: SessionDep) -> list[Budget]:
    return session.exec(select(Budget)).all()


@app.get("/summary/{category_id}/{year}/{month}")
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


@app.get("/summary/{year}/{month}")
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


@app.get("/summary/{year}")
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