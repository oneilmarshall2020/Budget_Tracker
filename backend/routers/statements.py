from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sqlalchemy import or_
from sqlmodel import select

from database import SessionDep
from helpers import category_fits, get_account_or_404, resolve_category
from models import Category, CategoryKind, ImportConfirm, Transaction, TransactionSource
from parsers import BANK_FEES, classify, clean_description, merchant_key, parse_statement

router = APIRouter(tags=["Statement import"])

MATCH_WINDOW_DAYS = 3  # a manual entry within 3 days of a statement row may be the same purchase


def same_money(a: float, b: float) -> bool:
    return abs(a - b) < 0.005


@router.post("/statement/preview")
def preview_statement(
    session: SessionDep,
    account_id: Annotated[int, Form()],
    file: Annotated[UploadFile, File()],
    password: Annotated[str | None, Form()] = None,
):
    """Read a statement and return rows for review."""
    account = get_account_or_404(session, account_id)
    try:
        parsed, problems = parse_statement(
            file.file.read(), file.filename or "", account.bank_name, password
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Fee rows get filed under "Bank Fees", so make sure that category exists.
    categories = session.exec(select(Category)).all()
    by_name = {c.name.lower(): c for c in categories}
    if BANK_FEES.lower() not in by_name and any(
        classify(r.description, r.amount)[1] == BANK_FEES for r in parsed
    ):
        fees = Category(name=BANK_FEES, kind=CategoryKind.expense)
        session.add(fees)
        session.commit()
        session.refresh(fees)
        by_name[fees.name.lower()] = fees
    by_id = {c.id: c for c in by_name.values()}

    # Learn from history: merchant -> category of its most recent categorized transaction.
    learned = {}
    for t in session.exec(
        select(Transaction).where(Transaction.category_id.is_not(None)).order_by(Transaction.date)
    ).all():
        learned[merchant_key(t.description)] = t.category_id

    # Existing transactions around these dates, for duplicate and match checks.
    existing = []
    if parsed:
        low = min(r.date for r in parsed) - timedelta(days=MATCH_WINDOW_DAYS)
        high = max(r.date for r in parsed) + timedelta(days=MATCH_WINDOW_DAYS)
        existing = session.exec(
            select(Transaction).where(
                Transaction.date >= low,
                Transaction.date <= high,
                or_(Transaction.account_id == account_id, Transaction.account_id.is_(None)),
            )
        ).all()
    used = set()  # each existing transaction can explain at most one statement row

    rows = []
    for index, row in enumerate(parsed):
        tx_type, suggested, flag = classify(row.description, row.amount)
        if row.type is not None:  # a CSV "type" column wins over the guess
            tx_type = row.type
        description = clean_description(row.description)
        amount = round(abs(row.amount), 2)

        category_id = None
        name = row.category_name or suggested
        if name and name.lower() in by_name:
            category_id = by_name[name.lower()].id
        if category_id is None:
            category_id = learned.get(merchant_key(description))
        if category_id is not None and not category_fits(by_id.get(category_id), tx_type):
            category_id = None

        include, note = True, None

        duplicate = next(
            (
                t for t in existing
                if t.id not in used
                and t.source == TransactionSource.statement
                and t.account_id == account_id
                and t.date == row.date
                and same_money(t.amount, amount)
                and t.description == description
            ),
            None,
        )
        if duplicate:
            used.add(duplicate.id)
            flag, include, note = "duplicate", False, "Already imported"
        else:
            # Something you logged by hand that is probably this same transaction?
            match = next(
                (
                    t for t in existing
                    if t.id not in used
                    and t.source == TransactionSource.manual
                    and t.type == tx_type
                    and same_money(t.amount, amount)
                    and abs((t.date - row.date).days) <= MATCH_WINDOW_DAYS
                ),
                None,
            )
            if match:
                used.add(match.id)
                flag, include = "match", False
                note = f"You already logged '{match.description}' on {match.date.isoformat()}"
            elif flag == "review":
                note = "A payment, or a transfer to your own account? Change the type if it's a transfer."

        rows.append({
            "key": index,
            "date": row.date.isoformat(),
            "description": description,
            "amount": amount,
            "type": tx_type.value,
            "category_id": category_id,
            "flag": flag,
            "note": note,
            "include": include,
        })

    return {"account_id": account_id, "rows": rows, "problems": problems}


@router.post("/statement/confirm")
def confirm_import(payload: ImportConfirm, session: SessionDep):
    """Save the rows you kept in the preview."""
    get_account_or_404(session, payload.account_id)
    if not payload.rows:
        return {"created": [], "skipped": 0}

    # Guard against saving the same statement twice (double click, re-import).
    low = min(r.date for r in payload.rows)
    high = max(r.date for r in payload.rows)
    existing = session.exec(
        select(Transaction).where(
            Transaction.account_id == payload.account_id,
            Transaction.source == TransactionSource.statement,
            Transaction.date >= low,
            Transaction.date <= high,
        )
    ).all()
    used = set()

    created, skipped = [], 0
    for row in payload.rows:
        category_id = resolve_category(session, row.category_id, row.type)
        duplicate = next(
            (
                t for t in existing
                if t.id not in used
                and t.date == row.date
                and same_money(t.amount, row.amount)
                and t.description == row.description
            ),
            None,
        )
        if duplicate:
            used.add(duplicate.id)
            skipped += 1
            continue

        transaction = Transaction(
            amount=round(row.amount, 2),
            date=row.date,
            description=row.description,
            type=row.type,
            source=TransactionSource.statement,
            category_id=category_id,
            account_id=payload.account_id,
        )
        session.add(transaction)
        created.append(transaction)

    session.commit()
    for transaction in created:
        session.refresh(transaction)
    return {"created": created, "skipped": skipped}
