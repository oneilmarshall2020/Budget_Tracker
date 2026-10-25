"""Logging in: accounts, passwords, sessions, lockouts and sign-up codes."""
import datetime
import re

import pytest
from sqlmodel import Session, select

import auth
import database
import users
from conftest import PASSWORD, sign_up
from main import app
from models import LoginSession, User


def log_in(browser, username="tester", password=PASSWORD):
    return browser.post("/auth/login", json={"username": username, "password": password})


def stored_user(username) -> User:
    with Session(database.engine) as session:
        return session.exec(select(User).where(User.username == username)).one()


# ---------------------------------------------------------------- signing up
def test_signing_up_logs_you_straight_in(anonymous):
    assert anonymous.get("/auth/me").status_code == 401
    me = sign_up(anonymous, "newcomer")
    assert anonymous.get("/auth/me").json() == me == {"id": me["id"], "username": "newcomer", "is_demo": False}


def test_usernames_ignore_capitals_and_are_unique(anonymous):
    assert sign_up(anonymous, "  Oj ")["username"] == "oj"
    r = anonymous.post("/auth/signup", json={"username": "OJ", "password": PASSWORD})
    assert r.status_code == 400 and "taken" in r.json()["detail"]


@pytest.mark.parametrize("username, password", [
    ("o", PASSWORD),               # too short
    ("has space", PASSWORD),       # not allowed characters
    ("fine.name", "short"),        # password under 8 characters
])
def test_bad_usernames_and_short_passwords_are_refused(anonymous, username, password):
    r = anonymous.post("/auth/signup", json={"username": username, "password": password})
    assert r.status_code == 422


def test_the_password_is_never_stored_or_sent_back(anonymous):
    me = sign_up(anonymous, "secretive", password="my secret phrase")
    assert set(me) == {"id", "username", "is_demo"}
    stored = stored_user("secretive").password_hash
    assert "my secret phrase" not in stored and stored.startswith("$argon2")


def test_a_sign_up_code_keeps_strangers_out(anonymous, monkeypatch):
    monkeypatch.setenv("SIGNUP_CODE", "mango-season")
    assert anonymous.get("/auth/settings").json()["signup_needs_code"] is True
    for code in (None, "wrong"):
        r = anonymous.post("/auth/signup", json={"username": "friend", "password": PASSWORD, "signup_code": code})
        assert r.status_code == 403
    sign_up(anonymous, "friend", signup_code=" mango-season ")


def test_no_code_needed_when_none_is_set(anonymous):
    assert anonymous.get("/auth/settings").json()["signup_needs_code"] is False


# ---------------------------------------------------------------- logging in and out
def test_log_in_and_out(anonymous):
    r = log_in(anonymous, "Tester")  # capitals don't matter
    assert r.status_code == 200 and r.json()["username"] == "tester"
    assert anonymous.get("/account/").status_code == 200

    token = anonymous.cookies[auth.COOKIE_NAME]
    assert anonymous.post("/auth/logout").status_code == 200
    assert anonymous.get("/auth/me").status_code == 401

    anonymous.cookies.set(auth.COOKIE_NAME, token)  # an old cookie is useless after logging out
    assert anonymous.get("/auth/me").status_code == 401


def test_wrong_password_and_unknown_user_look_the_same(anonymous):
    wrong_password = log_in(anonymous, "tester", "not the password")
    no_such_user = log_in(anonymous, "nobody-here", "not the password")
    assert wrong_password.status_code == no_such_user.status_code == 401
    assert wrong_password.json() == no_such_user.json() == {"detail": "Wrong username or password"}


def test_five_wrong_passwords_lock_the_account_for_a_while(anonymous):
    for _ in range(5):
        assert log_in(anonymous, password="guess guess").status_code == 401
    locked = log_in(anonymous)  # even the right password is refused now
    assert locked.status_code == 429 and "Try again" in locked.json()["detail"]

    with Session(database.engine) as session:  # 15 minutes later...
        user = session.exec(select(User).where(User.username == "tester")).one()
        user.locked_until = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=1)
        session.add(user)
        session.commit()
    assert log_in(anonymous).status_code == 200


def test_a_good_login_resets_the_wrong_password_count(anonymous):
    for _ in range(4):
        log_in(anonymous, password="guess guess")
    assert log_in(anonymous).status_code == 200
    assert stored_user("tester").failed_logins == 0


def test_an_expired_session_has_to_log_in_again(client):
    with Session(database.engine) as session:
        for login in session.exec(select(LoginSession)).all():
            login.expires_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)
            session.add(login)
        session.commit()
    assert client.get("/auth/me").status_code == 401


def test_the_database_keeps_only_a_scramble_of_the_login_token(client):
    token = client.cookies[auth.COOKIE_NAME]
    with Session(database.engine) as session:
        stored = session.exec(select(LoginSession)).one().token_hash
    assert token not in stored and stored == auth.token_hash(token)


# ---------------------------------------------------------------- the cookie
def test_the_cookie_is_hidden_from_page_code(anonymous):
    cookie = log_in(anonymous).headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "path=/" in cookie
    assert "secure" not in cookie, "plain http while you work on your laptop"


def test_the_cookie_is_https_only_once_deployed(anonymous, monkeypatch):
    monkeypatch.setenv("SECURE_COOKIES", "1")
    assert "secure" in log_in(anonymous).headers["set-cookie"].lower()


# ---------------------------------------------------------------- every endpoint is protected
# Open to everyone on purpose: the welcome message, starting a demo, the made-up statement.
PUBLIC = {"/", "/demo/start", "/demo/sample-statement.pdf"}


def data_endpoints():
    """Every endpoint except the login ones, with example values in place of {ids}."""
    examples = {"year": "2026", "month": "9"}
    for path, methods in app.openapi()["paths"].items():  # the same list /docs shows
        if path.startswith("/auth") or path in PUBLIC:
            continue
        for method in methods:
            yield method.upper(), re.sub(r"\{(\w+)\}", lambda m: examples.get(m.group(1), "1"), path)


@pytest.mark.parametrize("method, path", sorted(data_endpoints()))
def test_every_endpoint_with_your_data_needs_a_login(anonymous, method, path):
    r = anonymous.request(method, path)
    assert r.status_code == 401, f"{method} {path} answered {r.status_code} without a login"


# ---------------------------------------------------------------- users.py
def test_set_password_unlocks_and_logs_out_everywhere(client, anonymous):
    for _ in range(5):
        log_in(anonymous, password="guess guess")
    with Session(database.engine) as session:
        users.set_password(session, "tester", "a brand new password")
    assert client.get("/auth/me").status_code == 401, "the old login is gone"
    assert log_in(anonymous, password="a brand new password").status_code == 200


def test_create_from_the_terminal_needs_no_code(anonymous, monkeypatch):
    monkeypatch.setenv("SIGNUP_CODE", "mango-season")
    with Session(database.engine) as session:
        users.create(session, "Cousin", "family password")
    assert log_in(anonymous, "cousin", "family password").status_code == 200
