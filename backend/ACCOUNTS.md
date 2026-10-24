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
```

Forgot your password? There's no email reset, so use `set-password`. Once deployed, run it
with `DATABASE_URL` set to the deployed database (see the deploy notes).

## Settings (environment variables)

| Variable | Locally | Deployed |
|---|---|---|
| `SIGNUP_CODE` | leave unset: anyone can sign up | set it: new accounts need this code. Share it with people you want to let in |
| `SECURE_COOKIES` | leave unset | nothing to do: on Vercel the login cookie is https-only automatically |

## Rules worth knowing

- Usernames: 2 to 30 characters, letters, numbers, `.` `_` `-`. Capitals don't matter.
- Passwords: at least 8 characters. Stored only as an Argon2 hash.
- 5 wrong passwords in a row lock that account for 15 minutes.
- A login lasts 30 days on a device, or until you log out.
