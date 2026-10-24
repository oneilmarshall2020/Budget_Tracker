from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sqlalchemy import func, or_
from sqlmodel import select

from auth import CurrentUser
from categorize import learnable, match_rule, suggest_keyword
from database import SessionDep
from helpers import category_fits, get_account_or_404, get_owned_or_404, resolve_category
from matching import (
    Draft,
    looks_like_transfer,
    looks_renamed,
    mentions_account,
    pair_closest,
    same_money,
    short_date,
)
from models import (
    Account,
    Category,
    CategoryKind,
    CategoryRule,
    ImportConfirm,
    StatementImport,
    Transaction,
    TransactionSource,
    TransactionType,
)
from parsers import BANK_FEES, classify, clean_description, merchant_key, parse_statement

router = APIRouter(tags=["Statement import"])

MATCH_WINDOW_DAYS = 3  # a manual entry within 3 days of a statement row may be the same purchase
TRANSFER_WINDOW_DAYS = 2  # both sides of a transfer between your accounts land within 2 days
REFUND_LOOKBACK_DAYS = 60  # a refund undoes a purchase from at most 60 days before


@router.post("/statement/preview")
def preview_statement(
    session: SessionDep,
    user: CurrentUser,
    account_id: Annotated[int, Form()],
    file: Annotated[UploadFile, File()],
    password: Annotated[str | None, Form()] = None,
):
    """Read a statement and return rows for review. Nothing is saved here.

    Works in passes, each one only looking at rows the earlier passes didn't explain:
      1. category for every row (CSV column, bank fee, keyword, history)
      2. already imported, exactly            -> "duplicate"
      3. already imported under a new name    -> "possible"  (pending charges)
      4. you logged it by hand                -> "match"     (closest dates first)
      5. transfer between your own accounts   -> "transfer"
      6. refunds get the category of the purchase they undo
    """
    account = get_account_or_404(session, account_id, user)
    try:
        parsed, problems = parse_statement(
            file.file.read(), file.filename or "", account.bank_name, password, account.last_four
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Fee rows get filed under "Bank Fees", so make sure that category exists.
    mine = Transaction.user_id == user.id  # every query below only looks at your rows
    categories = session.exec(select(Category).where(Category.user_id == user.id)).all()
    by_name = {c.name.lower(): c for c in categories}
    if BANK_FEES.lower() not in by_name and any(
        classify(r.description, r.amount)[1] == BANK_FEES for r in parsed
    ):
        fees = Category(name=BANK_FEES, kind=CategoryKind.expense, user_id=user.id)
        session.add(fees)
        session.commit()
        session.refresh(fees)
        by_name[fees.name.lower()] = fees
    by_id = {c.id: c for c in by_name.values()}

    rules = session.exec(select(CategoryRule).where(CategoryRule.user_id == user.id)).all()

    # Learn from history: merchant -> category of its most recent categorized transaction.
    learned = {}
    for t in session.exec(
        select(Transaction).where(mine, Transaction.category_id.is_not(None)).order_by(Transaction.date)
    ).all():
        learned[merchant_key(t.description)] = t.category_id

    # ---------------------------------------------------------------- pass 1: categories
    drafts = []
    for index, row in enumerate(parsed):
        tx_type, suggested, flag = classify(row.description, row.amount)
        if row.type is not None:  # a CSV "type" column wins over the guess
            tx_type = row.type
        description = clean_description(row.description)
        draft = Draft(
            key=index,
            date=row.date,
            description=description,
            amount=round(abs(row.amount), 2),
            money_out=row.amount < 0,
            type=tx_type,
            flag=flag,
        )

        # Category, first match wins: CSV column, bank fee, your keywords, history.
        if row.category_name and row.category_name.lower() in by_name:
            draft.category_id, draft.source = by_name[row.category_name.lower()].id, "csv"
        elif suggested and suggested.lower() in by_name:
            draft.category_id, draft.source = by_name[suggested.lower()].id, "fee"
        else:
            fitting = [r for r in rules if category_fits(by_id.get(r.category_id), tx_type)]
            rule = match_rule(description, fitting)
            if rule:
                draft.category_id, draft.source, draft.rule_keyword = rule.category_id, "rule", rule.keyword
            elif merchant_key(description) in learned:
                draft.category_id, draft.source = learned[merchant_key(description)], "history"
        if draft.category_id is not None and not category_fits(by_id.get(draft.category_id), tx_type):
            draft.category_id, draft.source, draft.rule_keyword = None, None, None

        # The keyword to remember if you categorize this row yourself (None = don't learn).
        draft.keyword = suggest_keyword(description) if learnable(description, flag) else None
        drafts.append(draft)

    if not drafts:
        return {"account_id": account_id, "file_name": file.filename or "statement", "rows": [], "problems": problems}

    low = min(d.date for d in drafts)
    high = max(d.date for d in drafts)

    # What already exists around these dates on this account (or with no account).
    nearby = session.exec(
        select(Transaction).where(
            mine,
            Transaction.date >= low - timedelta(days=MATCH_WINDOW_DAYS),
            Transaction.date <= high + timedelta(days=MATCH_WINDOW_DAYS),
            or_(Transaction.account_id == account_id, Transaction.account_id.is_(None)),
        )
    ).all()
    imported = [t for t in nearby if t.source == TransactionSource.statement and t.account_id == account_id]
    logged = [t for t in nearby if t.source == TransactionSource.manual]

    # ---------------------------------------------------------------- pass 2: exact duplicates
    batch_names = {
        b.id: b.file_name
        for b in session.exec(select(StatementImport).where(StatementImport.user_id == user.id)).all()
    }
    used = set()
    for draft in drafts:
        duplicate = next(
            (
                t for t in imported
                if t.id not in used
                and t.date == draft.date
                and same_money(t.amount, draft.amount)
                and t.description == draft.description
            ),
            None,
        )
        if duplicate:
            used.add(duplicate.id)
            draft.flag, draft.include = "duplicate", False
            draft.imported_from = batch_names.get(duplicate.import_id)
            draft.note = f"Already imported from {draft.imported_from}" if draft.imported_from else "Already imported"

    # ---------------------------------------------------------------- pass 3: renamed (pending)
    open_drafts = [d for d in drafts if not d.settled]
    renamed = pair_closest(
        open_drafts,
        [t for t in imported if t.id not in used],
        lambda d, t: same_money(t.amount, d.amount) and looks_renamed(d.description, t.description),
        MATCH_WINDOW_DAYS,
    )
    for draft in open_drafts:
        if draft.key in renamed:
            t = renamed[draft.key]
            draft.flag, draft.include = "possible", False
            draft.note = (
                f"Probably '{t.description}' from {short_date(t.date)}, already imported "
                "(pending charges often change name when they post). Tick it if it's a different purchase."
            )

    # ---------------------------------------------------------------- pass 4: logged by hand
    open_drafts = [d for d in drafts if not d.settled]
    matches = pair_closest(
        open_drafts,
        logged,
        lambda d, t: t.type == d.type and same_money(t.amount, d.amount),
        MATCH_WINDOW_DAYS,
    )
    for draft in open_drafts:
        if draft.key in matches:
            t = matches[draft.key]
            draft.flag, draft.include, draft.match_id = "match", False, t.id
            draft.note = f"You already logged '{t.description}' on {short_date(t.date)}"

    # ---------------------------------------------------------------- pass 5: own transfers
    other_accounts = {
        a.id: a
        for a in session.exec(select(Account).where(Account.user_id == user.id)).all()
        if a.id != account_id
    }
    open_drafts = [d for d in drafts if not d.settled]
    other_side = session.exec(
        select(Transaction).where(
            mine,
            Transaction.date >= low - timedelta(days=TRANSFER_WINDOW_DAYS),
            Transaction.date <= high + timedelta(days=TRANSFER_WINDOW_DAYS),
            Transaction.account_id.is_not(None),
            Transaction.account_id != account_id,
        )
    ).all()

    def opposite_directions(draft, t):
        if t.type == TransactionType.transfer:
            return True  # direction unknown once saved as a transfer: amount + timing decide
        money_in = t.type in (TransactionType.income, TransactionType.refund)
        return draft.money_out == money_in

    pairs = pair_closest(
        open_drafts,
        other_side,
        lambda d, t: same_money(t.amount, d.amount)
        and opposite_directions(d, t)
        and (looks_like_transfer(d.description) or looks_like_transfer(t.description)),
        TRANSFER_WINDOW_DAYS,
    )
    for draft in open_drafts:
        own = None
        if draft.key in pairs:
            t = pairs[draft.key]
            own = other_accounts.get(t.account_id)
            draft.pair_id = t.id
            draft.note = (
                f"Transfer between your accounts: matches '{t.description}' in "
                f"{own.nickname if own else 'another account'} on {short_date(t.date)}"
            )
        elif looks_like_transfer(draft.description):
            own = next((a for a in other_accounts.values() if mentions_account(draft.description, a.last_four)), None)
            if own:
                draft.note = f"Transfer {'to' if draft.money_out else 'from'} your {own.nickname} (ending {own.last_four})"
        if draft.pair_id or own:
            draft.type, draft.flag = TransactionType.transfer, "transfer"
            draft.category_id, draft.source, draft.rule_keyword, draft.keyword = None, None, None, None

    # ---------------------------------------------------------------- pass 6: refunds
    history = session.exec(
        select(Transaction).where(
            mine,
            Transaction.type == TransactionType.expense,
            Transaction.date >= low - timedelta(days=REFUND_LOOKBACK_DAYS),
            Transaction.date <= high,
            or_(Transaction.account_id == account_id, Transaction.account_id.is_(None)),
        )
    ).all()
    # Purchases a refund could undo: expense rows in this statement, plus your history.
    purchases = [
        {"id": f"row-{d.key}", "date": d.date, "description": d.description,
         "category_id": d.category_id, "amount": d.amount}
        for d in drafts if d.type == TransactionType.expense
    ] + [
        {"id": f"tx-{t.id}", "date": t.date, "description": t.description,
         "category_id": t.category_id, "amount": t.amount}
        for t in history
    ]
    undone = set()  # each purchase can only be undone once
    for draft in drafts:
        if draft.type != TransactionType.refund or draft.settled or draft.source == "csv":
            continue
        earlier = [
            p for p in purchases
            if p["id"] not in undone
            and p["date"] <= draft.date
            and (draft.date - p["date"]).days <= REFUND_LOOKBACK_DAYS
            and same_money(p["amount"], draft.amount)
        ]
        if not earlier:
            continue  # bought before your first import: you pick the category
        original = max(earlier, key=lambda p: p["date"])  # the most recent one
        undone.add(original["id"])
        draft.reverses = f"{original['description']} ({short_date(original['date'])})"
        if original["category_id"] is not None and category_fits(by_id.get(original["category_id"]), draft.type):
            draft.category_id, draft.source, draft.rule_keyword = original["category_id"], "reversal", None

    # ---------------------------------------------------------------- notes + output
    rows = []
    for draft in drafts:
        if draft.flag == "review" and not draft.note:
            draft.note = "A payment, or a transfer to your own account? Change the type if it's a transfer."
        rows.append({
            "key": draft.key,
            "date": draft.date.isoformat(),
            "description": draft.description,
            "amount": draft.amount,
            "type": draft.type.value,
            "category_id": draft.category_id,
            "category_source": draft.source,
            "rule_keyword": draft.rule_keyword,
            "keyword": draft.keyword,
            "flag": draft.flag,
            "note": draft.note,
            "include": draft.include,
            "match_id": draft.match_id,
            "pair_id": draft.pair_id,
            "reverses": draft.reverses,
            "imported_from": draft.imported_from,
        })

    return {
        "account_id": account_id,
        "file_name": file.filename or "statement",
        "rows": rows,
        "problems": problems,
    }


def link_and_pair(session, payload: ImportConfirm, user) -> tuple[int, int]:
    """Two follow-ups from the review, done even if no new rows are saved:
    link your hand-logged entries to this account, and mark the other side of
    transfers between your accounts as transfers. Returns (linked, transfers_paired)."""
    linked = 0
    for transaction_id in payload.matched_ids:
        logged = session.get(Transaction, transaction_id)
        if logged and logged.user_id == user.id and logged.source == TransactionSource.manual and logged.account_id is None:
            logged.account_id = payload.account_id
            session.add(logged)
            linked += 1

    transfers_paired = 0
    for transaction_id in payload.transfer_pair_ids:
        other = session.get(Transaction, transaction_id)
        if other and other.user_id == user.id and other.account_id not in (None, payload.account_id):
            if other.type != TransactionType.transfer or other.category_id is not None:
                other.type, other.category_id = TransactionType.transfer, None
                session.add(other)
            transfers_paired += 1
    return linked, transfers_paired


@router.post("/statement/confirm")
def confirm_import(payload: ImportConfirm, session: SessionDep, user: CurrentUser):
    """Save the rows you kept in the preview."""
    get_account_or_404(session, payload.account_id, user)
    if not payload.rows:
        linked, transfers_paired = link_and_pair(session, payload, user)
        session.commit()
        return {"created": [], "skipped": 0, "import_id": None, "keywords_learned": [],
                "linked": linked, "transfers_paired": transfers_paired}

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

    # The batch: every row saved below points to it, so the whole import can be undone.
    batch = StatementImport(
        user_id=user.id,
        account_id=payload.account_id,
        file_name=payload.file_name.strip() or "statement",
        first_date=low,
        last_date=high,
        row_count=0,
    )
    session.add(batch)
    session.flush()  # gives the batch its id now, before the transactions need it

    # Rules so far; new ones get added as we learn, so later rows see them.
    rules = list(session.exec(select(CategoryRule).where(CategoryRule.user_id == user.id)).all())
    learned_keywords = []

    created, skipped = [], 0
    for row in payload.rows:
        category_id = resolve_category(session, row.category_id, row.type, user)
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
            user_id=user.id,
            amount=round(row.amount, 2),
            date=row.date,
            description=row.description,
            type=row.type,
            source=TransactionSource.statement,
            category_id=category_id,
            account_id=payload.account_id,
            import_id=batch.id,
        )
        session.add(transaction)
        created.append(transaction)

        # Learn: you categorized a place no keyword covers yet -> remember it.
        if category_id is not None and learnable(row.description):
            if match_rule(row.description, rules) is None:
                keyword = suggest_keyword(row.description)
                if keyword and all(r.keyword != keyword for r in rules):
                    rule = CategoryRule(keyword=keyword, category_id=category_id, user_id=user.id)
                    session.add(rule)
                    rules.append(rule)
                    learned_keywords.append(keyword)

    linked, transfers_paired = link_and_pair(session, payload, user)

    if not created:
        session.delete(batch)  # everything was already there: nothing to undo later
        batch = None
    else:
        batch.row_count = len(created)
        session.add(batch)

    session.commit()
    for transaction in created:
        session.refresh(transaction)
    return {
        "created": created,
        "skipped": skipped,
        "import_id": batch.id if batch else None,
        "keywords_learned": learned_keywords,
        "linked": linked,
        "transfers_paired": transfers_paired,
    }


@router.get("/statement/imports")
def list_imports(session: SessionDep, user: CurrentUser):
    """Your statement imports, newest first, with how many of their rows still exist."""
    remaining = dict(
        session.exec(
            select(Transaction.import_id, func.count(Transaction.id))
            .where(Transaction.user_id == user.id, Transaction.import_id.is_not(None))
            .group_by(Transaction.import_id)
        ).all()
    )
    batches = session.exec(
        select(StatementImport)
        .where(StatementImport.user_id == user.id)
        .order_by(StatementImport.imported_at.desc(), StatementImport.id.desc())
    ).all()
    return [{**batch.model_dump(), "remaining": remaining.get(batch.id, 0)} for batch in batches]


@router.delete("/statement/imports/{import_id}")
def undo_import(import_id: int, session: SessionDep, user: CurrentUser):
    """Remove every transaction an import created, then the import itself.

    Transactions you typed in yourself are never touched: they have no import_id.
    """
    batch = get_owned_or_404(session, StatementImport, import_id, user, "Import")

    rows = session.exec(select(Transaction).where(Transaction.import_id == import_id)).all()
    for transaction in rows:
        session.delete(transaction)
    session.flush()  # children first, then the parent (foreign keys are on)
    session.delete(batch)
    session.commit()
    return {"deleted": len(rows)}
