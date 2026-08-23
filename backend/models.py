import datetime

from sqlmodel import Field, SQLModel


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