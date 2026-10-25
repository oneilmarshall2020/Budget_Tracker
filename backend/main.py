from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from migrate import run_migrations
from routers import account, auth, budget, categories, demo, rules, statements, summaries, transaction


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()  # bring the tables up to date (backs up first if anything changes)
    yield


app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def never_cache(request: Request, call_next):
    """Every answer holds someone's private data, so no browser or CDN may keep a copy."""
    response = await call_next(request)
    response.headers.setdefault("Cache-Control", "no-store")
    return response


# No CORS settings needed: the page always calls the backend through its own address
# (/api/...), and Vite (locally) or the host (once deployed) passes those calls on to us.
# To the browser it's all one site, which is also what lets the login cookie work.

app.include_router(auth.router)
app.include_router(demo.router)
app.include_router(account.router)
app.include_router(categories.router)
app.include_router(rules.router)
app.include_router(budget.router)
app.include_router(transaction.router)
app.include_router(statements.router)
app.include_router(summaries.router)


@app.get("/")
def read_root():
    return {"message": "Hello from the budget API"}
