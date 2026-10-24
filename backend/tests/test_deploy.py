"""Settings that matter once the app is on the internet."""
import pytest

from conftest import PASSWORD
from database import postgres_url


@pytest.mark.parametrize("given, used", [
    ("postgresql://me:pw@ep-cool-1.us-east-1.aws.neon.tech/neondb?sslmode=require",
     "postgresql+psycopg://me:pw@ep-cool-1.us-east-1.aws.neon.tech/neondb?sslmode=require"),
    ("postgres://me:pw@host/db", "postgresql+psycopg://me:pw@host/db"),
    ("postgresql+psycopg://me:pw@host/db", "postgresql+psycopg://me:pw@host/db"),
    ("sqlite:///database.db", "sqlite:///database.db"),
])
def test_neon_addresses_get_the_right_driver(given, used):
    assert postgres_url(given) == used


def test_answers_are_never_cached(client, anonymous):
    for browser, path in [(client, "/account/"), (client, "/auth/me"), (anonymous, "/auth/me")]:
        assert browser.get(path).headers["cache-control"] == "no-store"


def test_the_cookie_is_https_only_on_vercel(anonymous, monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    login = anonymous.post("/auth/login", json={"username": "tester", "password": PASSWORD})
    assert "secure" in login.headers["set-cookie"].lower()
