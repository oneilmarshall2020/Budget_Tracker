"""Logins: storing passwords safely, remembering who's logged in, and working out
"who is asking?" for every request.

How a login works:
  1. You send your username and password once (POST /auth/login).
  2. If they match, we make a long random token, keep a scramble (hash) of it in the
     login_session table, and hand the token to your browser in a cookie.
  3. Your browser sends that cookie with every request after that. `current_user`
     below looks it up and tells each endpoint which user is asking.

Settings (environment variables):
  SIGNUP_CODE     if set, creating an account needs this code (set it when you deploy)
  SECURE_COOKIES  "1" = the cookie only travels over https (automatic on Vercel)
"""
import datetime
import hashlib
import os
import secrets
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Response
from pwdlib import PasswordHash
from sqlmodel import Session, select

from database import SessionDep
from models import LoginSession, User, utc_now

COOKIE_NAME = "budget_session"
SESSION_DAYS = 30  # stay logged in on a device for 30 days
MAX_FAILED_LOGINS = 5  # wrong passwords in a row before the account locks...
LOCKOUT_MINUTES = 15  # ...for this long

# Argon2: a deliberately slow, one-way scramble. Checking a guess takes a noticeable
# fraction of a second, so trying millions of passwords would take years.
password_hasher = PasswordHash.recommended()

# Checked when a username doesn't exist, so a wrong username takes as long as a wrong
# password. Otherwise the timing would reveal which usernames are real.
DUMMY_HASH = password_hasher.hash("not-anyone's-password")


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def password_matches(password: str, stored_hash: str | None) -> bool:
    if not stored_hash:  # unknown user, or one with no password yet: always "no"
        password_hasher.verify(password, DUMMY_HASH)
        return False
    return password_hasher.verify(password, stored_hash)


def token_hash(token: str) -> str:
    """The database keeps only this scramble of each login token."""
    return hashlib.sha256(token.encode()).hexdigest()


def as_utc(moment: datetime.datetime) -> datetime.datetime:
    """Some databases hand times back without a time zone; ours are always UTC."""
    return moment if moment.tzinfo else moment.replace(tzinfo=datetime.timezone.utc)


def secure_cookies() -> bool:
    # On by default on Vercel (always https), off on your laptop (plain http).
    return os.environ.get("SECURE_COOKIES", "1" if os.environ.get("VERCEL") else "0") == "1"


def signup_code() -> str:
    return os.environ.get("SIGNUP_CODE", "").strip()


def is_locked(user: User) -> bool:
    return user.locked_until is not None and as_utc(user.locked_until) > utc_now()


def start_session(session: Session, user: User, response: Response) -> None:
    """Log this browser in: save a new session and give the browser its cookie."""
    token = secrets.token_urlsafe(32)  # 256 random bits: impossible to guess
    now = utc_now()
    # Tidy up: this user's expired logins are no use to anyone.
    for old in session.exec(select(LoginSession).where(LoginSession.user_id == user.id)).all():
        if as_utc(old.expires_at) <= now:
            session.delete(old)
    session.add(LoginSession(
        user_id=user.id,
        token_hash=token_hash(token),
        created_at=now,
        expires_at=now + datetime.timedelta(days=SESSION_DAYS),
    ))
    session.commit()
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=SESSION_DAYS * 24 * 60 * 60,
        httponly=True,  # page code can't read it, so a bug in the page can't leak it
        samesite="lax",  # other websites can't make your browser send it with their requests
        secure=secure_cookies(),  # only ever sent over https, once deployed
        path="/",
    )


def end_session(session: Session, token: str | None, response: Response) -> None:
    if token:
        login = session.exec(
            select(LoginSession).where(LoginSession.token_hash == token_hash(token))
        ).first()
        if login:
            session.delete(login)
            session.commit()
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite="lax", secure=secure_cookies())


def current_user(
    session: SessionDep,
    token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> User:
    """Who is asking? Every endpoint that touches someone's data depends on this.
    No cookie, an unknown token or an expired one all mean: please log in."""
    if token:
        login = session.exec(
            select(LoginSession).where(LoginSession.token_hash == token_hash(token))
        ).first()
        if login and as_utc(login.expires_at) > utc_now():
            user = session.get(User, login.user_id)
            if user:
                return user
    raise HTTPException(status_code=401, detail="Please log in")


CurrentUser = Annotated[User, Depends(current_user)]
