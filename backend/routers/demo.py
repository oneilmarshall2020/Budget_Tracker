import secrets

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse
from sqlmodel import SQLModel

from auth import CurrentUser, end_session, start_session
from database import SessionDep
from demo import (
    MAX_DEMOS,
    SAMPLE_STATEMENT,
    count_demos,
    create_demo,
    delete_user_data,
    demo_code,
    demo_mode,
    remove_old_demos,
)
from routers.auth import public

router = APIRouter(tags=["Demo"])


class DemoStart(SQLModel):
    code: str | None = None


@router.post("/demo/start")
def start_demo(body: DemoStart, response: Response, session: SessionDep):
    """Make a throwaway account full of made-up data, and log straight in."""
    mode = demo_mode()
    if mode == "off":
        raise HTTPException(status_code=403, detail="The demo isn't switched on here")
    if mode == "code" and not secrets.compare_digest((body.code or "").strip(), demo_code()):
        raise HTTPException(status_code=403, detail="That demo link isn't right. Ask for a new one.")

    remove_old_demos(session)
    if count_demos(session) >= MAX_DEMOS:
        raise HTTPException(status_code=429, detail="Too many demos running right now. Try again tomorrow.")

    user = create_demo(session)
    start_session(session, user, response)
    return public(user)


@router.post("/demo/end")
def end_demo(response: Response, session: SessionDep, user: CurrentUser):
    """Delete this demo account and everything in it, now."""
    if not user.is_demo:
        raise HTTPException(status_code=400, detail="Only demo accounts can be ended")
    delete_user_data(session, user)  # its logins go too, so the cookie stops working
    session.commit()
    end_session(session, None, response)
    return {"ok": True}


@router.get("/demo/sample-statement.pdf")
def sample_statement():
    """A made-up NCB statement to try the import with. No real person's data."""
    if not SAMPLE_STATEMENT.exists():
        # Usually .gitignore's "*.pdf" kept it out of GitHub: add !backend/samples/*.pdf
        raise HTTPException(status_code=404, detail="The sample statement is missing from the backend")
    return FileResponse(SAMPLE_STATEMENT, media_type="application/pdf", filename="ncb-sample-statement.pdf")
