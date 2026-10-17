"""Automatic categorizing: keyword rules, the suggested set, and learning from you."""
import pytest


@pytest.fixture
def suggested(api):
    """The suggested categories + keywords, plus an account. Returns {category name: id}."""
    api.client.post("/rules/suggested")
    api.account()
    return api.categories()


def account_id(api):
    return api.client.get("/account/").json()[0]["id"]


# ---------------------------------------------------------------- the suggested set
def test_suggested_set_adds_categories_and_keywords(client):
    r = client.post("/rules/suggested").json()
    assert r["categories_added"] == 10 and r["keywords_added"] > 60
    kinds = {c["name"]: c["kind"] for c in client.get("/categories/").json()}
    assert kinds["Salary"] == "income" and kinds["Food & Dining"] == "expense"


def test_suggested_set_twice_adds_nothing(client):
    client.post("/rules/suggested")
    assert client.post("/rules/suggested").json() == {"categories_added": 0, "keywords_added": 0}


# ---------------------------------------------------------------- managing keywords
def test_keywords_are_stored_uppercase_with_single_spaces(client, suggested):
    r = client.post("/rules/", json={"keyword": "  afresh   marketplace ", "category_id": suggested["Groceries"]})
    assert r.json()["keyword"] == "AFRESH MARKETPLACE"


def test_a_keyword_can_only_belong_to_one_category(client, suggested):
    r = client.post("/rules/", json={"keyword": "hi-lo", "category_id": suggested["Shopping"]})
    assert r.status_code == 400 and "Groceries" in r.json()["detail"], "the message says who has it"


def test_bad_keywords_are_refused(client, suggested):
    assert client.post("/rules/", json={"keyword": " a ", "category_id": suggested["Shopping"]}).status_code == 422
    assert client.post("/rules/", json={"keyword": "XYZ", "category_id": 9999}).status_code == 404


def test_keywords_can_be_edited_and_deleted(client, suggested):
    rule = client.post("/rules/", json={"keyword": "afresh", "category_id": suggested["Groceries"]}).json()
    assert client.patch(f"/rules/{rule['id']}", json={"keyword": "afresh mkt"}).json()["keyword"] == "AFRESH MKT"
    assert client.delete(f"/rules/{rule['id']}").status_code == 200
    assert not any(r["keyword"] == "AFRESH MKT" for r in client.get("/rules/").json())


# ---------------------------------------------------------------- keywords in the import review
def test_preview_categorizes_known_places(api, suggested):
    rows = {r["description"]: r for r in api.preview_pdf(account_id(api)).json()["rows"]}
    name = {v: k for k, v in suggested.items()}

    def category_of(start):
        row = next(r for d, r in rows.items() if d.startswith(start))
        return name.get(row["category_id"])

    juici = next(r for d, r in rows.items() if d.startswith("JUICI"))
    assert juici["category_source"] == "rule" and juici["rule_keyword"] == "JUICI"
    assert category_of("JUICI") == "Food & Dining"
    assert category_of("APPLE.COM") == "Subscriptions"
    assert category_of("HI-LO") == "Groceries"
    assert category_of("MAVIS BANK COFFEE") == "Food & Dining", "by COFFEE"
    assert category_of("MOTHER'S-UWI MAIN CANTEENKINGSTON") == "Food & Dining", "glued words still match CANTEEN"
    assert category_of("PAYROLL") == "Salary"
    assert category_of("POS Tx Fee") == "Bank Fees"


def test_only_unknown_places_are_left_uncategorized(api, suggested):
    rows = api.preview_pdf(account_id(api)).json()["rows"]
    left = sorted({r["description"].split()[0] for r in rows if r["category_id"] is None})
    assert left == ["ELink", "NEW", "POSREV"], "transfers, reversals with no name, and New Hope"


def test_preview_suggests_what_to_learn(api, suggested):
    rows = api.preview_pdf(account_id(api)).json()["rows"]
    new_hope = next(r for r in rows if r["description"].startswith("NEW HOPE"))
    assert new_hope["keyword"] == "NEW HOPE", "short first word, so two words"
    assert all(r["keyword"] is None for r in rows if "Tx Fee" in r["description"] or "TRF-" in r["description"]), \
        "never learn from fees or transfers"


def test_categorizing_a_new_place_on_import_teaches_a_keyword(api, suggested):
    rows = api.preview_pdf(account_id(api)).json()["rows"]
    next(r for r in rows if r["description"].startswith("NEW HOPE"))["category_id"] = suggested["Food & Dining"]
    result = api.confirm(account_id(api), rows)
    assert result["keywords_learned"] == ["NEW HOPE"]

    api.client.delete(f"/statement/imports/{result['import_id']}")
    again = api.preview_pdf(account_id(api)).json()["rows"]
    new_hope = next(r for r in again if r["description"].startswith("NEW HOPE"))
    assert new_hope["category_source"] == "rule" and new_hope["rule_keyword"] == "NEW HOPE"


# ---------------------------------------------------------------- matching details
@pytest.mark.parametrize("description, expected", [
    ("AMAZON PRIME VIDEO", "Subscriptions"),  # the longer keyword wins over AMAZON
    ("AMAZON.COM ORDER 123", "Shopping"),
    ("OVERFLOW STORE", None),                 # FLOW only matches at the start of a word
    ("PAYROLL REVERSAL", None),               # an income keyword never lands on an expense
    ("juici patties", "Food & Dining"),       # upper/lower case doesn't matter
])
def test_keyword_matching(api, suggested, description, expected):
    (row,) = api.preview_csv(account_id(api), [f"2026-10-01,{description},-100"])
    name = {v: k for k, v in suggested.items()}
    assert name.get(row["category_id"]) == expected


# ---------------------------------------------------------------- learning when you re-categorize
@pytest.fixture
def campus(api, suggested):
    """Three Campus Foods rows (Food & Dining by keyword), an Afresh row, a fee, and a snack you logged."""
    api.import_csv(account_id(api), [
        "2026-09-14,POS CAMPUS FOODS & ESSENTIALSKINGSTON,-1260",
        "2026-09-18,POS CAMPUS FOODS & ESSENTIALSKINGSTON,-690",
        "2026-09-21,POS CAMPUS FOODS & ESSENTIALSKING 319,-500",
        "2026-09-22,POS AFRESH MARKETPLACE LIMITEKINGSTON,-900",
        "2026-09-22,POS Tx Fee,-10.30",
    ])
    api.log(300, "2026-09-25", "Campus Foods snack")
    return {t["description"]: t for t in api.client.get("/transaction/?year=2026&month=9").json()}


def suggest(client, description, category_id, exclude_id=None):
    params = {"description": description, "category_id": category_id}
    if exclude_id:
        params["exclude_id"] = exclude_id
    return client.get("/rules/suggest", params=params).json()


def test_suggest_offers_to_move_an_existing_keyword(client, suggested, campus):
    tx = campus["CAMPUS FOODS & ESSENTIALSKINGSTON"]
    s = suggest(client, tx["description"], suggested["Groceries"], tx["id"])
    assert s["keyword"] == "CAMPUS FOODS" and s["rule_category_id"] == suggested["Food & Dining"]
    assert s["others"] == 3, "the other 2 Campus Foods rows and your snack"


def test_suggest_offers_a_new_keyword_for_a_new_place(client, suggested, campus):
    s = suggest(client, campus["AFRESH MARKETPLACE LIMITEKINGSTON"]["description"], suggested["Groceries"])
    assert s["keyword"] == "AFRESH" and s["rule_id"] is None


def test_suggest_never_learns_from_fees(client, suggested, campus):
    assert suggest(client, "POS Tx Fee", suggested["Shopping"])["keyword"] is None


def test_remember_moves_the_keyword_and_apply_changes_the_others(client, api, suggested, campus):
    tx = campus["CAMPUS FOODS & ESSENTIALSKINGSTON"]
    client.patch(f"/transaction/{tx['id']}", json={"category_id": suggested["Groceries"]})

    r = client.post("/rules/remember", json={"keyword": "campus foods", "category_id": suggested["Groceries"]})
    assert r.json()["category_id"] == suggested["Groceries"]
    assert [x["keyword"] for x in client.get("/rules/").json()].count("CAMPUS FOODS") == 1, "moved, not copied"

    r = client.post("/rules/apply", json={"keyword": "CAMPUS FOODS", "category_id": suggested["Groceries"], "exclude_id": tx["id"]})
    assert r.json()["updated"] == 3
    assert all(t["category_id"] == suggested["Groceries"] for t in client.get("/transaction/?q=campus").json())

    (row,) = api.preview_csv(account_id(api), ["2026-10-02,POS CAMPUS FOODS & ESSENTIALSKINGSTON,-800"])
    assert row["category_id"] == suggested["Groceries"], "and next import follows"


def test_remember_creates_a_keyword_if_new(client, suggested):
    r = client.post("/rules/remember", json={"keyword": "AFRESH", "category_id": suggested["Groceries"]})
    assert r.status_code == 200 and r.json()["keyword"] == "AFRESH"
    assert client.post("/rules/remember", json={"keyword": "AFRESH", "category_id": 9999}).status_code == 404
