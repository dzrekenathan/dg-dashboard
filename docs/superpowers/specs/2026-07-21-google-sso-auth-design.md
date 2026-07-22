# Google SSO Authentication & Directorate Onboarding — Design

Date: 2026-07-21
Status: Approved for planning

## Background

The backend (`d:/GSL/backend`, FastAPI + async SQLAlchemy) currently authenticates users with email/password (`app/routers/auth.py`, `app/core/security.py`): bcrypt-hashed passwords, JWT issuance via `python-jose`, plus forgot/reset-password flows. The `User` model (`app/models.py`) has `role` as a raw string (`"dg"`, `"management"`) and `directorate` as a raw nullable string. A companion React frontend (`d:/GSL/clet-dashboard`) consumes `POST /auth/login`, `POST /auth/register`, and `GET /auth/me`, storing the returned JWT + session info in `localStorage`.

This design replaces password-based auth with Google SSO, restricted to the `gslaw.edu.gh` Workspace domain, adds a directorate self-selection step for new staff, and introduces a small hardcoded admin-role map for DG, Registrar, and Super Admin accounts.

## Goals

- Remove password-based login/signup entirely; authenticate exclusively via Google OAuth.
- Restrict sign-in to `@gslaw.edu.gh` Google accounts.
- Let a new staff user pick their directorate once, at first login; persist it thereafter.
- Recognize DG, Registrar, and Super Admin by a hardcoded email→role map maintained directly in backend code (not exposed via any API) — these roles skip directorate selection and land on their own dashard.
- Preserve the existing `TokenResponse` shape (`access_token, role, name, email, directorate`) wherever possible to minimize frontend churn.

## Non-goals

- Building the DG/Registrar's own future task-filling pages (explicitly deferred by the user).
- Supporting non-Google identity providers.
- A password-based break-glass/fallback path for Super Admin (explicitly rejected — Google SSO only, no exceptions).

## Roles & Directorates

**Roles** (enum, replaces the current raw string): `staff`, `dg`, `registrar`, `super_admin`.

**Directorates** (enum, replaces the current raw string), selectable by `staff` users only:
`GSL`, `CDT`, `AQAI`, `LRKS`, `DTI`, `CCP`, `PTC`, `FRM`, `SFL`, `CA`.

`dg`, `registrar`, and `super_admin` users have `directorate = NULL` — they are not scoped to one directorate.

**Permissions:**
- `staff`: access only their own directorate's progress/task pages (`user.directorate` scoped).
- `dg`, `registrar`: view the general cross-directorate dashboard only. They do **not** see other directorates' task-filling pages. (Each will get their own task page in a future iteration — out of scope here, but the role split makes it a small addition later.)
- `super_admin`: full access — every directorate's task pages, the general dashboard, and DG's/Registrar's views.

## Auth Flow

1. Frontend login page: user types their `@gslaw.edu.gh` email, clicks "Sign in with Google" → browser navigates to `GET /auth/google/login?email=<hint>`.
2. Backend builds Google's OAuth authorization URL (`client_id`, `redirect_uri`, `scope=openid email profile`, `login_hint=email`, and a `state` parameter — a short-lived signed JWT nonce, avoiding server-side session storage) and redirects the browser to Google.
3. Google authenticates the user and redirects back to `GET /auth/google/callback?code=...&state=...`.
4. Backend verifies `state`, exchanges `code` for tokens with Google (via `httpx`), verifies the ID token against Google's JWKS (via `google-auth`), and extracts `email`, `sub` (Google's stable user id), `name`.
5. Backend rejects (redirects to a frontend error page) if the email's domain isn't `gslaw.edu.gh`.
6. Backend checks the hardcoded `ADMIN_ACCOUNTS` map (see below) for this email:
   - Matched → upsert a `User` row with the mapped role, `directorate=NULL`.
   - Not matched → look up an existing `User` by email:
     - Found (directorate already set from a prior first login) → use as-is.
     - Not found → create `User(role="staff", directorate=NULL)` — this is a first-time login that needs directorate selection.
7. Backend generates a short-lived (~2 min), single-use, signed **exchange code** and redirects the browser to `FRONTEND_URL/auth/callback?code=...`. The long-lived session JWT is never placed in a URL, avoiding it leaking into browser history or server logs.
8. Frontend's callback page immediately calls `POST /auth/exchange {code}`. Backend responds with either:
   - `{needs_onboarding: true, onboarding_token}` — new staff user, no directorate yet.
   - `{access_token, role, name, email, directorate}` — existing user or admin-mapped account, ready to use.
9. If onboarding was needed, the frontend shows the 10-directorate dropdown and calls `POST /auth/onboarding/complete {onboarding_token, directorate}`, which sets the user's directorate and returns the same `TokenResponse` shape as step 8.

## Data Model Changes (`app/models.py`)

- Remove `password_hash` entirely.
- Add `google_id` (nullable string) — Google's stable `sub`, stored for robustness against email changes on the Workspace account.
- `role`: raw string → enum (`staff | dg | registrar | super_admin`).
- `directorate`: raw string → enum (`GSL | CDT | AQAI | LRKS | DTI | CCP | PTC | FRM | SFL | CA`), nullable.

## Hardcoded Admin Map

A module (e.g. `app/admin_accounts.py`) not exposed via any API:

```python
ADMIN_ACCOUNTS: dict[str, str] = {
    # "name@gslaw.edu.gh": "dg",
    # "name@gslaw.edu.gh": "registrar",
    # "name@gslaw.edu.gh": "super_admin",
}
```

The user edits this file directly and redeploys when an admin account needs to be added or changed. Checked first, before the normal staff lookup/creation path, on every successful Google callback.

## API Contract

| Endpoint | Method | Purpose |
|---|---|---|
| `/auth/google/login` | GET | Redirect to Google's OAuth consent screen |
| `/auth/google/callback` | GET | Google redirects here; backend redirects to frontend with a one-time `code` |
| `/auth/exchange` | POST | `{code}` → full session, or `{needs_onboarding, onboarding_token}` |
| `/auth/onboarding/complete` | POST | `{onboarding_token, directorate}` → full session |
| `/auth/me` | GET | Unchanged — current user profile |

**Removed:** `POST /auth/login`, `POST /auth/register`, `POST /auth/forgot-password`, `POST /auth/reset-password`, bcrypt hashing utilities, and the plaintext-password seed users currently created in `app/main.py`'s startup lifespan.

## Config (`app/config.py`)

New settings: `google_client_id`, `google_client_secret`, `google_redirect_uri`, `allowed_email_domain` (default `gslaw.edu.gh`).

## Authorization Dependencies (`app/core/security.py`)

Replace `require_management` with:
- `require_role(*roles)` — generic role check.
- `require_directorate_access(directorate)` — passes for `staff` matching their own directorate, or for `super_admin`.

## Frontend Changes (`d:/GSL/clet-dashboard`)

- `LoginPage.jsx`: replace the email/password form with an email field + "Sign in with Google" button navigating to `${API_URL}/auth/google/login?email=...`.
- New `AuthCallbackPage.jsx` at route `/auth/callback`: reads `?code=`, calls `/auth/exchange`; on a full session, stores it and routes by role (`staff` → own directorate page, `dg`/`registrar` → general dashboard, `super_admin` → full access); on `needs_onboarding`, shows the 10-directorate picker and calls `/auth/onboarding/complete`.
- `AuthContext.jsx`: remove `login()`/`register()` password calls; add `exchangeCode()` and `completeOnboarding()`.
- Delete `SignUpPage.jsx` and the forgot/reset-password pages.

## Migration & Seed Strategy

- A migration (matching the project's existing raw-migration-script pattern, e.g. `migrate_google_sso.py`, alongside or replacing `migrate_directorate.py`) to: drop `password_hash`, add `google_id`, convert `role` and `directorate` to enum columns.
- Replace `app/seed.py`'s plaintext-password user list with real entries in `ADMIN_ACCOUNTS` (the user fills in actual DG/Registrar/Super Admin emails).

## Testing

- Unit tests: domain-restriction check, `ADMIN_ACCOUNTS` lookup precedence, onboarding-token issuance/consumption, `require_role`/`require_directorate_access` permission logic.
- Integration test for `/auth/exchange` and `/auth/onboarding/complete` with a mocked Google token-exchange/JWKS verification (real Google endpoints aren't reachable in CI).

## Open Items for the User

- Fill in real DG / Registrar / Super Admin emails into `ADMIN_ACCOUNTS` before deploying.
- Obtain/confirm the Google OAuth Client ID, Client Secret, and the exact redirect URI to register in Google Cloud Console (must exactly match `google_redirect_uri`).
