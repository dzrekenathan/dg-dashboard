import asyncio
from urllib.parse import urlparse, parse_qs

from app.core.security import create_access_token, decode_token
from app.core import google_oauth
from app.models import UserRole
from app.admin_accounts import ADMIN_ACCOUNTS


def _fake_google_claims(email, sub="google-sub-1", name="Person"):
    async def fake_exchange(code):
        return {"id_token": "fake-id-token"}

    def fake_verify(token):
        return {"email": email, "sub": sub, "name": name}

    return fake_exchange, fake_verify


def test_google_login_redirects_to_google_with_state(client):
    response = client.get("/auth/google/login", params={"email": "person@gslaw.edu.gh"}, follow_redirects=False)

    assert response.status_code in (302, 307)
    location = response.headers["location"]
    parsed = urlparse(location)
    query = parse_qs(parsed.query)
    assert parsed.netloc == "accounts.google.com"
    assert query["login_hint"] == ["person@gslaw.edu.gh"]
    state_payload = decode_token(query["state"][0])
    assert state_payload["purpose"] == "oauth_state"
    assert state_payload.get("email_hint") == "person@gslaw.edu.gh"


def test_google_login_without_email_redirects_without_login_hint(client):
    response = client.get("/auth/google/login", follow_redirects=False)

    assert response.status_code in (302, 307)
    location = response.headers["location"]
    parsed = urlparse(location)
    query = parse_qs(parsed.query)
    assert parsed.netloc == "accounts.google.com"
    assert "login_hint" not in query
    state_payload = decode_token(query["state"][0])
    assert state_payload["purpose"] == "oauth_state"
    assert state_payload.get("email_hint") is None


def test_callback_rejects_non_org_domain(client, monkeypatch):
    fake_exchange, fake_verify = _fake_google_claims("person@gmail.com")
    monkeypatch.setattr(google_oauth, "exchange_code_for_tokens", fake_exchange)
    monkeypatch.setattr(google_oauth, "verify_id_token", fake_verify)
    state = create_access_token({"purpose": "oauth_state", "email_hint": "person@gmail.com"})

    response = client.get("/auth/google/callback", params={"code": "abc", "state": state}, follow_redirects=False)

    assert response.status_code in (302, 307)
    assert "error=domain_not_allowed" in response.headers["location"]


def test_callback_then_exchange_for_admin_mapped_email_skips_onboarding(client, monkeypatch, session_maker):
    monkeypatch.setitem(ADMIN_ACCOUNTS, "dg@gslaw.edu.gh", UserRole.DG)
    fake_exchange, fake_verify = _fake_google_claims("dg@gslaw.edu.gh", name="The DG")
    monkeypatch.setattr(google_oauth, "exchange_code_for_tokens", fake_exchange)
    monkeypatch.setattr(google_oauth, "verify_id_token", fake_verify)
    state = create_access_token({"purpose": "oauth_state", "email_hint": "dg@gslaw.edu.gh"})

    callback_response = client.get("/auth/google/callback", params={"code": "abc", "state": state}, follow_redirects=False)
    location = callback_response.headers["location"]
    code = parse_qs(urlparse(location).query)["code"][0]

    exchange_response = client.post("/auth/exchange", json={"code": code})

    assert exchange_response.status_code == 200
    body = exchange_response.json()
    assert body["role"] == "dg"
    assert body["directorate"] is None
    assert "access_token" in body


def test_callback_then_exchange_for_new_staff_needs_onboarding(client, monkeypatch, session_maker):
    fake_exchange, fake_verify = _fake_google_claims("newstaff@gslaw.edu.gh", name="New Staff")
    monkeypatch.setattr(google_oauth, "exchange_code_for_tokens", fake_exchange)
    monkeypatch.setattr(google_oauth, "verify_id_token", fake_verify)
    state = create_access_token({"purpose": "oauth_state", "email_hint": "newstaff@gslaw.edu.gh"})

    callback_response = client.get("/auth/google/callback", params={"code": "abc", "state": state}, follow_redirects=False)
    code = parse_qs(urlparse(callback_response.headers["location"]).query)["code"][0]

    exchange_response = client.post("/auth/exchange", json={"code": code})

    assert exchange_response.status_code == 200
    body = exchange_response.json()
    assert body["needs_onboarding"] is True
    assert "onboarding_token" in body

    complete_response = client.post(
        "/auth/onboarding/complete",
        json={"onboarding_token": body["onboarding_token"], "directorate": "DTI"},
    )

    assert complete_response.status_code == 200
    complete_body = complete_response.json()
    assert complete_body["role"] == "staff"
    assert complete_body["directorate"] == "DTI"


def test_exchange_rejects_reused_code_after_expiry_style_tamper(client):
    response = client.post("/auth/exchange", json={"code": "not-a-real-token"})
    assert response.status_code == 400
