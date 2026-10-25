"""Demo accounts: made-up data to try Ledger with, gone after a week or when you end it."""
import datetime

from fastapi.testclient import TestClient
from sqlmodel import Session, select

import database
import demo
from conftest import PASSWORD, Api
from main import app
from models import Account, Category, LoginSession, Transaction, TransactionType, User


def start(browser, code=None):
    return browser.post("/demo/start", json={"code": code})


def demo_users():
    with Session(database.engine) as session:
        return session.exec(select(User).where(User.is_demo)).all()


def rows(model, user_id):
    with Session(database.engine) as session:
        return session.exec(select(model).where(model.user_id == user_id)).all()


# ---------------------------------------------------------------- who can start one
def test_open_on_your_laptop(anonymous):
    settings = anonymous.get("/auth/settings").json()
    assert settings["demo"] == "open" and settings["demo_days"] == demo.DEMO_DAYS
    me = start(anonymous).json()
    assert me["is_demo"] is True and me["username"].startswith("demo-")
    assert anonymous.get("/auth/me").json() == me


def test_off_once_deployed_unless_you_set_a_code(anonymous, monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    assert anonymous.get("/auth/settings").json()["demo"] == "off"
    assert start(anonymous).status_code == 403


def test_the_demo_link_carries_the_code(anonymous, monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("DEMO_CODE", "try-it-out")
    assert anonymous.get("/auth/settings").json()["demo"] == "code"
    assert start(anonymous).status_code == 403
    assert start(anonymous, "wrong").status_code == 403
    assert start(anonymous, "try-it-out").status_code == 200


def test_feedback_link_comes_from_the_settings(anonymous, monkeypatch):
    assert anonymous.get("/auth/settings").json()["feedback_url"] is None
    monkeypatch.setenv("FEEDBACK_URL", "https://forms.example.com/ledger")
    assert anonymous.get("/auth/settings").json()["feedback_url"] == "https://forms.example.com/ledger"


# ---------------------------------------------------------------- what's in it
def test_a_demo_starts_full_of_made_up_data(anonymous):
    start(anonymous)
    accounts = anonymous.get("/account/").json()
    assert {a["nickname"] for a in accounts} == {"NCB Chequing", "NCB Savings"}
    assert len(anonymous.get("/categories/").json()) == 10
    assert len(anonymous.get("/rules/").json()) > 50

    today = datetime.date.today()
    month = anonymous.get(f"/summary/{today.year}/{today.month}").json()
    assert month["spending"] > 0, "this month already has spending in it"
    assert month["total_budgeted"] > 0
    assert all(t["date"] <= today.isoformat() for t in anonymous.get("/transaction/").json()), "nothing in the future"


def test_filling_is_by_date(client):
    with Session(database.engine) as session:
        user = demo.create_demo(session, today=datetime.date(2026, 11, 3))
        dates = [t.date for t in session.exec(select(Transaction).where(Transaction.user_id == user.id)).all()]
    assert max(dates) <= datetime.date(2026, 11, 3)
    assert {d.month for d in dates} >= {10, 11}


def test_a_demo_never_opens_overspent(client):
    """Whatever day someone opens it, this month's pay is already in."""
    for day in (1, 16, 31):
        with Session(database.engine) as session:
            user_id = demo.create_demo(session, today=datetime.date(2026, 10, day)).id
        month = [t for t in rows(Transaction, user_id) if (t.date.year, t.date.month) == (2026, 10)]
        income = sum(t.amount for t in month if t.type == TransactionType.income)
        spent = sum(t.amount for t in month if t.type == TransactionType.expense)
        assert income > spent, f"opened on Oct {day}"


def test_the_sample_statement_imports_cleanly(anonymous):
    start(anonymous)
    pdf = anonymous.get("/demo/sample-statement.pdf")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    chequing = next(a for a in anonymous.get("/account/").json() if a["nickname"] == "NCB Chequing")
    preview = anonymous.post(
        "/statement/preview",
        data={"account_id": chequing["id"]},
        files={"file": ("ncb-sample-statement.pdf", pdf.content, "application/pdf")},
    ).json()
    assert preview["problems"] == []
    row = {r["description"]: r for r in preview["rows"]}
    find = lambda text: next(r for d, r in row.items() if text in d)  # noqa: E731
    assert find("JUICI")["flag"] == "match", "the hand-logged lunch is spotted"
    assert find("TRF-FROM SAVINGS")["flag"] == "transfer", "money from the demo savings account"
    assert find("TRF-TO SAVINGS")["flag"] == "transfer", "money to the demo savings account"
    assert "PRICESMART" in (find("POSREV")["reverses"] or ""), "the refund finds its purchase"
    assert find("LOCAL VENDOR")["category_id"] is None, "one left for you to pick"

    # Importing it, as reviewed, gives September a sensible month: pay in, nothing doubled up.
    Api(anonymous).confirm(chequing["id"], preview["rows"], file_name="ncb-sample-statement.pdf")
    month = anonymous.get("/summary/2026/9").json()
    assert 0 < month["spending"] < month["income"]
    descriptions = [t["description"] for t in anonymous.get("/transaction/").json() if t["date"].startswith("2026-09")]
    assert "Hi-Lo groceries" not in descriptions, "September is the statement's month only"


def test_anyone_can_download_the_sample(anonymous):
    assert anonymous.get("/demo/sample-statement.pdf").status_code == 200


def test_a_missing_sample_says_so(anonymous, monkeypatch, tmp_path):
    import routers.demo
    monkeypatch.setattr(routers.demo, "SAMPLE_STATEMENT", tmp_path / "not-here.pdf")
    r = anonymous.get("/demo/sample-statement.pdf")
    assert r.status_code == 404 and "missing" in r.json()["detail"]


# ---------------------------------------------------------------- privacy
def test_each_demo_is_separate_from_real_accounts_and_other_demos(client, api, september):
    first = TestClient(app)
    second = TestClient(app)
    with first, second:
        start(first)
        start(second)
        first.post("/transaction/", json={"amount": 5, "date": "2026-10-01", "description": "only in first"})
        assert "only in first" not in [t["description"] for t in second.get("/transaction/").json()]
        assert "Lunch at Juici" not in [t["description"] for t in first.get("/transaction/").json()
                                        if t["account_id"] == september["account"]["id"]]
    assert all(a["nickname"] == "NCB Savings" for a in api.client.get("/account/").json()), "tester's own accounts only"


def test_demos_cant_log_in_with_a_password(anonymous):
    me = start(anonymous).json()
    other = TestClient(app)
    with other:
        r = other.post("/auth/login", json={"username": me["username"], "password": PASSWORD})
        assert r.status_code == 401


def test_nobody_can_sign_up_with_a_demo_name(anonymous):
    r = anonymous.post("/auth/signup", json={"username": "demo-abc123", "password": PASSWORD})
    assert r.status_code == 400


# ---------------------------------------------------------------- going away
def test_ending_a_demo_deletes_everything(anonymous):
    me = start(anonymous).json()
    assert rows(Transaction, me["id"])
    assert anonymous.post("/demo/end").status_code == 200
    assert anonymous.get("/auth/me").status_code == 401
    for model in (Transaction, Account, Category, LoginSession):
        assert rows(model, me["id"]) == []
    assert demo_users() == []


def test_a_real_account_cant_be_ended(client):
    assert client.post("/demo/end").status_code == 400
    assert client.get("/auth/me").status_code == 200


def test_demos_older_than_a_week_are_cleaned_up(client, anonymous):
    old = start(anonymous).json()
    with Session(database.engine) as session:
        user = session.get(User, old["id"])
        user.created_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=demo.DEMO_DAYS, minutes=1)
        session.add(user)
        session.commit()
    fresh = TestClient(app)
    with fresh:
        start(fresh)  # starting a new demo tidies up the old ones
    # (SQLite can hand the freed id to the next user, so compare names, not ids.)
    assert [u.username for u in demo_users()] != [old["username"]]
    assert len(demo_users()) == 1, "only the new demo is left"
    assert client.get("/auth/me").status_code == 200, "real accounts are never cleaned up"


def test_there_is_a_limit_on_demos_at_once(anonymous, monkeypatch):
    monkeypatch.setattr(demo, "MAX_DEMOS", 2)
    import routers.demo
    monkeypatch.setattr(routers.demo, "MAX_DEMOS", 2)
    assert start(anonymous).status_code == 200
    with TestClient(app) as second, TestClient(app) as third:
        assert start(second).status_code == 200
        assert start(third).status_code == 429
