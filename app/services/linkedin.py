from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status

from app.core.config import settings

AUTHORIZE_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
POSTS_URL = "https://api.linkedin.com/v2/ugcPosts"


def get_auth_url(state: str) -> str:
    if not settings.linkedin_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LinkedIn OAuth is not configured",
        )

    params = {
        "response_type": "code",
        "client_id": settings.linkedin_client_id,
        "redirect_uri": settings.linkedin_redirect_uri,
        "state": state,
        "scope": " ".join(settings.scope_list),
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code_for_token(code: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.linkedin_redirect_uri,
                "client_id": settings.linkedin_client_id,
                "client_secret": settings.linkedin_client_secret,
            },
        )
        response.raise_for_status()
        return response.json()


async def refresh_access_token(refresh_token: str) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": settings.linkedin_client_id,
                "client_secret": settings.linkedin_client_secret,
            },
        )
        response.raise_for_status()
        return response.json()


async def get_user_profile(access_token: str) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()


async def create_post(access_token: str, author_urn: str, text: str) -> dict:
    payload = {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            POSTS_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Restli-Protocol-Version": "2.0.0",
            },
        )
        response.raise_for_status()
        return response.json()
