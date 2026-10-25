# Testing the backend

## Run the tests

From the `backend` folder, venv active:

```bash
pip install -r requirements.txt   # once (pytest is in there)
python -m pytest                  # run everything (about 20 seconds)
```

You'll see a dot per test and then `181 passed`. Other handy forms:

| Command | Runs |
|---|---|
| `pytest -q` | everything, less output |
| `pytest tests/test_reports.py` | one file |
| `pytest -k undo` | every test with "undo" in its name |
| `pytest -x` | stop at the first failure |

**Run them before every commit**, and after every change, small ones included.

## Your data is safe

Each test gets its own brand-new database in a temporary folder (see `tests/conftest.py`).
Tests never touch your real `database.db`, and one test can't affect another. Each one also
starts logged in as a made-up user called `tester`.

## What's tested

| File | Covers |
|---|---|
| `test_setup.py` | accounts, categories, budgets, and what deleting does |
| `test_transactions.py` | logging by hand, edits, search, the "already imported?" check |
| `test_statement_import.py` | reading PDFs/CSVs, the review, saving, re-importing, undo |
| `test_reports.py` | monthly and yearly numbers, checked against the raw transactions |
| `test_keywords.py` | keywords, the suggested set, learning on import and on edit |
| `test_matching.py` | closest-date pairing, pending charges, your transfers, refunds |
| `test_parser.py` | the NCB reader on text laid out like a real statement |
| `test_migrations.py` | new databases, old databases, your pre-login data going to `owner`, backups, models matching migrations |
| `test_auth.py` | signing up, logging in and out, lockouts, sign-up codes, the cookie, every endpoint needing a login |
| `test_isolation.py` | two people in one app: nobody can see, change or point at anyone else's data |
| `test_deploy.py` | settings for the internet: Neon addresses, no caching of private answers, https-only cookies |
| `test_demo.py` | demo accounts: when they're allowed, what's in them, the sample statement importing cleanly, deleting them |

`tests/fixtures/` holds a test NCB statement (plus a locked and a "misread" version), with
rows copied from a real statement and names taken out. `make_mock_statement.py` rebuilds them
(`pip install reportlab` first). They're only for tests: the demo's sample statement,
`samples/ncb_sample_statement.pdf`, is a separate, fully invented one (`samples/make_sample_statement.py`).

## Reading a failure

This is real output, from flipping one minus sign in `routers/summaries.py` so refunds
got added to spending instead of taken off:

```
>       assert monthly["spending"] == report["spending"], "refunds come off spending"
E       AssertionError: refunds come off spending
E       assert 21709.4 == 18627.32
FAILED tests/test_reports.py::test_income_spending_and_net
```

The `>` line is the check that failed. The message says what should have happened, and the
two numbers are what the app said versus what's right: 3,082.08 too much, which is the
statement's refunds counted twice over. Three tests went red for that one sign.

## Writing a test

A test is a function whose name starts with `test_`, in a file whose name starts with `test_`.
Ask for fixtures by naming them as parameters, then `assert` what should be true:

```python
def test_a_budget_needs_a_positive_amount(client, api):
    food = api.category("Food")
    r = client.post("/budget/", json={"category_id": food["id"], "year": 2026, "month": 9, "amount": -5})
    assert r.status_code == 422
```

Fixtures you can ask for (all in `conftest.py`):
- `client`: the API, with a fresh database, logged in as `tester`.
- `stranger`: a second person on the same database, logged in as `stranger`.
- `anonymous`: a browser that hasn't logged in.
- `api`: shortcuts like `api.account()`, `api.category("Food")`, `api.log(...)`, `api.preview_pdf(...)`, `api.import_csv(...)`.
- `september`: an account, Food and Salary, a budget, a logged lunch and an August snack.
- `imported`: `september` plus the test statement imported.

**When you find a bug, write a test that fails first**, then fix the code until it passes.
That bug can never come back without a red test telling you.

## Testing by hand

- **Built in, nothing to install:** with the backend running, open http://127.0.0.1:8000/docs.
  Every endpoint is listed. Click one, **Try it out**, fill it in, **Execute**.
  Log in first: run `POST /auth/login` with your username and password. The page keeps the
  login cookie, so every other endpoint works after that.
- **Bruno** (https://www.usebruno.com, free) saves your requests as files you can commit:
  1. Install it and choose **Create Collection**. Name it "Budget API" and save it in a new
     `Budget_Tracker/bruno` folder.
  2. **Environments → Create**, call it "local", and add a variable `baseUrl` = `http://127.0.0.1:8000`.
     Pick "local" in the top-right.
  3. **New Request**: `POST {{baseUrl}}/auth/login` with the JSON body
     `{"username": "you", "password": "..."}`, then Send. Bruno keeps the cookie for the requests after it.
     Then `GET {{baseUrl}}/account/`, Send.
  4. For a JSON body, e.g. `POST {{baseUrl}}/categories/`: open **Body → JSON** and enter
     `{"name": "Food", "kind": "expense"}`.
  5. For a statement preview: `POST {{baseUrl}}/statement/preview`, **Body → Multipart Form**,
     add `account_id` (text) and `file` (file), and pick a statement.
