# Deploying: Neon + Vercel, free

```
browser ──> your site (Vercel, frontend/)  ──/api/...──>  your backend (Vercel, backend/)  ──>  Neon (Postgres)
```

- **Neon** keeps the database. The free plan has no expiry and needs no card.
- **Vercel** runs two projects from your GitHub repo: the **site** (React, built by Vite) and the
  **backend** (FastAPI). Every `git push` redeploys both.
- The site forwards every `/api/...` call to the backend (`frontend/vercel.json`), just like Vite
  does on your laptop. To the browser it's one site, so the login cookie works the same.

Do the parts in order. Each one ends with a check.

## 0. Before you start

- [ ] The login update works locally: you can log in at `localhost:5173`.
- [ ] `python -m pytest` passes.
- [ ] Everything is committed and pushed to GitHub (`git status` is clean).

## 1. Neon: the database

1. Sign up at [neon.com](https://neon.com) (signing in with GitHub is fine).
2. Create a project. Name it `budget`. For the region pick **AWS US East 1 (N. Virginia)**,
   the closest to Vercel's default region (Washington, D.C.), so every query is a short hop.
3. Click **Connect**. Copy the connection string. It looks like
   `postgresql://neondb_owner:...@ep-...-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require`.

**This address is the key to everyone's data.** Keep it in a password manager. Never commit it,
never paste it in a chat. If it ever leaks, reset the role's password in Neon and update Vercel.

## 2. Copy your data into Neon (once)

Backend stopped, from the `backend` folder, venv active. Use **single quotes** (zsh would
otherwise trip over the `?` and `&` in the address):

```bash
DATABASE_URL='paste the Neon address here' python copy_to_postgres.py
```

Check: it prints `Copied:` with your counts (transactions, accounts, keywords...) and `Done.`
Your `database.db` isn't changed. From now on the deployed site holds your real data, and
`database.db` is your local playground for trying things.

## 3. Vercel: the backend

1. Sign up at [vercel.com](https://vercel.com) with GitHub (the free **Hobby** plan).
2. **Add New… → Project**, then **Import** next to your `Budget_Tracker` repo
   (give Vercel access to it if asked).
3. **Project Name**: something like `oj-budget-api`. Your backend's address becomes
   `https://oj-budget-api.vercel.app`, so pick a name you like.
4. **Root Directory**: click **Edit**, choose `backend`. Vercel should detect FastAPI.
5. **Environment Variables**, add two:

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | the Neon address |
   | `SIGNUP_CODE` | a code you make up for friends, e.g. `mango-river-42` |

6. **Deploy**.

Check, in your browser:
- `https://<backend name>.vercel.app/` shows `{"message":"Hello from the budget API"}`
- `https://<backend name>.vercel.app/auth/settings` shows `{"signup_needs_code":true}`

## 4. Point the site at the backend

Open `frontend/vercel.json` and replace `REPLACE-WITH-YOUR-BACKEND` with your backend's
name, so it reads e.g. `https://oj-budget-api.vercel.app/$1`. Then:

```bash
git add frontend/vercel.json
git commit -m "Point the site at the deployed backend"
git push
```

## 5. Vercel: the site

1. **Add New… → Project**, and import the **same repo again**.
2. **Project Name**: e.g. `oj-budget` (your app's address: `https://oj-budget.vercel.app`).
3. **Root Directory**: **Edit**, choose `frontend`. Vercel detects Vite and fills in
   `npm run build` and `dist` by itself.
4. No environment variables. **Deploy**.

Check: open `https://<site name>.vercel.app`, log in with your username and password, and
your data is there.

## 6. Final checks

- [ ] Log a test expense, refresh, delete it.
- [ ] On your phone, open the site and log in. Add it to your home screen
      (Safari: Share → Add to Home Screen) and it opens like an app.
- [ ] In a private window, try to create an account **without** the code: refused.
      With the code: works, and the new account starts empty.

## Everyday changes from now on

1. Change code on your laptop, try it locally.
2. `python -m pytest`
3. `git commit` and `git push`. Both projects redeploy in about a minute. New migrations run
   by themselves when the backend starts.

Changed an environment variable in Vercel? It only applies to new deployments: open the
project's **Deployments**, then **⋯ → Redeploy** on the latest one.

Forgot a password on the deployed site:

```bash
DATABASE_URL='the Neon address' python users.py set-password NAME
```

## If something goes wrong

| What you see | Likely cause |
|---|---|
| The backend's deployment fails | Open it in Vercel and read the **Build Logs**. A missing package belongs in `requirements.txt` |
| The backend shows `500` / `FUNCTION_INVOCATION_FAILED` | Backend project → **Logs** shows why. If it mentions `DATABASE_URL`, the variable is missing or misspelled: fix it, then **Redeploy** |
| The site says "Can't reach the server" | `frontend/vercel.json` has the wrong backend name, or wasn't pushed. Check the backend address works on its own |
| You log in but land back on the login screen | Open the **site's** address, not the backend's. The cookie belongs to the site |
| The first visit after a quiet few hours takes a few seconds | Normal: Neon and Vercel were asleep and wake on the first request |
| You need to look at what the backend did | Backend project → **Logs**. SQL is never printed there (it would include everyone's data) |
