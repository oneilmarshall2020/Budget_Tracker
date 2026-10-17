"""Logging transactions by hand, editing them, searching, and the 'already imported?' check."""


def test_type_defaults_to_expense_and_source_to_manual(api):
    tx = api.log(1580, "2026-09-21", "Lunch at Juici")
    assert tx["type"] == "expense"
    assert tx["source"] == "manual"


def test_amount_must_be_positive(client):
    assert client.post("/transaction/", json={"amount": 0, "date": "2026-08-20", "description": "x"}).status_code == 422


def test_income_cant_use_a_spending_category(client, api):
    food = api.category("Food")
    r = client.post("/transaction/", json={"amount": 100, "date": "2026-09-02", "description": "Pay",
                                           "type": "income", "category_id": food["id"]})
    assert r.status_code == 400


def test_transfers_drop_their_category(api):
    food = api.category("Food")
    move = api.log(100, "2026-09-02", "Move", type="transfer", category_id=food["id"])
    assert move["category_id"] is None


def test_editing_into_a_mismatched_category_is_rejected(client, api):
    food = api.category("Food")
    move = api.log(100, "2026-09-02", "Move", type="transfer")
    r = client.patch(f"/transaction/{move['id']}", json={"type": "income", "category_id": food["id"]})
    assert r.status_code == 400


def test_an_empty_description_in_an_edit_is_ignored(client, api):
    move = api.log(100, "2026-09-02", "Move", type="transfer")
    r = client.patch(f"/transaction/{move['id']}", json={"description": None})
    assert r.status_code == 200 and r.json()["description"] == "Move"


def test_month_list_is_newest_first(client, imported):
    sept = client.get("/transaction/?year=2026&month=9").json()
    assert len(sept) == 39, "38 imported + the lunch you logged"
    dates = [t["date"] for t in sept]
    assert dates == sorted(dates, reverse=True)


# ---------------------------------------------------------------- search
def test_search_covers_every_month(client, imported):
    found = client.get("/transaction/?q=campus").json()
    assert len(found) == 4, "3 Campus Foods rows in September + the snack in August"
    assert all("CAMPUS" in t["description"].upper() for t in found)


def test_search_can_be_limited_to_a_month(client, imported):
    assert len(client.get("/transaction/?q=campus&year=2026&month=9").json()) == 3
    assert client.get("/transaction/?q=juici&year=2026&month=8").json() == []


def test_search_ignores_case_and_commas_in_amounts(client, imported):
    assert [t["description"] for t in client.get("/transaction/?q=LUNCH").json()] == ["Lunch at Juici"]
    assert len(client.get("/transaction/?q=1,580").json()) == 1


def test_search_with_no_match_is_empty(client, imported):
    assert client.get("/transaction/?q=zzz-nothing").json() == []


# ---------------------------------------------------------------- already imported?
def test_similar_finds_an_imported_row_close_by(client, api):
    account = api.account()
    api.import_csv(account["id"], ["2026-09-04,POS JUICI PATTIES - UWI MONA,-1120"])

    def similar(amount, date, tx_type="expense"):
        return client.get(f"/transaction/similar?amount={amount}&date={date}&type={tx_type}").json()

    assert [t["description"] for t in similar(1120, "2026-09-05")] == ["JUICI PATTIES - UWI MONA"]
    assert similar(1120, "2026-09-10") == [], "a week later: different purchase"
    assert similar(1120.50, "2026-09-04") == [], "different amount"
    assert similar(1120, "2026-09-04", "income") == [], "different type"


def test_similar_ignores_entries_you_logged_yourself(client, api):
    api.log(300, "2026-09-25", "Campus Foods snack")
    assert client.get("/transaction/similar?amount=300&date=2026-09-25&type=expense").json() == []
