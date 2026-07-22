import asyncio
from urllib.parse import urlparse, parse_qs

import httpx
import respx

from app.core import google_oauth
from app.config import settings


def test_build_authorize_url_contains_required_params():
    url = google_oauth.build_authorize_url("person@gslaw.edu.gh", "state-token-abc")
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    assert parsed.netloc == "accounts.google.com"
    assert query["client_id"] == [settings.google_client_id]
    assert query["redirect_uri"] == [settings.google_redirect_uri]
    assert query["login_hint"] == ["person@gslaw.edu.gh"]
    assert query["state"] == ["state-token-abc"]
    assert query["scope"] == ["openid email profile"]


def test_exchange_code_for_tokens_posts_to_google_and_returns_json():
    async def scenario():
        with respx.mock() as mock:
            route = mock.post(google_oauth.GOOGLE_TOKEN_ENDPOINT).mock(
                return_value=httpx.Response(200, json={"id_token": "fake-id-token", "access_token": "fake-access"})
            )
            result = await google_oauth.exchange_code_for_tokens("auth-code-xyz")
            assert route.called
            sent_body = route.calls[0].request.content.decode()
            assert "code=auth-code-xyz" in sent_body
            assert "grant_type=authorization_code" in sent_body
            return result

    result = asyncio.run(scenario())
    assert result == {"id_token": "fake-id-token", "access_token": "fake-access"}


def test_verify_id_token_delegates_to_google_auth_library(monkeypatch):
    captured = {}

    def fake_verify(token, request, audience):
        captured["token"] = token
        captured["audience"] = audience
        return {"email": "person@gslaw.edu.gh", "sub": "google-sub-1", "name": "Person"}

    monkeypatch.setattr(google_oauth.google_id_token, "verify_oauth2_token", fake_verify)

    claims = google_oauth.verify_id_token("some.jwt.token")

    assert claims["email"] == "person@gslaw.edu.gh"
    assert captured["token"] == "some.jwt.token"
    assert captured["audience"] == settings.google_client_id
