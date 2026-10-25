import datetime
import os
import secrets
from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Response
from sqlmodel import select

from auth import (
    COOKIE_NAME,
    LOCKOUT_MINUTES,
    MAX_FAILED_LOGINS,
    CurrentUser,
    end_session,
    hash_password,
    is_locked,
    password_matches,
    signup_code,
    start_session,
)
from database import SessionDep
from demo import DEMO_DAYS, demo_mode
from models import LogIn, SignUp, User, clean_username, utc_now

DEMO_PREFIX = "demo-"  # demo accounts are called demo-xxxxxx (see demo.py)

router = APIRouter(tags=["Login"])

WRONG_LOGIN = "Wrong username or password"


def public(user: User) -> dict:
    """What the page gets to know about a user (never the password hash)."""
    return {"id": user.id, "username": user.username, "is_demo": user.is_demo}


@router.get("/auth/settings")
def login_settings():
    """What the login page needs to know before anyone is logged in.

    demo:          "open", "code" (needs the code from a ?demo= link) or "off"
    demo_days:     how long a demo lasts before it's deleted
    feedback_url:  where "Give feedback" points (the FEEDBACK_URL setting), or null
    """
    return {
        "signup_needs_code": bool(signup_code()),
        "demo": demo_mode(),
        "demo_days": DEMO_DAYS,
        "feedback_url": os.environ.get("FEEDBACK_URL", "").strip() or None,
    }


@router.post("/auth/signup")
def sign_up(body: SignUp, response: Response, session: SessionDep):
    """Create an account and log straight in."""
    code = signup_code()
    if code and not secrets.compare_digest((body.signup_code or "").strip(), code):
        raise HTTPException(status_code=403, detail="That sign-up code isn't right")
    if body.username.startswith(DEMO_PREFIX):
        raise HTTPException(status_code=400, detail="Usernames starting with demo- are kept for demos")
    if session.exec(select(User).where(User.username == body.username)).first():
        raise HTTPException(status_code=400, detail="That username is taken. Pick another one.")
    user = User(username=body.username, password_hash=hash_password(body.password))
    session.add(user)
    session.commit()
    session.refresh(user)
    start_session(session, user, response)
    return public(user)


@router.post("/auth/login")
def log_in(body: LogIn, response: Response, session: SessionDep):
    try:
        username = clean_username(body.username)
    except ValueError:
        username = None
    user = session.exec(select(User).where(User.username == username)).first() if username else None

    if user and is_locked(user):
        raise HTTPException(
            status_code=429,
            detail=f"Too many wrong passwords. Try again in {LOCKOUT_MINUTES} minutes.",
        )

    if not password_matches(body.password, user.password_hash if user else None):
        if user:
            user.failed_logins += 1
            if user.failed_logins >= MAX_FAILED_LOGINS:
                user.failed_logins = 0
                user.locked_until = utc_now() + datetime.timedelta(minutes=LOCKOUT_MINUTES)
            session.add(user)
            session.commit()
        raise HTTPException(status_code=401, detail=WRONG_LOGIN)

    user.failed_logins, user.locked_until = 0, None
    session.add(user)
    start_session(session, user, response)  # also saves the reset counter
    return public(user)


@router.post("/auth/logout")
def log_out(
    response: Response,
    session: SessionDep,
    token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
):
    end_session(session, token, response)
    return {"ok": True}


@router.get("/auth/me")
def who_am_i(user: CurrentUser):
    """The page asks this when it opens: a 401 means "show the login screen"."""
    return public(user)
