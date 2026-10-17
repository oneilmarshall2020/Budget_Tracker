"""Accounts, categories and budgets: what's allowed, and what deleting does."""


def test_blank_category_name_is_rejected(client):
    assert client.post("/categories/", json={"name": "   "}).status_code == 422


def test_account_last_four_must_be_four_digits(client):
    r = client.post("/account/", json={"nickname": "Main", "bank_name": "NCB", "account_type": "savings", "last_four": "12a4"})
    assert r.status_code == 422


def test_account_type_must_be_a_known_one(client):
    r = client.post("/account/", json={"nickname": "Main", "bank_name": "NCB", "account_type": "piggybank", "last_four": "1234"})
    assert r.status_code == 422


def test_account_keeps_leading_zeros_and_defaults_to_jmd(api):
    account = api.account(last_four="0042")
    assert account["last_four"] == "0042"
    assert account["currency"] == "JMD"


def test_categories_are_spending_unless_told_otherwise(api):
    assert api.category("Food")["kind"] == "expense"
    assert api.category("Salary", kind="income")["kind"] == "income"


def test_budget_rules(client, api):
    food = api.category("Food")
    salary = api.category("Salary", kind="income")

    def budget(category_id, amount=500):
        return client.post("/budget/", json={"category_id": category_id, "year": 2026, "month": 9, "amount": amount})

    assert budget(food["id"], 10000).status_code == 200
    assert budget(food["id"]).status_code == 400, "only one budget per category per month"
    assert budget(salary["id"]).status_code == 400, "no budgets on income categories"
    assert budget(999).status_code == 404, "a missing category is a 404, not a crash"
    assert len(client.get("/budget/?year=2026&month=9").json()) == 1
    assert client.get("/budget/?year=2026&month=10").json() == []


def test_cant_flip_the_kind_of_a_category_in_use(client, september):
    r = client.patch(f"/categories/{september['food']['id']}", json={"kind": "income"})
    assert r.status_code == 400


def test_renaming_an_account_keeps_its_other_fields(client, api):
    account = api.account(last_four="0042")
    r = client.patch(f"/account/{account['id']}", json={"nickname": "Savings"})
    assert r.json()["nickname"] == "Savings"
    assert r.json()["last_four"] == "0042"


def test_deleting_a_category_keeps_its_transactions_but_removes_budgets_and_keywords(client, api, imported):
    food_id = imported["food"]["id"]
    client.post("/rules/", json={"keyword": "CAMPUS", "category_id": food_id})
    before = len(client.get("/transaction/?year=2026").json())

    client.delete(f"/categories/{food_id}")

    after = client.get("/transaction/?year=2026").json()
    assert len(after) == before
    assert not any(t["category_id"] == food_id for t in after)
    assert not any(b["category_id"] == food_id for b in client.get("/budget/").json())
    assert not any(r["category_id"] == food_id for r in client.get("/rules/").json())


def test_deleting_an_account_keeps_its_transactions_and_imports_unlinked(client, imported):
    before = len(client.get("/transaction/?year=2026").json())

    client.delete(f"/account/{imported['account']['id']}")

    after = client.get("/transaction/?year=2026").json()
    assert len(after) == before
    assert all(t["account_id"] is None for t in after)
    imports = client.get("/statement/imports").json()
    assert len(imports) == 1 and imports[0]["account_id"] is None, "the import can still be undone"
