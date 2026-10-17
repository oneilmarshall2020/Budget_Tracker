from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from migrate import run_migrations
from routers import account, budget, categories, rules, statements, summaries, transaction


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()  # bring the tables up to date (backs up first if anything changes)
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
