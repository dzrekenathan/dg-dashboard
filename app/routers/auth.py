from datetime import timedelta
from typing import Union

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.models import User, UserRole
from app.schemas import (
    ExchangeRequest,
    OnboardingCompleteRequest,
    TokenResponse,
    OnboardingRequiredResponse,
    UserOut,
)
from app.core.security import create_access_token, decode_token, get_current_user
from app.core import google_oauth
from app.admin_accounts import get_admin_role

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_session_token(user: User) -> TokenResponse:
    token = create_access_token({"sub": user.id, "role": user.role.value})
    return TokenResponse(
        access_token=token,
        role=user.role,
        name=user.name,
        email=user.email,
        directorate=user.directorate,
    )


@router.get("/google/login")
async def google_login(email: str | None = Query(None)):
    state = create_access_token(
        {"purpose": "oauth_state", "email_hint": email},
        expires_delta=timedelta(minutes=settings.oauth_state_expire_minutes),
    )
    return RedirectResponse(google_oauth.build_authorize_url(email, state))


@router.get("/google/callback")
async def google_callback(code: str, state: str, db: AsyncSession = Depends(get_db)):
    try:
        state_payload = decode_token(state)
    except HTTPException:
        return RedirectResponse(f"{settings.frontend_url}/login?error=invalid_state")
    if state_payload.get("purpose") != "oauth_state":
        return RedirectResponse(f"{settings.frontend_url}/login?error=invalid_state")

    tokens = await google_oauth.exchange_code_for_tokens(code)
    claims = google_oauth.verify_id_token(tokens["id_token"])

    email = claims["email"].lower().strip()
    if not email.endswith(f"@{settings.allowed_email_domain}"):
        return RedirectResponse(f"{settings.frontend_url}/login?error=domain_not_allowed")

    admin_role = get_admin_role(email)
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            email=email,
            name=claims.get("name", email),
            google_id=claims["sub"],
            role=admin_role or UserRole.STAFF,
            directorate=None,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    elif admin_role is not None and user.role != admin_role:
        user.role = admin_role
        await db.commit()
        await db.refresh(user)

    exchange_code = create_access_token(
        {"purpose": "exchange_code", "user_id": user.id},
        expires_delta=timedelta(minutes=settings.exchange_code_expire_minutes),
    )
    return RedirectResponse(f"{settings.frontend_url}/auth/callback?code={exchange_code}")


@router.post("/exchange", response_model=Union[TokenResponse, OnboardingRequiredResponse])
async def exchange(body: ExchangeRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(body.code)
    except HTTPException:
        raise HTTPException(status_code=400, detail="Exchange code is invalid or has expired")
    if payload.get("purpose") != "exchange_code":
        raise HTTPException(status_code=400, detail="Invalid exchange code")

    result = await db.execute(select(User).where(User.id == payload.get("user_id")))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Account not found")

    if user.role == UserRole.STAFF and user.directorate is None:
        onboarding_token = create_access_token(
            {"purpose": "onboarding", "user_id": user.id},
            expires_delta=timedelta(minutes=settings.onboarding_token_expire_minutes),
        )
        return OnboardingRequiredResponse(onboarding_token=onboarding_token)

    return _issue_session_token(user)


@router.post("/onboarding/complete", response_model=TokenResponse)
async def complete_onboarding(body: OnboardingCompleteRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(body.onboarding_token)
    except HTTPException:
        raise HTTPException(status_code=400, detail="Onboarding link is invalid or has expired")
    if payload.get("purpose") != "onboarding":
        raise HTTPException(status_code=400, detail="Invalid onboarding token")

    result = await db.execute(select(User).where(User.id == payload.get("user_id")))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Account not found")

    user.directorate = body.directorate
    await db.commit()
    await db.refresh(user)

    return _issue_session_token(user)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user
