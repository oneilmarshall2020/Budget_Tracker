# Logins and accounts

Everyone who uses the app has their own login, and only ever sees their own data:
accounts, categories, keywords, budgets, imports and transactions. Asking for someone
else's (even by guessing an id) gets "not found".

## How it works

| Piece | Where | What it does |
|---|---|---|
| `users` table | `models.py` (`User`) | One row per person: username, a scramble (hash) of the password, lockout info |
| `login_session` table | `models.py` (`LoginSession`) | One row per logged-in browser, holding a scramble of its token |
| `user_id` column | the six data tables | Who each row belongs to |
| `auth.py` | | Hashing passwords (Argon2), starting and ending sessions, and `CurrentUser`: "who is asking?" |
| `routers/auth.py` | | `/auth/signup`, `/auth/login`, `/auth/logout`, `/auth/me`, `/auth/settings` |
| `demo.py`, `routers/demo.py` | | Demo accounts (below): `/demo/start`, `/demo/end`, `/demo/sample-statement.pdf` |
| `users.py` | | Terminal commands for managing logins (below) |

Every endpoint that touches data takes `user: CurrentUser`. No valid login cookie means
a `401`, and the page shows the login screen.

## Terminal commands

From the `backend` folder, venv active:

```bash
python users.py list                  # who has an account, and how much data each has
python users.py claim                 # make the data from before logins existed yours
python users.py create                # make an account without the sign-up code
python users.py set-password NAME     # new password for NAME (also unlocks it and logs it out everywhere)
python users.py remove-old-demos      # delete demo accounts older than a week now (also happens by itself)
```

Forgot your password? There's no email reset, so use `set-password`. Once deployed, run it
with `DATABASE_URL` set to the deployed database (see the deploy notes).

## Settings (environment variables)

| Variable | Locally | Deployed |
|---|---|---|
| `SIGNUP_CODE` | leave unset: anyone can sign up | set it: new accounts need this code. Share it with people you want to let in |
| `SECURE_COOKIES` | leave unset | nothing to do: on Vercel the login cookie is https-only automatically |
| `DEMO_CODE` | leave unset: "Try the demo" shows for anyone | set it to switch demos on. Unset = no demos on the internet |
| `FEEDBACK_URL` | optional | optional: where the demo's **Give feedback** button goes, e.g. a Google Form |

## Rules worth knowing

- Usernames: 2 to 30 characters, letters, numbers, `.` `_` `-`. Capitals don't matter.
- Passwords: at least 8 characters. Stored only as an Argon2 hash.
- 5 wrong passwords in a row lock that account for 15 minutes.
- A login lasts 30 days on a device, or until you log out.

## Demo accounts

So people can try Ledger without typing in anything real, and without you ever seeing
their money.

- **Try the demo** (on the login page) makes an account called `demo-` plus six letters and
  numbers, and logs straight in. Nobody can sign up with a name starting `demo-`, and a demo
  has no password, so nobody can log into one from another browser.
- It starts with two made-up NCB accounts, the suggested categories and keywords, budgets,
  and everyday spending for last month and this month (`EVERYDAY` and `BUDGETS` in `demo.py`).
- A blue banner says it's a demo, and has **Sample statement** (an invented September 2026
  statement to try the import with) and **Give feedback** (if `FEEDBACK_URL` is set).
- **End demo** (where **Log out** usually is) deletes it and everything in it, there and then.
  Otherwise demos older than 7 days (`DEMO_DAYS`) are deleted whenever someone starts a new
  one. At most 200 (`MAX_DEMOS`) can exist at once, so nobody can fill your database.
- `python users.py list` counts demos separately from real accounts.

Where the button shows:

| `DEMO_CODE` | On your laptop | Deployed |
|---|---|---|
| not set | on the login page, below the login box | nowhere: demos are off |
| set | only with the link | only with the link `https://<your site>/?demo=<the code>`, above the login box |

Someone who has the link can make demos, so it's fine to share it with the people you want
feedback from. To stop it working, change `DEMO_CODE` (and redeploy).
