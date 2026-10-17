"""Import matching: things you logged by hand, pending charges, your own transfers, refunds."""
import pytest


@pytest.fixture
def setup(api):
    """Suggested categories, plus two of your accounts: Savings (9988) and Chequing (1234)."""
    api.client.post("/rules/suggested")
    savings = api.account(nickname="Savings", last_four="9988")
    chequing = api.account(nickname="Chequing", last_four="1234", account_type="chequing")
    names = {v: k for k, v in api.categories().items()}
    return {"savings": savings["id"], "chequing": chequing["id"], "name": names}


def find(rows, text, date=None):
    return next(r for r in rows if text in r["description"] and (date is None or r["date"] == date))


# ---------------------------------------------------------------- logged by hand: closest date first
def test_identical_purchases_pair_with_the_closest_date(api, setup):
    api.log(1120, "2026-09-04", "Juici lunch")
    rows = api.preview_csv(setup["chequing"], [
        "2026-09-01,POS JUICI PATTIES - UWI MONA,-1120",
        "2026-09-04,POS JUICI PATTIES - UWI MONA,-1120",
    ])
    assert find(rows, "JUICI", "2026-09-04")["flag"] == "match", "your Sep 4 entry pairs with the Sep 4 row"
    assert find(rows, "JUICI", "2026-09-01")["include"], "the Sep 1 lunch is still imported"


def test_month_ends_stay_in_the_right_month(api, setup):
    api.log(900, "2026-10-01", "KFC with friends")
    rows = api.preview_csv(setup["chequing"], [
        "2026-09-29,POS KFC HALF WAY TREE,-900",
        "2026-10-01,POS KFC HALF WAY TREE,-900",
    ])
    assert find(rows, "KFC", "2026-10-01")["flag"] == "match"
    api.confirm(setup["chequing"], rows)
    sep = [t for t in api.client.get("/transaction/?year=2026&month=9").json() if "KFC" in t["description"]]
    oct_ = [t for t in api.client.get("/transaction/?year=2026&month=10").json() if "KFC" in t["description"]]
    assert len(sep) == 1 and len(oct_) == 1


def test_matched_entries_get_linked_to_the_cards_account(api, setup):
    lunch = api.log(1120, "2026-09-04", "Juici lunch")
    result = api.confirm(setup["chequing"], api.preview_csv(setup["chequing"], ["2026-09-04,POS JUICI PATTIES,-1120"]))
    assert result["linked"] == 1
    assert api.client.get(f"/transaction/{lunch['id']}").json()["account_id"] == setup["chequing"]


# ---------------------------------------------------------------- pending charges
def test_a_renamed_pending_charge_is_flagged(api, setup):
    api.import_csv(setup["chequing"], ["2026-07-01,UBER * PENDING help.uber.co,-887.22"])
    rows = api.preview_csv(setup["chequing"], [
        "2026-07-02,UBER *TRIP help.uber.com,-887.22",
        "2026-07-02,POS KFC HALF WAY TREE,-887.22",
    ])
    uber, kfc = find(rows, "UBER"), find(rows, "KFC")
    assert uber["flag"] == "possible" and not uber["include"] and "UBER * PENDING" in uber["note"]
    assert kfc["flag"] is None and kfc["include"], "a different place with the same amount is not flagged"


# ---------------------------------------------------------------- transfers between your accounts
def test_account_digits_mark_a_transfer_right_away(api, setup):
    (row,) = api.preview_csv(setup["chequing"], ["2026-06-08,ELink TRF-FROM SAVINGS 9988,5000"])
    assert row["type"] == "transfer" and row["flag"] == "transfer"
    assert "Savings (ending 9988)" in row["note"]
    assert row["category_id"] is None and row["keyword"] is None


def test_the_second_side_pairs_with_the_first_and_fixes_it(api, setup):
    api.import_csv(setup["savings"], ["2026-06-10,ELink TRF-TO CHQ,-3000"])  # imported as an expense
    first = find(api.client.get("/transaction/?q=TRF-TO CHQ").json(), "TRF-TO CHQ")
    assert first["type"] == "expense"

    rows = api.preview_csv(setup["chequing"], [
        "2026-06-11,ELink TRF-FROM SAV,3000",
        "2026-06-12,ELink TRF-TO SOMEONE ELSE,-2000",
    ])
    second = find(rows, "TRF-FROM SAV")
    assert second["type"] == "transfer" and second["pair_id"] == first["id"] and "Savings" in second["note"]
    assert find(rows, "SOMEONE ELSE")["type"] == "expense", "a transfer to someone else stays a payment"

    assert api.confirm(setup["chequing"], rows)["transfers_paired"] == 1
    first = api.client.get(f"/transaction/{first['id']}").json()
    assert first["type"] == "transfer" and first["category_id"] is None


def test_same_amount_in_and_out_without_transfer_words_is_not_a_transfer(api, setup):
    api.import_csv(setup["chequing"], ["2026-06-15,POS HI-LO FOOD STORES,-7000"])
    (row,) = api.preview_csv(setup["savings"], ["2026-06-15,PAYROLL DEP EMPLOYER SALARY,7000"])
    assert row["type"] == "income" and row["pair_id"] is None


def test_transfers_count_as_neither_income_nor_spending(api, setup):
    api.import_csv(setup["savings"], ["2026-06-10,ELink TRF-TO CHQ,-3000", "2026-06-15,PAYROLL DEP EMPLOYER SALARY,7000"])
    api.import_csv(setup["chequing"], ["2026-06-11,ELink TRF-FROM SAV,3000", "2026-06-15,POS HI-LO FOOD STORES,-2000"])
    june = api.client.get("/summary/2026/6").json()
    assert (june["income"], june["spending"]) == (7000, 2000)


# ---------------------------------------------------------------- refunds
def test_refunds_take_the_category_of_the_purchase_they_undo(api, setup):
    name = setup["name"]
    api.import_csv(setup["chequing"], ["2026-04-28,APPLE.COM/BILL 866-712-7753,-1661.20"])
    rows = api.preview_csv(setup["chequing"], [
        "2026-05-02,POSREV,1661.20",
        "2026-05-03,AMAZON.COM ORDER 123,-5000",
        "2026-05-03,POS Tx Fee,-112.50",
        "2026-05-10,POSREV,5000",
        "2026-05-10,POSREV,112.50",
        "2026-05-11,POSREV,5000",
        "2026-05-12,POSREV,999.99",
    ])
    apple, amazon, fee, amazon_again, unknown = [r for r in rows if r["description"] == "POSREV"]

    assert name[apple["category_id"]] == "Subscriptions", "from last month's import"
    assert apple["category_source"] == "reversal" and apple["reverses"] == "APPLE.COM/BILL 866-712-7753 (Apr 28)"
    assert name[amazon["category_id"]] == "Shopping" and amazon["reverses"] == "AMAZON.COM ORDER 123 (May 3)"
    assert name[fee["category_id"]] == "Bank Fees"
    assert amazon_again["category_id"] is None, "a purchase can only be refunded once"
    assert unknown["category_id"] is None, "no matching purchase: you pick"

    api.confirm(setup["chequing"], rows)
    may = api.client.get("/summary/2026/5").json()
    assert not any(x["category"] == "Shopping" for x in may["spending_by_category"]), "refund nets Shopping to zero"
