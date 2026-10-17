"""Importing statements: reading the PDF/CSV, the review, saving, re-importing and undoing.

The test statement (fixtures/ncb_sept.pdf) is a made-up NCB statement laid out like the
real one: 39 rows from Sep 3 to Sep 30, with fees, reversals, ELink transfers and a salary.
"""


def find(rows, start):
    return next(r for r in rows if r["description"].startswith(start))


# ---------------------------------------------------------------- reading the file
def test_locked_pdf_asks_for_its_password(api):
    account = api.account()
    r = api.preview_pdf(account["id"], "ncb_sept_locked.pdf")
    assert r.status_code == 400 and "password" in r.json()["detail"]
    assert api.preview_pdf(account["id"], "ncb_sept_locked.pdf", password="0427").status_code == 200


def test_preview_reads_every_row_with_no_problems(api):
    r = api.preview_pdf(api.account()["id"])
    assert r.status_code == 200
    assert len(r.json()["rows"]) == 39
    assert r.json()["problems"] == []


def test_a_misread_amount_shows_up_as_problems(api):
    r = api.preview_pdf(api.account()["id"], "ncb_sept_tampered.pdf")
    assert len(r.json()["problems"]) == 2, "the running balance and the page total both disagree"


def test_fees_get_their_own_category(api):
    rows = api.preview_pdf(api.account()["id"]).json()["rows"]
    fees_id = api.categories()["Bank Fees"]  # created automatically
    fee_rows = [r for r in rows if "Tx Fee" in r["description"]]
    assert len(fee_rows) == 22
    assert all(r["category_id"] == fees_id and r["type"] == "expense" for r in fee_rows)


def test_types_are_guessed_from_the_description(api):
    rows = api.preview_pdf(api.account()["id"]).json()["rows"]
    assert all(r["type"] == "refund" for r in rows if r["description"] == "POSREV")
    trf_to, trf_from = find(rows, "ELink TRF-TO"), find(rows, "ELink TRF-FROM")
    assert (trf_to["type"], trf_to["flag"]) == ("expense", "review")
    assert (trf_from["type"], trf_from["flag"]) == ("income", "review")
    payroll = find(rows, "PAYROLL")
    assert payroll["type"] == "income" and payroll["date"] == "2026-09-25", "the year comes from the statement"


def test_descriptions_are_tidied(api):
    rows = api.preview_pdf(api.account()["id"]).json()["rows"]
    assert not any(r["description"].startswith("POS ") and "Tx Fee" not in r["description"] for r in rows)
    assert find(rows, "SOCIAL")["description"] == "SOCIAL WELFARE CANTEEN 12 GIBRA", "extra spaces collapsed"


def test_your_logged_lunch_is_matched_not_counted_twice(api, september):
    rows = api.preview_pdf(september["account"]["id"]).json()["rows"]
    juici = find(rows, "JUICI")
    assert juici["flag"] == "match" and not juici["include"]
    assert "Lunch at Juici" in juici["note"]


def test_places_you_categorized_before_are_remembered(api, september):
    rows = api.preview_pdf(september["account"]["id"]).json()["rows"]
    campus = [r for r in rows if r["description"].startswith("CAMPUS FOODS")]
    assert len(campus) == 3
    assert all(r["category_id"] == september["food"]["id"] for r in campus), "learned from the August snack"


# ---------------------------------------------------------------- saving
def test_confirm_saves_the_ticked_rows(imported):
    created = imported["result"]["created"]
    assert len(created) == 38, "39 rows minus the lunch you already logged"
    assert imported["result"]["skipped"] == 0
    assert all(t["source"] == "statement" and t["import_id"] == imported["import_id"] for t in created)
    transfer = next(t for t in created if "TRF-FROM" in t["description"])
    assert transfer["type"] == "transfer" and transfer["category_id"] is None


def test_confirming_twice_saves_nothing_new(api, imported):
    again = api.confirm(imported["account"]["id"], imported["rows"])
    assert again["created"] == [] and again["skipped"] == 38
    assert again["import_id"] is None
    assert len(api.client.get("/statement/imports").json()) == 1, "an import that saved nothing isn't listed"


def test_previewing_it_again_shows_everything_as_already_there(api, imported):
    rows = api.preview_pdf(imported["account"]["id"]).json()["rows"]
    flags = [r["flag"] for r in rows]
    assert flags.count("duplicate") == 38 and flags.count("match") == 1
    assert not any(r["include"] for r in rows)
    assert find(rows, "HI-LO")["note"] == "Already imported from ncb_sept.pdf"


# ---------------------------------------------------------------- undo
def test_imports_are_listed_with_their_details(client, imported):
    (batch,) = client.get("/statement/imports").json()
    assert batch["file_name"] == "ncb_sept.pdf"
    assert batch["row_count"] == batch["remaining"] == 38
    assert (batch["first_date"], batch["last_date"]) == ("2026-09-03", "2026-09-30")


def test_undo_removes_only_that_imports_rows(client, imported):
    one = next(t for t in client.get("/transaction/?year=2026&month=9").json() if t["import_id"] == imported["import_id"])
    client.delete(f"/transaction/{one['id']}")
    assert client.get("/statement/imports").json()[0]["remaining"] == 37

    r = client.delete(f"/statement/imports/{imported['import_id']}")

    assert r.status_code == 200 and r.json()["deleted"] == 37
    left = client.get("/transaction/?year=2026&month=9").json()
    assert [t["description"] for t in left] == ["Lunch at Juici"], "your own entry is never touched"
    assert client.get("/statement/imports").json() == []
    assert client.delete(f"/statement/imports/{imported['import_id']}").status_code == 404


def test_after_undo_the_statement_can_be_imported_again(api, imported):
    api.client.delete(f"/statement/imports/{imported['import_id']}")
    rows = api.preview_pdf(imported["account"]["id"]).json()["rows"]
    assert len(api.confirm(imported["account"]["id"], rows)["created"]) == 38


# ---------------------------------------------------------------- CSV and other files
def test_csv_import(api, september):
    rows_and_problems = api.client.post(
        "/statement/preview",
        data={"account_id": september["account"]["id"]},
        files={"file": ("export.csv", (
            "date,description,amount,type,category\n"
            "2026-10-01,Groceries at Hi-Lo,-4500,,Food\n"
            "2026-10-02,Side gig,12000,,Salary\n"
            "2026-10-03,To my JN account,-3000,transfer,\n"
            "not-a-date,Broken row,-10,,\n"
            "2026-10-04,Netflix,-1600,,\n"
        ).encode(), "text/csv")},
    ).json()
    rows, problems = rows_and_problems["rows"], rows_and_problems["problems"]
    assert len(rows) == 4 and len(problems) == 1, "the broken row is skipped and reported"
    assert (rows[0]["type"], rows[0]["category_id"]) == ("expense", september["food"]["id"]), "category column used"
    assert (rows[1]["type"], rows[1]["category_id"]) == ("income", september["salary"]["id"]), "positive = income"
    assert rows[2]["type"] == "transfer", "a type column wins over the guess"


def test_other_file_types_are_rejected(client, api):
    r = client.post("/statement/preview", data={"account_id": api.account()["id"]},
                    files={"file": ("notes.txt", b"hello", "text/plain")})
    assert r.status_code == 400


def test_pdf_from_a_bank_without_a_reader_explains_itself(api):
    jn = api.account(nickname="JN", bank="JN Bank", account_type="chequing", last_four="7777")
    r = api.preview_pdf(jn["id"])
    assert r.status_code == 400 and "no PDF reader" in r.json()["detail"]
