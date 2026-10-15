import datetime
from enum import Enum

from pydantic import field_validator
from sqlmodel import Field, SQLModel


# --- Helper Functions ---
def clean_text(value: str | None, label: str) -> str | None:
    """Strip whitespace and reject blanks. None passes through (partial updates)."""
    if value is None:
        return value
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{label} cannot be blank")
    return cleaned

def clean_last_four(value: str | None) -> str | None:
    if value is None:
        return value
    cleaned = value.strip()
    if len(cleaned) != 4 or not cleaned.isdigit():
        raise ValueError("Last four must be exactly 4 digits")
    return cleaned


# --- Enums ---
class TransactionType(str, Enum):
    income = "income"
    expense = "expense"
    transfer = "transfer"
    refund = "refund"

class TransactionSource(str, Enum):
    manual = "manual"       
    statement = "statement"  

class CategoryKind(str, Enum):
    income = "income"
    expense = "expense"

class AccountType(str, Enum):
    savings = "savings"
    chequing = "chequing"
    credit_card = "credit_card"


# --- Accounts ---
class Account(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    nickname: str
    bank_name: str
    account_type: AccountType
    last_four: str
    currency: str = "JMD"

class AccountCreate(SQLModel):
    nickname: str
    bank_name: str
    account_type: AccountType
    last_four: str
    currency: str = "JMD"

    @field_validator("nickname")
    @classmethod
    def check_nickname(cls, value):
        return clean_text(value, "Nickname")

    @field_validator("bank_name")
    @classmethod
    def check_bank_name(cls, value):
        return clean_text(value, "Bank name")

    @field_validator("last_four")
    @classmethod
    def check_last_four(cls, value):
        return clean_last_four(value)

class AccountUpdate(SQLModel):
    nickname: str | None = None
    bank_name: str | None = None
    account_type: AccountType | None = None
    last_four: str | None = None
    currency: str | None = None

    @field_validator("nickname")
    @classmethod
    def check_nickname(cls, value):
        return clean_text(value, "Nickname")

    @field_validator("bank_name")
    @classmethod
    def check_bank_name(cls, value):
        return clean_text(value, "Bank name")

    @field_validator("last_four")
    @classmethod
    def check_last_four(cls, value):
        return clean_last_four(value)


# --- Categories ---
class Category(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    kind: CategoryKind = CategoryKind.expense

class CategoryCreate(SQLModel):
    name: str
    kind: CategoryKind = CategoryKind.expense

    @field_validator("name")
    @classmethod
    def check_name(cls, value):
        return clean_text(value, "Category name")

class CategoryUpdate(SQLModel):
    name: str | None = None
    kind: CategoryKind | None = None

    @field_validator("name")
    @classmethod
    def check_name(cls, value):
        return clean_text(value, "Category name")


# --- Budgets ---
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

class BudgetUpdate(SQLModel):
    category_id: int | None = None
    year: int | None = Field(default=None, ge=2000, le=2100)
    month: int | None = Field(default=None, ge=1, le=12)
    amount: float | None = Field(default=None, gt=0)


# --- Transactions ---
class Transaction(SQLModel, table=True):
    __tablename__ = "transactions"

    id: int | None = Field(default=None, primary_key=True)
    amount: float  
    date: datetime.date
    description: str
    type: TransactionType
    source: TransactionSource = TransactionSource.manual
    category_id: int | None = Field(default=None, foreign_key="category.id")
    account_id: int | None = Field(default=None, foreign_key="account.id")

class TransactionCreate(SQLModel):
    amount: float = Field(gt=0)
    date: datetime.date
    description: str
    type: TransactionType = TransactionType.expense
    category_id: int | None = None
    account_id: int | None = None

    @field_validator("description")
    @classmethod
    def check_description(cls, value):
        return clean_text(value, "Description")

class TransactionUpdate(SQLModel):
    amount: float | None = Field(default=None, gt=0)
    date: datetime.date | None = None
    description: str | None = None
    type: TransactionType | None = None
    category_id: int | None = None
    account_id: int | None = None

    @field_validator("description")
    @classmethod
    def check_description(cls, value):
        return clean_text(value, "Description")


# --- Statement Import ---
class ImportRow(SQLModel):
    date: datetime.date
    description: str
    amount: float = Field(gt=0)
    type: TransactionType
    category_id: int | None = None

    @field_validator("description")
    @classmethod
    def check_description(cls, value):
        return clean_text(value, "Description")


class ImportConfirm(SQLModel):
    account_id: int
    rows: list[ImportRow]
