"""Shared setup for the tests. pytest loads this file by itself before running any test.

The big idea: every test gets its own brand-new, empty database in a temporary folder.
So tests never touch your real database.db, and one test can't break another.

A "fixture" is a function pytest runs for you when a test asks for it by name:
    def test_something(api):        # pytest sees "api", runs the api() fixture below,
        ...                         # and passes in what it returns
"""
import os

# Safety net, set before anything imports database.py: point the default database
# somewhere harmless (in memory) and keep the test output quiet.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ECHO_SQL"] = "0"

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import database  # noqa: E402
from main import app  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
ROW_FIELDS = ("date", "description", "amount", "type", "category_id")


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A test version of the API, backed by a fresh database file in a temp folder."""
    engine = database.make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(database, "engine", engine)  # swapped back after the test
    with TestClient(app) as test_client:  # starting the app runs the migrations
        yield test_client
    engine.dispose()


class Api:
    """Small helpers so tests read like what they do: api.account(...), api.preview_pdf(...)."""

    def __init__(self, client):
        self.client = client

    # ---- setup
    def account(self, nickname="NCB Savings", last_four="0042", account_type="savings", bank="NCB"):
        r = self.client.post("/account/", json={
            "nickname": nickname, "bank_name": bank, "account_type": account_type, "last_four": last_four,
        })
        assert r.status_code == 200, r.text
        return r.json()

    def category(self, name, kind="expense"):
        r = self.client.post("/categories/", json={"name": name, "kind": kind})
        assert r.status_code == 200, r.text
        return r.json()

    def categories(self):
        """{name: id} for every category."""
        return {c["name"]: c["id"] for c in self.client.get("/categories/").json()}

    def log(self, amount, date, description, **extra):
        """Log a transaction by hand."""
        r = self.client.post("/transaction/", json={"amount": amount, "date": date, "description": description, **extra})
        assert r.status_code == 200, r.text
        return r.json()

    # ---- statement import
    def preview_pdf(self, account_id, name="ncb_sept.pdf", password=None):
        data = {"account_id": account_id}
        if password:
            data["password"] = password
        with open(FIXTURES / name, "rb") as f:
            return self.client.post("/statement/preview", data=data, files={"file": (name, f, "application/pdf")})

    def preview_csv(self, account_id, lines, header="date,description,amount"):
        text = header + "\n" + "\n".join(lines) + "\n"
        r = self.client.post("/statement/preview", data={"account_id": account_id},
                             files={"file": ("export.csv", text.encode(), "text/csv")})
        assert r.status_code == 200, r.text
        return r.json()["rows"]

    def confirm(self, account_id, rows, file_name="statement.pdf"):
        """Import the ticked rows, sending exactly what the app sends."""
        keep = [r for r in rows if r["include"]]
        r = self.client.post("/statement/confirm", json={
            "account_id": account_id,
            "file_name": file_name,
            "rows": [{k: row[k] for k in ROW_FIELDS} for row in keep],
            "matched_ids": [row["match_id"] for row in rows if row.get("flag") == "match" and not row["include"]],
            "transfer_pair_ids": [row["pair_id"] for row in keep if row.get("pair_id") and row["type"] == "transfer"],
        })
        assert r.status_code == 200, r.text
        return r.json()

    def import_csv(self, account_id, lines):
        return self.confirm(account_id, self.preview_csv(account_id, lines), file_name="export.csv")


@pytest.fixture
def api(client):
    return Api(client)


@pytest.fixture
def september(api):
    """The usual starting point: an account, Food + Salary categories, a Food budget,
    a lunch you logged by hand in September and a snack in August."""
    account = api.account()
    food = api.category("Food")
    salary = api.category("Salary", kind="income")
    api.client.post("/budget/", json={"category_id": food["id"], "year": 2026, "month": 9, "amount": 10000})
    lunch = api.log(1580, "2026-09-21", "Lunch at Juici", category_id=food["id"])
    snack = api.log(300, "2026-08-20", "Campus Foods snacks", category_id=food["id"])
    return {"account": account, "food": food, "salary": salary, "lunch": lunch, "snack": snack}


@pytest.fixture
def imported(api, september):
    """`september`, plus the test statement imported the way you'd review it:
    the ELink from your savings marked as a transfer and the payroll filed as Salary."""
    rows = api.preview_pdf(september["account"]["id"]).json()["rows"]
    for row in rows:
        if "TRF-FROM" in row["description"]:
            row["type"] = "transfer"
        if row["description"].startswith("PAYROLL"):
            row["category_id"] = september["salary"]["id"]
    result = api.confirm(september["account"]["id"], rows, file_name="ncb_sept.pdf")
    return {**september, "rows": rows, "result": result, "import_id": result["import_id"]}
