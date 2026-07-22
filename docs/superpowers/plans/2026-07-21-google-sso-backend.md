# Google SSO Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace email/password authentication with Google OAuth (restricted to `@gslaw.edu.gh`), add first-login directorate self-selection for staff, and a hardcoded admin-role map for DG/Registrar/Super Admin — in the FastAPI backend at `d:/GSL/backend`.

**Architecture:** A stateless OAuth Authorization Code flow using signed short-lived JWTs (via the existing `python-jose` setup) for CSRF state, the post-callback exchange code, and the onboarding token — no server-side session storage needed. `httpx` performs the Google token exchange; `google-auth` verifies the ID token against Google's JWKS. A hardcoded `ADMIN_ACCOUNTS` dict (committed to the repo, not exposed via any API) maps specific emails to `dg`/`registrar`/`super_admin` roles.

**Tech Stack:** FastAPI, SQLAlchemy (async, `asyncpg`), `python-jose`, `httpx`, `google-auth`, pytest, `aiosqlite` (test DB), `respx` (HTTP mocking).

**Spec:** `docs/superpowers/specs/2026-07-21-google-sso-auth-design.md`

## Global Constraints

- Sign-in restricted to Google accounts on the `gslaw.edu.gh` domain (`settings.allowed_email_domain`).
- No passwords anywhere — `password_hash`, bcrypt, and the forgot/reset-password endpoints are removed entirely, not deprecated.
- `TokenResponse` keeps its existing shape (`access_token, role, name, email, directorate`) so the frontend contract is preserved wherever possible.
- `role` enum values: `staff, dg, registrar, super_admin` (lowercase, matches existing JSON/DB convention). `directorate` enum values: `GSL, CDT, AQAI, LRKS, DTI, CCP, PTC, FRM, SFL, CA`.
- `ADMIN_ACCOUNTS` lives in code only (`app/admin_accounts.py`), never returned by any endpoint.
- Tests run against an in-memory SQLite DB (`aiosqlite`) via a `get_db` dependency override — they must never touch the real `DATABASE_URL`. The FastAPI `lifespan` (which seeds real data on startup) must NOT run during tests: instantiate `TestClient(app)` without a `with` block.

---

### Task 1: Test harness, dependencies, and new config settings

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Modify: `app/config.py`

**Interfaces:**
- Produces: `tests/conftest.py` fixtures `db_engine`, `session_maker`, `client` — used by every later test file.
- Produces: `settings.google_client_id`, `settings.google_client_secret`, `settings.google_redirect_uri`, `settings.allowed_email_domain`, `settings.oauth_state_expire_minutes`, `settings.exchange_code_expire_minutes`, `settings.onboarding_token_expire_minutes` on the existing `app.config.settings` singleton.

- [ ] **Step 1: Add new runtime and dev dependencies to `pyproject.toml`**

Add `httpx` and `google-auth`, and a `[dependency-groups]` section. **Keep `passlib[bcrypt]` in place for now** — `app/core/security.py` still does `import bcrypt` until Task 5 rewrites it; removing the dependency here would break every test that imports `app.main` (which transitively imports `app.core.security`). Task 5 removes `passlib[bcrypt]` in the same step that removes the `bcrypt` import.

```toml
[project]
name = "clet-backend"
version = "0.1.0"
description = "CLET M&E Dashboard API"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "python-jose[cryptography]>=3.3.0",
    "httpx>=0.27.0",
    "google-auth>=2.35.0",
    "requests>=2.34.2",
    "passlib[bcrypt]>=1.7.4",
    "python-multipart>=0.0.18",
    "openpyxl>=3.1.5",
    "pydantic-settings>=2.6.0",
    "websockets>=13.0",
]

[dependency-groups]
dev = [
    "pytest>=8.3.0",
    "aiosqlite>=0.20.0",
    "respx>=0.21.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["app"]
```

- [ ] **Step 2: Install dependencies**

Run: `cd d:/GSL/backend && uv sync --group dev`
Expected: resolves and installs `httpx`, `google-auth`, `pytest`, `aiosqlite`, `respx` with no errors.

- [ ] **Step 3: Add Google/OAuth settings to `app/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str  # no default — must be set via env var
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080
    frontend_url: str = "https://dgreneral-dashboard.netlify.app"

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    allowed_email_domain: str = "gslaw.edu.gh"
    oauth_state_expire_minutes: int = 5
    exchange_code_expire_minutes: int = 2
    onboarding_token_expire_minutes: int = 10


settings = Settings()
```

- [ ] **Step 4: Create `tests/__init__.py`**

```python
```

(Empty file — makes `tests` a package so relative imports resolve consistently.)

- [ ] **Step 5: Write `tests/conftest.py`**

```python
import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


async def _create_tables(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture
def db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    asyncio.run(_create_tables(engine))
    yield engine
    asyncio.run(engine.dispose())


@pytest.fixture
def session_maker(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest.fixture
def client(session_maker):
    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)  # no `with` block: skips the real-DB lifespan
    yield test_client
    app.dependency_overrides.clear()
```

- [ ] **Step 6: Write a smoke test to verify the harness works**

Create `tests/test_smoke.py`:

```python
def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

- [ ] **Step 7: Run the smoke test**

Run: `cd d:/GSL/backend && uv run pytest tests/test_smoke.py -v`
Expected: `1 passed`. If it fails with a `database_url` validation error, confirm `.env` has `DATABASE_URL` set (Settings still loads it at import time even though tests use SQLite for actual queries).

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock app/config.py tests/__init__.py tests/conftest.py tests/test_smoke.py
git commit -m "test: add pytest harness with in-memory SQLite DB override"
```

---

### Task 2: `UserRole`/`Directorate` enums and `User` model changes

**Files:**
- Modify: `app/models.py`

**Interfaces:**
- Produces: `app.models.UserRole` (str enum: `STAFF="staff", DG="dg", REGISTRAR="registrar", SUPER_ADMIN="super_admin"`), `app.models.Directorate` (str enum: `GSL, CDT, AQAI, LRKS, DTI, CCP, PTC, FRM, SFL, CA`, values equal names), `app.models.User` with fields `id, email, name, google_id, role: UserRole, directorate: Directorate | None, created_at`. `password_hash` no longer exists.
- Consumes: nothing new (SQLAlchemy `Base` from `app.database`).

- [ ] **Step 1: Write a failing test for the new model shape**

Create `tests/test_models.py`:

```python
import asyncio

from sqlalchemy import text

from app.models import User, UserRole, Directorate


def test_user_round_trips_role_and_directorate_as_lowercase_values(session_maker):
    async def scenario():
        async with session_maker() as session:
            user = User(
                email="staff@gslaw.edu.gh",
                name="Staff Person",
                google_id="google-sub-123",
                role=UserRole.STAFF,
                directorate=Directorate.DTI,
            )
            session.add(user)
            await session.commit()

            raw = await session.execute(
                text("SELECT role, directorate FROM users WHERE email = :e"),
                {"e": "staff@gslaw.edu.gh"},
            )
            return raw.fetchone()

    row = asyncio.run(scenario())
    assert row.role == "staff"
    assert row.directorate == "DTI"


def test_user_has_no_password_hash_field():
    assert not hasattr(User, "password_hash")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd d:/GSL/backend && uv run pytest tests/test_models.py -v`
Expected: FAIL — `password_hash` is still a required field so constructing `User(...)` without it raises, and/or `UserRole`/`Directorate` don't exist yet (`ImportError`).

- [ ] **Step 3: Rewrite `app/models.py`'s `User` model**

```python
import enum
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, Text, Enum, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from sqlalchemy.dialects.postgresql import UUID
import uuid


class UserRole(str, enum.Enum):
    STAFF = "staff"
    DG = "dg"
    REGISTRAR = "registrar"
    SUPER_ADMIN = "super_admin"


class Directorate(str, enum.Enum):
    GSL = "GSL"
    CDT = "CDT"
    AQAI = "AQAI"
    LRKS = "LRKS"
    DTI = "DTI"
    CCP = "CCP"
    PTC = "PTC"
    FRM = "FRM"
    SFL = "SFL"
    CA = "CA"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    google_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    directorate: Mapped[Directorate | None] = mapped_column(
        Enum(Directorate, native_enum=False, length=10, values_callable=lambda e: [m.value for m in e]),
        nullable=True,
        default=None,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

(Leave `Task`, `ActivityTracking`, `ActivityComment`, `SOVisibility` below it unchanged.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd d:/GSL/backend && uv run pytest tests/test_models.py -v`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add app/models.py tests/test_models.py
git commit -m "feat: replace password_hash with google_id; make role/directorate enums"
```

---

### Task 3: Hardcoded admin-account map

**Files:**
- Create: `app/admin_accounts.py`
- Create: `tests/test_admin_accounts.py`

**Interfaces:**
- Consumes: `app.models.UserRole`.
- Produces: `app.admin_accounts.ADMIN_ACCOUNTS: dict[str, UserRole]`, `app.admin_accounts.get_admin_role(email: str) -> UserRole | None`.

- [ ] **Step 1: Write the failing test**

```python
from app.models import UserRole
from app import admin_accounts


def test_get_admin_role_matches_case_and_whitespace_insensitively(monkeypatch):
    monkeypatch.setitem(admin_accounts.ADMIN_ACCOUNTS, "dg@gslaw.edu.gh", UserRole.DG)
    assert admin_accounts.get_admin_role("  DG@gslaw.edu.gh  ") == UserRole.DG


def test_get_admin_role_returns_none_for_unknown_email():
    assert admin_accounts.get_admin_role("nobody@gslaw.edu.gh") is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd d:/GSL/backend && uv run pytest tests/test_admin_accounts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.admin_accounts'`.

- [ ] **Step 3: Create `app/admin_accounts.py`**

```python
"""
Hardcoded email -> role map for accounts that skip directorate self-selection.
Edit this file directly (and redeploy) to add or change a DG/Registrar/Super
Admin account. Never exposed via any API endpoint.
"""
from app.models import UserRole

ADMIN_ACCOUNTS: dict[str, UserRole] = {
    # "name@gslaw.edu.gh": UserRole.DG,
    # "name@gslaw.edu.gh": UserRole.REGISTRAR,
    # "name@gslaw.edu.gh": UserRole.SUPER_ADMIN,
}


def get_admin_role(email: str) -> UserRole | None:
    return ADMIN_ACCOUNTS.get(email.lower().strip())
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd d:/GSL/backend && uv run pytest tests/test_admin_accounts.py -v`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add app/admin_accounts.py tests/test_admin_accounts.py
git commit -m "feat: add hardcoded admin email-to-role map"
```

---

### Task 4: Google OAuth helper module

**Files:**
- Create: `app/core/google_oauth.py`
- Create: `tests/test_google_oauth.py`

**Interfaces:**
- Consumes: `app.config.settings`.
- Produces: `app.core.google_oauth.build_authorize_url(email_hint: str, state: str) -> str`, `app.core.google_oauth.exchange_code_for_tokens(code: str) -> dict` (async), `app.core.google_oauth.verify_id_token(id_token_str: str) -> dict`.

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd d:/GSL/backend && uv run pytest tests/test_google_oauth.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.google_oauth'`.

- [ ] **Step 3: Create `app/core/google_oauth.py`**

```python
from urllib.parse import urlencode

import httpx
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

from app.config import settings

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"


def build_authorize_url(email_hint: str, state: str) -> str:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "login_hint": email_hint,
        "state": state,
        "prompt": "select_account",
    }
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
    )
```

- [ ] **Step 4: Run to verify they pass**

Run: `cd d:/GSL/backend && uv run pytest tests/test_google_oauth.py -v`
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add app/core/google_oauth.py tests/test_google_oauth.py
git commit -m "feat: add Google OAuth authorize-url, token-exchange, and id-token verification helpers"
```

---

### Task 5: Rewrite `app/core/security.py` and fix downstream role checks

**Files:**
- Modify: `app/core/security.py`
- Modify: `app/routers/tasks.py:13,79,106`
- Modify: `app/routers/so_visibility.py:7,45`
- Create: `tests/test_security.py`

**Interfaces:**
- Consumes: `app.models.User`, `app.models.UserRole`.
- Produces: `app.core.security.create_access_token(data, expires_delta=None) -> str` (unchanged signature), `decode_token(token) -> dict` (unchanged), `get_current_user` (unchanged), `require_role(*roles: UserRole)` (a dependency **factory** — call it to get a dependency callable), replacing `require_management`.
- Removes: `hash_password`, `verify_password`, `require_management`.

- [ ] **Step 1: Write the failing tests**

```python
import asyncio

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.security import create_access_token, require_role
from app.models import User, UserRole


def _make_user(session_maker, role, directorate=None, email="person@gslaw.edu.gh"):
    async def scenario():
        async with session_maker() as session:
            user = User(email=email, name="Person", google_id="g-1", role=role, directorate=directorate)
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user
    return asyncio.run(scenario())


def _mount_probe_route(app, session_maker):
    from app.database import get_db

    async def override_get_db():
        async with session_maker() as session:
            yield session
    app.dependency_overrides[get_db] = override_get_db

    @app.get("/__probe/staff-or-admin")
    async def probe(user: User = Depends(require_role(UserRole.STAFF, UserRole.SUPER_ADMIN))):
        return {"email": user.email}


def test_require_role_allows_matching_role(session_maker):
    user = _make_user(session_maker, UserRole.STAFF)
    app = FastAPI()
    _mount_probe_route(app, session_maker)
    token = create_access_token({"sub": user.id, "role": user.role.value})

    response = TestClient(app).get("/__probe/staff-or-admin", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "person@gslaw.edu.gh"


def test_require_role_rejects_non_matching_role(session_maker):
    user = _make_user(session_maker, UserRole.DG, email="dg@gslaw.edu.gh")
    app = FastAPI()
    _mount_probe_route(app, session_maker)
    token = create_access_token({"sub": user.id, "role": user.role.value})

    response = TestClient(app).get("/__probe/staff-or-admin", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd d:/GSL/backend && uv run pytest tests/test_security.py -v`
Expected: FAIL — `ImportError: cannot import name 'require_role' from 'app.core.security'`.

- [ ] **Step 3: Rewrite `app/core/security.py`**

```python
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import settings
from app.database import get_db
from app.models import User, UserRole

bearer_scheme = HTTPBearer()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload["exp"] = expire
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_token(credentials.credentials)
    user_id: str = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_role(*roles: UserRole):
    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="You do not have access to this resource")
        return user
    return _check
```

- [ ] **Step 4: Fix the two call sites that used `require_management`**

In `app/routers/tasks.py`, change line 13:

```python
from app.core.security import get_current_user, require_management
```
to:
```python
from app.core.security import get_current_user, require_role
from app.models import Task, User, UserRole
```

(Note: `app.models` import on that line already exists as `from app.models import Task, User` — extend it to include `UserRole` rather than adding a second import line.)

Change line 79 and line 106 from `Depends(require_management)` to `Depends(require_role(UserRole.STAFF, UserRole.SUPER_ADMIN))`.

In `app/routers/so_visibility.py`, change line 7:
```python
from app.core.security import get_current_user, require_management
```
to:
```python
from app.core.security import get_current_user, require_role
```
and line 5 from `from app.models import SOVisibility, User` to `from app.models import SOVisibility, User, UserRole`.

Change line 45 from `Depends(require_management)` to `Depends(require_role(UserRole.STAFF, UserRole.SUPER_ADMIN))`.

- [ ] **Step 5: Run the security tests to verify they pass**

Run: `cd d:/GSL/backend && uv run pytest tests/test_security.py -v`
Expected: `2 passed`.

- [ ] **Step 6: Remove the now-unused `passlib[bcrypt]` dependency from `pyproject.toml`**

`app/core/security.py` no longer imports `bcrypt` after Step 3's rewrite, so drop the line `"passlib[bcrypt]>=1.7.4",` from the `dependencies` list added back in Task 1. Then run: `cd d:/GSL/backend && uv sync --group dev`.
Expected: resolves with no errors, `bcrypt`/`passlib` removed from the environment.

- [ ] **Step 7: Fix `app/main.py`'s now-broken `hash_password` import (discovered during implementation — not just `app/routers/auth.py` is affected)**

`app/main.py` separately does `from app.core.security import hash_password` at module level to seed two password-based default users in `_bootstrap()`. Since `tests/conftest.py` does `from app.main import app`, this breaks collection for *every* test the moment Step 3 removes `hash_password` — not only `app/routers/auth.py`. Fix it now rather than leaving three tasks' worth of tests uncollectable: replace `app/main.py` with the content specified in Task 8 Step 3 below (this pulls that part of Task 8 forward). Task 8 itself then only needs to handle `app/seed.py`.

- [ ] **Step 8: Run the full test suite to confirm nothing else broke**

Run: `cd d:/GSL/backend && uv run pytest -v`
Expected: `app/routers/auth.py` still imports the now-removed `verify_password`/`hash_password`/old schemas at this point in the plan — that's fixed in Tasks 6-7. The collection error should now point ONLY at `app/routers/auth.py` (not `app/main.py`, since Step 7 already fixed that). That's expected and resolved by the end of Task 7; skip ahead and come back to re-run the full suite after Task 7 instead of blocking here.

- [ ] **Step 9: Commit**

```bash
git add app/core/security.py app/routers/tasks.py app/routers/so_visibility.py app/main.py tests/test_security.py pyproject.toml uv.lock
git commit -m "feat: replace require_management with role-based require_role dependency"
```

---

### Task 6: Rewrite `app/schemas.py` auth schemas

**Files:**
- Modify: `app/schemas.py`

**Interfaces:**
- Consumes: `app.models.UserRole`, `app.models.Directorate`.
- Produces: `ExchangeRequest{code: str}`, `OnboardingCompleteRequest{onboarding_token: str, directorate: Directorate}`, `TokenResponse{access_token, token_type, role: UserRole, name, email, directorate: Directorate | None}`, `OnboardingRequiredResponse{needs_onboarding: bool = True, onboarding_token: str}`, `UserOut{id, email, name, role: UserRole, directorate: Directorate | None}`.
- Removes: `LoginRequest`, `RegisterRequest`, `ForgotPasswordRequest`, `ResetPasswordRequest`.

- [ ] **Step 1: Replace the `# ── Auth ──` section at the top of `app/schemas.py`**

Replace lines 1-44 (from the imports through the end of `UserOut`) with:

```python
from pydantic import BaseModel
from typing import Optional
from app.models import UserRole, Directorate


# ── Auth ──────────────────────────────────────────────────────────────────────

class ExchangeRequest(BaseModel):
    code: str


class OnboardingCompleteRequest(BaseModel):
    onboarding_token: str
    directorate: Directorate


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    name: str
    email: str
    directorate: Directorate | None = None


class OnboardingRequiredResponse(BaseModel):
    needs_onboarding: bool = True
    onboarding_token: str


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: UserRole
    directorate: Directorate | None = None

    model_config = {"from_attributes": True}
```

Leave everything from `# ── Tasks ──` onward unchanged.

- [ ] **Step 2: Verify the module still imports cleanly**

Run: `cd d:/GSL/backend && uv run python -c "import app.schemas"`
Expected: no output, exit code 0. (No dedicated test file for this step — schema wiring is exercised end-to-end by Task 7's router tests.)

- [ ] **Step 3: Commit**

```bash
git add app/schemas.py
git commit -m "feat: replace password-auth schemas with Google SSO exchange/onboarding schemas"
```

---

### Task 7: Rewrite `app/routers/auth.py`

**Files:**
- Modify: `app/routers/auth.py`
- Create: `tests/test_auth_router.py`

**Interfaces:**
- Consumes: `app.core.security.create_access_token`, `decode_token`, `get_current_user`; `app.core.google_oauth.build_authorize_url`, `exchange_code_for_tokens`, `verify_id_token`; `app.admin_accounts.get_admin_role`; `app.schemas.ExchangeRequest`, `OnboardingCompleteRequest`, `TokenResponse`, `OnboardingRequiredResponse`, `UserOut`.
- Produces: `GET /auth/google/login`, `GET /auth/google/callback`, `POST /auth/exchange`, `POST /auth/onboarding/complete`, `GET /auth/me`.

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd d:/GSL/backend && uv run pytest tests/test_auth_router.py -v`
Expected: FAIL — current `app/routers/auth.py` has no `/google/login`, `/exchange`, etc. routes (404s) and imports schemas that no longer exist (`LoginRequest` etc.), so collection itself may error.

- [ ] **Step 3: Rewrite `app/routers/auth.py`**

```python
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
async def google_login(email: str = Query(...)):
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
```

- [ ] **Step 4: Run to verify they pass**

Run: `cd d:/GSL/backend && uv run pytest tests/test_auth_router.py -v`
Expected: `5 passed`.

- [ ] **Step 5: Run the full test suite**

Run: `cd d:/GSL/backend && uv run pytest -v`
Expected: all tests across `tests/` pass (this also re-confirms Task 5's Step 6 deferral is now resolved, since `app/routers/auth.py` no longer imports the removed password helpers).

- [ ] **Step 6: Commit**

```bash
git add app/routers/auth.py tests/test_auth_router.py
git commit -m "feat: implement Google OAuth login/callback/exchange/onboarding endpoints"
```

---

### Task 8: Clean up `app/seed.py` (`app/main.py` was already fixed in Task 5 Step 7)

**Files:**
- Modify: `app/seed.py`
- Create: `tests/test_bootstrap.py`

**Interfaces:**
- Consumes: nothing new.
- Removes: the password-based `USERS` list from `app/seed.py`. (`app/main.py`'s password-based `default_users` seeding block was already removed in Task 5 Step 7, pulled forward because it blocked test collection for every task from that point on — verify it's already in the state shown in Step 3 below rather than re-deriving it.)

- [ ] **Step 1: Write the failing test**

Create `tests/test_bootstrap.py`:

```python
import asyncio
from sqlalchemy import select

from app.models import User


def test_bootstrap_no_longer_creates_password_seeded_users(client, session_maker):
    client.get("/health")  # triggers nothing password-related; app.main must import cleanly

    async def scenario():
        async with session_maker() as session:
            result = await session.execute(select(User).where(User.email == "dg@clet.gov.gh"))
            return result.scalar_one_or_none()

    assert asyncio.run(scenario()) is None
```

- [ ] **Step 2: Confirm `app/main.py` is already in its target state**

This was pulled forward into Task 5 Step 7 because it blocked test collection for every task after the `security.py` rewrite. Read `app/main.py` and confirm it has no `hash_password` import and no `default_users` seeding block — only the `_bootstrap()` function seeding `SOVisibility` rows, CORS, routers, and the `/health` endpoint. If it's already in this state (it should be), proceed to Step 3 without changes. If it somehow isn't, that's a regression — restore it to match Task 5 Step 7's content before continuing.

- [ ] **Step 3: Rewrite `app/seed.py`**

Users now self-provision on first Google login, so `seed.py` only needs to seed `SOVisibility` rows:

```python
"""
Run once to seed initial reference data.
    uv run python -m app.seed
"""
import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal, engine
from app.database import Base
from app.models import SOVisibility


SOS = ["SO1", "SO2", "SO3", "SO4"]


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        for so in SOS:
            exists = await db.execute(select(SOVisibility).where(SOVisibility.so_number == so))
            if not exists.scalar_one_or_none():
                db.add(SOVisibility(so_number=so, is_visible=True))
                print(f"  ✓ Created visibility row: {so}")

        await db.commit()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
```

- [ ] **Step 4: Run the full test suite to verify the new test passes and nothing else broke**

Run: `cd d:/GSL/backend && uv run pytest -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/main.py app/seed.py tests/test_bootstrap.py
git commit -m "chore: remove password-based user seeding now that users self-provision via Google"
```

---

### Task 9: Database migration

**Files:**
- Create: `alembic/versions/002_google_sso.py`
- Create: `migrate_google_sso.py`

**Interfaces:**
- Consumes: the `users` table as created by `alembic/versions/001_initial.py`.
- Produces: `users.password_hash` dropped, `users.google_id` added (nullable, unique), existing `role` value `"management"` rewritten to `"staff"`.

- [ ] **Step 1: Write the Alembic revision**

`alembic/versions/001_initial.py` has `revision = "001"` (not `"001_initial"` — the filename and the revision id differ). Create `alembic/versions/002_google_sso.py` directly (no need to run `alembic revision`, since the exact content is given below) with `down_revision = "001"`:

```python
"""google sso

Revision ID: 002
Revises: 001
Create Date: 2026-07-21
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_id", sa.String(length=255), nullable=True))
    op.create_unique_constraint("uq_users_google_id", "users", ["google_id"])
    op.execute("UPDATE users SET role = 'staff' WHERE role = 'management'")
    op.drop_column("users", "password_hash")


def downgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.execute("UPDATE users SET role = 'management' WHERE role = 'staff'")
    op.drop_constraint("uq_users_google_id", "users", type_="unique")
    op.drop_column("users", "google_id")
```

- [ ] **Step 2: Validate the migration compiles (offline SQL dry run, no live DB needed)**

Run: `cd d:/GSL/backend && uv run alembic upgrade head --sql`
Expected: prints the generated `ALTER TABLE`/`UPDATE` SQL statements with no Python traceback.

- [ ] **Step 3: Write the standalone manual-apply script** (matching the existing `migrate_directorate.py` convenience-script convention, for environments where running `alembic upgrade head` isn't part of the deploy process)

```python
"""
One-off migration: switch users table to Google SSO (drop password_hash, add google_id).
Run with: uv run python migrate_google_sso.py
"""
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings


async def migrate():
    engine = create_async_engine(
        settings.database_url,
        echo=True,
        connect_args={"ssl": "require"},
    )
    async with engine.begin() as conn:
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id VARCHAR(255);"))
        await conn.execute(text(
            "DO $$ BEGIN "
            "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_users_google_id') THEN "
            "ALTER TABLE users ADD CONSTRAINT uq_users_google_id UNIQUE (google_id); "
            "END IF; END $$;"
        ))
        await conn.execute(text("UPDATE users SET role = 'staff' WHERE role = 'management';"))
        await conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS password_hash;"))

        result = await conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'users' AND column_name IN ('google_id', 'password_hash');"
        ))
        rows = result.fetchall()
        print(f"\nColumns present after migration: {[r[0] for r in rows]}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
```

- [ ] **Step 4: Commit**

```bash
git add alembic/versions/002_google_sso.py migrate_google_sso.py
git commit -m "feat: add migration dropping password_hash and adding google_id"
```

---

## Post-Plan Checklist for the User (not implementation tasks)

- Fill real DG / Registrar / Super Admin emails into `app/admin_accounts.py`.
- Create OAuth credentials in Google Cloud Console; set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` in `.env` / hosting provider env vars, matching exactly what's registered in the console.
- Run `alembic upgrade head` (or `migrate_google_sso.py`) against the production database before deploying the new code.
- Implement the companion frontend plan: `docs/superpowers/plans/2026-07-21-google-sso-frontend.md` (in the `clet-dashboard` repo).
