import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.post import LinkedInAccount
from app.services.linkedin import exchange_code_for_token, get_auth_url, get_user_profile
from app.services.session import (
    clear_session_cookie,
    create_session,
    get_current_account,
    revoke_session,
    set_session_cookie,
)

router = APIRouter(prefix="/auth", tags=["auth"])
OAUTH_STATE_COOKIE = "linkedin_oauth_state"


@router.get("/login")
async def login():
    """Redirect user to LinkedIn OAuth authorization page."""
    state = secrets.token_urlsafe(24)
    response = RedirectResponse(url=get_auth_url(state))
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )
    return response


@router.get("/callback")
async def callback(
    code: str = Query(...),
    state: str = Query(...),
    oauth_state: str | None = Cookie(default=None, alias=OAUTH_STATE_COOKIE),
    db: Session = Depends(get_db),
):
    """Handle LinkedIn OAuth callback, store session, and redirect to dashboard."""
    if not oauth_state or not secrets.compare_digest(oauth_state, state):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")

    token_data = await exchange_code_for_token(code)
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LinkedIn did not return an access token",
        )

    profile = await get_user_profile(access_token)
    account = upsert_account(db, token_data, profile)
    raw_session = create_session(db, account)

    response = RedirectResponse(url="/dashboard")
    set_session_cookie(response, raw_session)
    response.delete_cookie(OAUTH_STATE_COOKIE)
    return response


@router.get("/session")
async def session(account: LinkedInAccount = Depends(get_current_account)):
    return {
        "id": account.id,
        "name": account.display_name,
        "picture": account.avatar_url,
        "author_urn": account.author_urn,
    }


@router.post("/logout")
async def logout(
    response: Response,
    session_token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
    db: Session = Depends(get_db),
):
    revoke_session(db, session_token)
    clear_session_cookie(response)
    return {"status": "logged_out"}


def upsert_account(db: Session, token_data: dict, profile: dict) -> LinkedInAccount:
    member_id = profile.get("sub")
    if not member_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LinkedIn profile response did not include a member id",
        )

    expires_in = token_data.get("expires_in")
    token_expires_at = None
    if isinstance(expires_in, int):
        token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    account = (
        db.query(LinkedInAccount)
        .filter(LinkedInAccount.linkedin_member_id == str(member_id))
        .first()
    )
    if not account:
        account = LinkedInAccount(
            linkedin_member_id=str(member_id),
            author_urn=f"urn:li:person:{member_id}",
            display_name=profile.get("name") or "LinkedIn member",
            avatar_url=profile.get("picture"),
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            token_expires_at=token_expires_at,
        )
        db.add(account)
    else:
        account.display_name = profile.get("name") or account.display_name
        account.avatar_url = profile.get("picture")
        account.author_urn = f"urn:li:person:{member_id}"
        account.access_token = token_data["access_token"]
        account.refresh_token = token_data.get("refresh_token") or account.refresh_token
        account.token_expires_at = token_expires_at

    db.commit()
    db.refresh(account)
    return account
