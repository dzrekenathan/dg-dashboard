# CLET M&E Dashboard API

Backend API for the CLET (Ghana) Monitoring & Evaluation Dashboard — tracks Strategic Objective (SO) tasks and activities, exposes real-time updates over WebSocket, and supports Excel import/export of the SO task matrix.

Built with **FastAPI**, **SQLAlchemy 2.0 (async)**, and **PostgreSQL**.

## Tech stack

- **FastAPI** — HTTP API framework
- **SQLAlchemy 2.0 (asyncio)** + **asyncpg** — async ORM / Postgres driver
- **Alembic** — database migrations
- **python-jose** — JWT auth
- **passlib / bcrypt** — password hashing
- **openpyxl** — `.xlsx` import/export
- **websockets** — real-time task/visibility broadcast
- **uv** — dependency management (also used in the Docker build)

## Project structure

```
app/
  main.py                    FastAPI app, CORS, startup bootstrap (tables + default users/SOs)
  config.py                  Settings loaded from .env (pydantic-settings)
  database.py                Async engine/session, Base, get_db dependency
  models.py                  SQLAlchemy models: User, Task, ActivityTracking, ActivityComment, SOVisibility
  schemas.py                 Pydantic request/response models
  seed.py                    Standalone script to seed directorate users + SO visibility rows
  core/
    security.py               Password hashing, JWT create/decode, get_current_user, require_management
    ws_manager.py              WebSocket connection manager (broadcast helper)
  routers/
    auth.py                    /auth      — login, register, forgot/reset password, /auth/me
    tasks.py                    /tasks     — list, update, Excel import, Excel export
    so_visibility.py            /so-visibility — get/toggle SO1-4 visibility
    activity_tracking.py        /activity-tracking — per-task activity status, comments, recent activity feed
    ws.py                        /ws       — WebSocket endpoint for live updates
alembic/                       Migration environment + versions
Dockerfile
docker-compose.yml            Postgres + API services
.env.example
```

## Getting started

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- PostgreSQL 16 (or use the provided `docker-compose.yml`)

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in values:

```bash
cp .env.example .env
```

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | Async Postgres DSN, e.g. `postgresql+asyncpg://user:pass@host:5432/db` | *(required)* |
| `SECRET_KEY` | JWT signing secret — set a long random value in production | `change-me-in-production` |
| `ALGORITHM` | JWT signing algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime in minutes | `10080` (7 days) |
| `FRONTEND_URL` | Frontend origin (used for reference; CORS list is also set in `main.py`) | `https://dgreneral-dashboard.netlify.app` |

### 3. Start Postgres

Using Docker:

```bash
docker compose up -d postgres
```

Or point `DATABASE_URL` at your own instance.

### 4. Run the API

```bash
uv run uvicorn app.main:app --reload
```

On startup, the app automatically creates all tables and seeds two default users (`dg@clet.gov.gh`, `management@clet.gov.gh`) and SO1-SO4 visibility rows if they don't already exist (see `app/main.py`).

For the fuller set of directorate-specific accounts (GSL, DTI, CDT, AQAI, LRKS, CCP, P&C, RMF, SF&L, C&A), run the seed script once:

```bash
uv run python -m app.seed
```

The API is now available at `http://localhost:8000`, with interactive docs at `http://localhost:8000/docs`.

### Running with Docker Compose (full stack)

```bash
docker compose up --build
```

This starts Postgres and the API together, with the API reading its config from `.env`.

## Database migrations

Migrations are managed with Alembic (`alembic.ini`, `alembic/`).

```bash
# Apply migrations
uv run alembic upgrade head

# Create a new migration after changing models.py
uv run alembic revision --autogenerate -m "description"
```

Note: `app/main.py` also calls `Base.metadata.create_all` on startup, so a fresh database gets its schema without running migrations. Use Alembic for schema changes on an existing database.

## Authentication & roles

- Auth is JWT bearer token based (`Authorization: Bearer <token>`), issued via `/auth/login` or `/auth/register`.
- Two roles exist:
  - `dg` — Director General, read access
  - `management` — can update tasks, toggle SO visibility, and import Excel data (`require_management` dependency)
- Users optionally belong to a `directorate` (e.g. `GSL`, `DTI`, `CDT`, ...).
- Password reset uses a short-lived (15 min) JWT with `purpose: password_reset` returned from `/auth/forgot-password` and consumed by `/auth/reset-password`.

## API overview

All endpoints except `/health`, `/auth/login`, `/auth/register`, `/auth/forgot-password`, `/auth/reset-password`, and `/ws` require a valid bearer token.

### Auth — `/auth`
| Method | Path | Description | Role |
|---|---|---|---|
| POST | `/auth/login` | Log in, returns JWT + user info | — |
| POST | `/auth/register` | Register a new `management` user | — |
| POST | `/auth/forgot-password` | Issue a password reset token | — |
| POST | `/auth/reset-password` | Reset password using a reset token | — |
| GET | `/auth/me` | Current authenticated user | any |

### Tasks — `/tasks`
| Method | Path | Description | Role |
|---|---|---|---|
| GET | `/tasks` | List tasks, optional `so_number` filter | any |
| PATCH | `/tasks/{task_id}` | Update a task's status/progress/notes/etc. (broadcasts `TASK_UPDATED`) | management |
| POST | `/tasks/import` | Import tasks from an `.xlsx` SO Matrix file, replacing tasks for affected SOs (broadcasts `TASKS_UPDATED`) | management |
| GET | `/tasks/export` | Export tasks (optional `so_number` filter) to `.xlsx` | any |

### SO Visibility — `/so-visibility`
| Method | Path | Description | Role |
|---|---|---|---|
| GET | `/so-visibility` | Get visibility map for SO1-SO4 | any |
| PATCH | `/so-visibility/{so_number}` | Toggle visibility for one SO (broadcasts `VISIBILITY_UPDATED`) | management |

### Activity Tracking — `/activity-tracking`
| Method | Path | Description | Role |
|---|---|---|---|
| GET | `/activity-tracking/stats` | Total comment count | any |
| GET | `/activity-tracking/recent` | 20 most recent comments across all tasks | any |
| GET | `/activity-tracking/{task_id}` | Activity tracking rows + comments for a task | any |
| PATCH | `/activity-tracking/{task_id}/{activity_ref}` | Upsert status/progress/assignee/target date for an activity | any |
| POST | `/activity-tracking/{task_id}/{activity_ref}/comments` | Add a comment to an activity | any |

### WebSocket — `/ws`
Clients connect to `/ws` to receive real-time broadcast messages:
- `TASK_UPDATED` / `TASKS_UPDATED` — task data changed
- `VISIBILITY_UPDATED` — SO visibility changed

Send `"ping"` to receive `"pong"` as a keepalive.

### Health
`GET /health` → `{"status": "ok", "service": "CLET M&E Dashboard API"}`

## Excel import/export format

Import/export use a sheet named `SO Matrix` (falls back to the active sheet) with these columns:

```
SO #, Strategic Objective, Thematic Area, Task, Reference Nos., Activities & Sub-Activities,
Timeframe, Responsibility, Outputs / Deliverables, Outcomes / Impact, Risks & Mitigation,
Budget, Status, Progress %, Assigned To, Target Date, Notes / Comments, Last Updated, Updated By
```

Import replaces all existing tasks for any SO number present in the uploaded file (or only the SO passed via `?so_number=` if provided). Valid `Status` values: `Not Started`, `In Progress`, `Completed`, `On Hold`, `At Risk`, `Cancelled` — anything else falls back to `Not Started`.

## Deployment notes

- CORS in `app/main.py` currently allows the production frontend origin plus `"*"` — tighten this for production if credentials/cookies are ever introduced.
- Set a strong, unique `SECRET_KEY` in production; the default is insecure.
- The default seeded passwords in `main.py`/`seed.py` (e.g. `CLET@DG2026`) are meant for initial setup only — change them after first login.
