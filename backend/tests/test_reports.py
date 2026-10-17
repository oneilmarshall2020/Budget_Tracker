"""Monthly and yearly reports, checked against the raw transactions."""
import pytest


def money(x):
    return round(x, 2)


@pytest.fixture
def report(client, imported):
    """September after the import, with a small Bank Fees budget so it goes over."""
    fees_id = next(c["id"] for c in client.get("/categories/").json() if c["name"] == "Bank Fees")
    client.post("/budget/", json={"category_id": fees_id, "year": 2026, "month": 9, "amount": 100})
    sept = client.get("/transaction/?year=2026&month=9").json()
    return {
        "monthly": client.get("/summary/2026/9").json(),
        "yearly": client.get("/summary/2026").json(),
        "sept": sept,
        "fees_id": fees_id,
        "income": money(sum(t["amount"] for t in sept if t["type"] == "income")),
        "spending": money(sum(t["amount"] for t in sept if t["type"] == "expense")
                          - sum(t["amount"] for t in sept if t["type"] == "refund")),
    }


def test_income_spending_and_net(report):
    monthly = report["monthly"]
    assert monthly["income"] == report["income"] == 33212.05, "transfers aren't income"
    assert monthly["spending"] == report["spending"], "refunds come off spending"
    assert monthly["net"] == money(report["income"] - report["spending"])


def test_spending_by_category(report):
    by_cat = {x["category"]: x["amount"] for x in report["monthly"]["spending_by_category"]}
    fee_total = money(sum(t["amount"] for t in report["sept"] if t["category_id"] == report["fees_id"]))
    assert by_cat["Bank Fees"] == fee_total
    assert by_cat["Food"] == money(1260 + 690 + 500 + 1580), "3 Campus Foods rows + your lunch"
    assert by_cat["Uncategorized"] == money(report["spending"] - fee_total - by_cat["Food"])
    amounts = [x["amount"] for x in report["monthly"]["spending_by_category"]]
    assert amounts == sorted(amounts, reverse=True), "ranked most to least"


def test_budget_vs_actual(report):
    lines = {x["category"]: x for x in report["monthly"]["categories"]}
    assert lines["Food"]["budgeted"] == 10000
    assert lines["Bank Fees"]["remaining"] < 0, "fees went over their budget"


def test_income_by_source(report):
    assert report["monthly"]["income_by_category"][0]["category"] == "Salary"


def test_yearly_matches_monthly(report):
    september = report["yearly"]["months"][8]
    assert september["income"] == report["monthly"]["income"]
    assert september["spending"] == report["monthly"]["spending"]
    assert report["yearly"]["months"][7]["spending"] == 300, "August has the snack"
    assert report["yearly"]["spending"] == money(report["monthly"]["spending"] + 300)


def test_savings_rate(report):
    yearly = report["yearly"]
    assert yearly["savings_rate"] == round(yearly["net"] / yearly["income"] * 100, 1)


def test_over_budget_habits(report):
    assert report["yearly"]["over_budget"] == [{"category": "Bank Fees", "months_over": 1, "months_budgeted": 1}]


def test_month_13_is_rejected(client):
    assert client.get("/summary/2026/13").status_code == 400
