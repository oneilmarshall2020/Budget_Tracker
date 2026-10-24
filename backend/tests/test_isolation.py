"""Two people, one app: nobody sees or touches anyone else's data.

`api` is "tester". `stranger` is a second person, logged in on another browser.
"""
import pytest

from conftest import Api

STATEMENT = [
    "2026-09-04,POS JUICI PATTIES - UWI MONA,-1120",
    "2026-09-25,PAYROLL DEP EMPLOYER SALARY,33212.05",
]


@pytest.fixture
def tester_data(api, september):
    """tester's month, plus a keyword and an imported statement."""
    rule = api.client.post("/rules/", json={"keyword": "JUICI", "category_id": september["food"]["id"]}).json()
    imported = api.import_csv(september["account"]["id"], STATEMENT)
    budget = api.client.get("/budget/").json()[0]
    return {**september, "rule": rule, "import_id": imported["import_id"], "budget": budget,
            "statement_row": imported["created"][0]}


def everything(client):
    """What a person sees: every list the page loads."""
    return {
        "accounts": client.get("/account/").json(),
        "categories": client.get("/categories/").json(),
        "rules": client.get("/rules/").json(),
        "budgets": client.get("/budget/").json(),
        "transactions": client.get("/transaction/").json(),
        "search": client.get("/transaction/?q=juici").json(),
        "imports": client.get("/statement/imports").json(),
        "similar": client.get("/transaction/similar?amount=1120&date=2026-09-04&type=expense").json(),
    }


def test_a_new_person_starts_with_nothing(tester_data, stranger):
    assert all(found == [] for found in everything(stranger).values())
    month = stranger.get("/summary/2026/9").json()
    year = stranger.get("/summary/2026").json()
    assert month["income"] == month["spending"] == year["income"] == year["spending"] == 0
    assert month["categories"] == year["over_budget"] == []


def test_someone_elses_things_are_not_found(tester_data, stranger):
    t = tester_data
    for path in (f"/transaction/{t['lunch']['id']}",):
        assert stranger.get(path).status_code == 404
    attempts = [
        ("PATCH", f"/transaction/{t['lunch']['id']}", {"description": "mine now"}),
        ("DELETE", f"/transaction/{t['lunch']['id']}", None),
        ("PATCH", f"/account/{t['account']['id']}", {"nickname": "mine now"}),
        ("DELETE", f"/account/{t['account']['id']}", None),
        ("PATCH", f"/categories/{t['food']['id']}", {"name": "mine now"}),
        ("DELETE", f"/categories/{t['food']['id']}", None),
        ("PATCH", f"/budget/{t['budget']['id']}", {"amount": 1}),
        ("DELETE", f"/budget/{t['budget']['id']}", None),
        ("PATCH", f"/rules/{t['rule']['id']}", {"keyword": "MINE"}),
        ("DELETE", f"/rules/{t['rule']['id']}", None),
        ("DELETE", f"/statement/imports/{t['import_id']}", None),
    ]
    for method, path, body in attempts:
        r = stranger.request(method, path, json=body)
        assert r.status_code == 404, f"{method} {path} answered {r.status_code}"


def test_you_cant_point_at_someone_elses_account_or_category(tester_data, stranger):
    food, account = tester_data["food"]["id"], tester_data["account"]["id"]
    own = Api(stranger)
    own_food = own.category("Food")
    attempts = [
        ("/transaction/", {"amount": 5, "date": "2026-09-01", "description": "x", "category_id": food}),
        ("/transaction/", {"amount": 5, "date": "2026-09-01", "description": "x", "account_id": account}),
        ("/budget/", {"category_id": food, "year": 2026, "month": 9, "amount": 100}),
        ("/rules/", {"keyword": "SNEAKY", "category_id": food}),
        ("/rules/remember", {"keyword": "SNEAKY", "category_id": food}),
        ("/rules/apply", {"keyword": "JUICI", "category_id": food}),
        ("/statement/confirm", {"account_id": account, "rows": []}),
    ]
    for path, body in attempts:
        r = stranger.post(path, json=body)
        assert r.status_code == 404, f"POST {path} answered {r.status_code}"
    r = stranger.get(f"/rules/suggest?description=JUICI%20PATTIES&category_id={food}")
    assert r.status_code == 404
    r = stranger.patch(f"/transaction/{own.log(5, '2026-09-01', 'Mine')['id']}", json={"category_id": food})
    assert r.status_code == 404
    assert own_food["id"] != food


def test_you_cant_preview_a_statement_into_someone_elses_account(tester_data, stranger):
    r = stranger.post(
        "/statement/preview",
        data={"account_id": tester_data["account"]["id"]},
        files={"file": ("export.csv", b"date,description,amount\n2026-09-01,X,-5\n", "text/csv")},
    )
    assert r.status_code == 404


def test_your_import_doesnt_touch_someone_elses_entries(tester_data, stranger, api):
    before = everything(api.client)
    own = Api(stranger)
    account = own.account(nickname="My NCB", last_four="0042")
    # The same rows tester imported, plus one that looks just like tester's hand-logged lunch.
    rows = own.preview_csv(account["id"], STATEMENT + ["2026-09-21,LUNCH AT JUICI,-1580"])
    assert all(row["include"] for row in rows), "nothing is 'already there' for someone else"
    assert all(row["flag"] in (None, "review") and row["match_id"] is None for row in rows)
    assert all(row["category_id"] is None for row in rows), "tester's categories don't leak in"
    r = stranger.post("/statement/confirm", json={
        "account_id": account["id"],
        "rows": [],
        "matched_ids": [tester_data["lunch"]["id"]],  # tester's hand-logged lunch
        "transfer_pair_ids": [tester_data["statement_row"]["id"]],
    })
    assert r.json()["linked"] == r.json()["transfers_paired"] == 0
    assert everything(api.client) == before, "tester's data is exactly as it was"


def test_two_people_can_use_the_same_keywords_and_starter_set(tester_data, stranger, api):
    own = Api(stranger)
    own_food = own.category("Food")
    assert stranger.post("/rules/", json={"keyword": "JUICI", "category_id": own_food["id"]}).status_code == 200

    first = api.client.post("/rules/suggested").json()
    second = stranger.post("/rules/suggested").json()
    assert second["categories_added"] > 0 and second["keywords_added"] > 0
    assert first["keywords_added"] > 0
    assert len(api.client.get("/rules/").json()) == len(stranger.get("/rules/").json())


def test_reports_only_count_your_own_money(tester_data, stranger, api):
    own = Api(stranger)
    own.log(500, "2026-09-10", "My lunch")
    theirs = api.client.get("/summary/2026/9").json()
    mine = stranger.get("/summary/2026/9").json()
    assert mine["spending"] == 500
    assert theirs["spending"] > 500 and theirs["income"] > 0
