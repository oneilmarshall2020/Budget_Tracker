import datetime

from sqlmodel import Field, SQLModel
from pydantic import field_validator

class Category(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str

class CategoryCreate(SQLModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Category name cannot be blank")
        return cleaned

class Budget(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    category_id: int = Field(foreign_key="category.id")
    year: int
    month: int
    amount: float

class BudgetCreate(SQLModel):
    category_id: int
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    amount: float = Field(gt=0)

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

class ExpenseCreate(SQLModel):
    amount: float = Field(gt=0)
    date: datetime.date
    description: str
    category_id: int | None = None

    @field_validator("description")
    @classmethod
    def description_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Description cannot be blank")
        return cleaned