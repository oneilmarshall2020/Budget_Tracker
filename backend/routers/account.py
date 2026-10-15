from fastapi import APIRouter
from sqlmodel import select

from database import SessionDep
from helpers import get_account_or_404
from models import Account, AccountCreate, AccountUpdate, Transaction

router = APIRouter(tags=["Accounts"])


@router.post("/account/")
def create_account(account_in: AccountCreate, session: SessionDep) -> Account:
    account = Account(**account_in.model_dump())
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


@router.get("/account/")
def read_accounts(session: SessionDep) -> list[Account]:
    return session.exec(select(Account).order_by(Account.nickname)).all()


@router.patch("/account/{account_id}")
def update_account(
    account_id: int, account_update: AccountUpdate, session: SessionDep
) -> Account:
    account = get_account_or_404(session, account_id)
    account.sqlmodel_update(account_update.model_dump(exclude_unset=True, exclude_none=True))
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


@router.delete("/account/{account_id}")
def delete_account(account_id: int, session: SessionDep):
    account = get_account_or_404(session, account_id)

    linked = session.exec(select(Transaction).where(Transaction.account_id == account_id)).all()
    for transaction in linked:
        transaction.account_id = None
        session.add(transaction)

    session.flush()
    session.delete(account)
    session.commit()
    return {"ok": True}
