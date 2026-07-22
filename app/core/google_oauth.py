from urllib.parse import urlencode

import httpx
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

from app.config import settings

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"


def build_authorize_url(email_hint: str | None, state: str) -> str:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    if email_hint:
        params["login_hint"] = email_hint
    return f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_ENDPOINT,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        response.raise_for_status()
        return response.json()


def verify_id_token(id_token_str: str) -> dict:
    return google_id_token.verify_oauth2_token(
        id_token_str,
        google_requests.Request(),
        settings.google_client_id,
        clock_skew_in_seconds=10,
    )
