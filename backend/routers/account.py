from fastapi import APIRouter
from sqlmodel import select

from auth import CurrentUser
from database import SessionDep
from helpers import get_account_or_404
from models import Account, AccountCreate, AccountUpdate, StatementImport, Transaction

router = APIRouter(tags=["Accounts"])


@router.post("/account/")
def create_account(account_in: AccountCreate, session: SessionDep, user: CurrentUser) -> Account:
    account = Account(**account_in.model_dump(), user_id=user.id)
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


@router.get("/account/")
def read_accounts(session: SessionDep, user: CurrentUser) -> list[Account]:
    return session.exec(
        select(Account).where(Account.user_id == user.id).order_by(Account.nickname)
    ).all()


@router.patch("/account/{account_id}")
def update_account(
    account_id: int, account_update: AccountUpdate, session: SessionDep, user: CurrentUser
) -> Account:
    account = get_account_or_404(session, account_id, user)
    account.sqlmodel_update(account_update.model_dump(exclude_unset=True, exclude_none=True))
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


@router.delete("/account/{account_id}")
def delete_account(account_id: int, session: SessionDep, user: CurrentUser):
    account = get_account_or_404(session, account_id, user)

    # The money was still earned or spent, so keep the transactions and unlink them.
    linked = session.exec(select(Transaction).where(Transaction.account_id == account_id)).all()
    for transaction in linked:
        transaction.account_id = None
        session.add(transaction)

    # Same for the import history (it can still be undone afterwards).
    imports = session.exec(
        select(StatementImport).where(StatementImport.account_id == account_id)
    ).all()
    for batch in imports:
        batch.account_id = None
        session.add(batch)

    session.flush()
    session.delete(account)
    session.commit()
    return {"ok": True}
