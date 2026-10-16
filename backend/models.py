import datetime
from enum import Enum

from pydantic import field_validator
from sqlmodel import Field, SQLModel


# ---------------------------------------------------------------- helpers
def clean_text(value: str | None, label: str) -> str | None:
    """Strip whitespace and reject blanks. None passes through (partial updates)."""
    if value is None:
        return value
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{label} cannot be blank")
    return cleaned


def clean_keyword(value: str | None) -> str | None:
    """Keywords are stored uppercase with single spaces: ' juici  patties' -> 'JUICI PATTIES'."""
    if value is None:
        return value
    cleaned = " ".join(value.upper().split())
    if len(cleaned) < 2:
        raise ValueError("Keyword must be at least 2 characters")
    return cleaned


def clean_last_four(value: str | None) -> str | None:
    if value is None:
        return value
    cleaned = value.strip()
    if len(cleaned) != 4 or not cleaned.isdigit():
        raise ValueError("Last four must be exactly 4 digits")
    return cleaned


# ---------------------------------------------------------------- enums
class TransactionType(str, Enum):
    income = "income"
    expense = "expense"
    transfer = "transfer"
    refund = "refund"


class TransactionSource(str, Enum):
    manual = "manual"        # typed in by you
    statement = "statement"  # imported from a bank statement


class CategoryKind(str, Enum):
    income = "income"
    expense = "expense"


class AccountType(str, Enum):
    savings = "savings"
    chequing = "chequing"
    credit_card = "credit_card"


# ---------------------------------------------------------------- accounts
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


# ---------------------------------------------------------------- categories
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


# ---------------------------------------------------------------- keyword rules
class CategoryRule(SQLModel, table=True):
    """keyword -> category. Descriptions containing the keyword get that category."""

    __tablename__ = "category_rule"

    id: int | None = Field(default=None, primary_key=True)
    keyword: str = Field(unique=True)  # one category per keyword
    category_id: int = Field(foreign_key="category.id")


class RuleCreate(SQLModel):
    keyword: str
    category_id: int

    @field_validator("keyword")
    @classmethod
    def check_keyword(cls, value):
        return clean_keyword(value)


class RuleApply(SQLModel):
    """Give every transaction matching this keyword this category."""

    keyword: str
    category_id: int
    exclude_id: int | None = None  # the one you just edited

    @field_validator("keyword")
    @classmethod
    def check_keyword(cls, value):
        return clean_keyword(value)


class RuleUpdate(SQLModel):
    keyword: str | None = None
    category_id: int | None = None

    @field_validator("keyword")
    @classmethod
    def check_keyword(cls, value):
        return clean_keyword(value)


# ---------------------------------------------------------------- budgets
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


# ---------------------------------------------------------------- statement imports
class StatementImport(SQLModel, table=True):
    """One confirmed statement import (a batch), so the whole thing can be undone."""

    __tablename__ = "statement_import"

    id: int | None = Field(default=None, primary_key=True)
    account_id: int | None = Field(default=None, foreign_key="account.id")
    file_name: str
    # Stored in UTC (the universal clock); the browser shows it in your local time.
    imported_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    first_date: datetime.date
    last_date: datetime.date
    row_count: int


# ---------------------------------------------------------------- transactions
class Transaction(SQLModel, table=True):
    # "transaction" is a reserved word in SQL, so the table gets a safer name.
    __tablename__ = "transactions"

    id: int | None = Field(default=None, primary_key=True)
    amount: float  # always positive; `type` says which way the money moved
    date: datetime.date
    description: str
    type: TransactionType
    source: TransactionSource = TransactionSource.manual
    category_id: int | None = Field(default=None, foreign_key="category.id")
    account_id: int | None = Field(default=None, foreign_key="account.id")
    # Which statement import created this row (None = you typed it in).
    import_id: int | None = Field(default=None, foreign_key="statement_import.id")


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


# ---------------------------------------------------------------- statement import
class ImportRow(SQLModel):
    """One reviewed row from the import preview, sent back to be saved."""

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
    file_name: str = "statement"
    rows: list[ImportRow]
    # Entries you logged by hand that the review matched: link them to this account.
    matched_ids: list[int] = []
    # The other side of transfers between your accounts: mark those as transfers too.
    transfer_pair_ids: list[int] = []
