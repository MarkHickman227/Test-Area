import json

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from app.services.linkedin import exchange_code_for_token, get_auth_url, get_user_profile

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
async def login():
    """Redirect user to LinkedIn OAuth authorization page."""
    return RedirectResponse(url=get_auth_url())


@router.get("/callback")
async def callback(code: str = Query(...), state: str = Query("random_state")):
    """Handle LinkedIn OAuth callback, store session, and redirect to dashboard."""
    token_data = await exchange_code_for_token(code)
    access_token = token_data.get("access_token")
    profile = await get_user_profile(access_token)

    session_data = json.dumps({"access_token": access_token, "profile": profile})
    return HTMLResponse(f"""
        <script>
            localStorage.setItem("linkedin_session", {json.dumps(session_data)});
            window.location.href = "/dashboard";
        </script>
    """)
