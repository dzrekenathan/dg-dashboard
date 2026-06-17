from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import settings
from app.database import engine, AsyncSessionLocal
from app.database import Base
from app.models import User, SOVisibility
from app.core.security import hash_password
from app.routers import auth, tasks, so_visibility, ws, activity_tracking


# ── Startup: create tables + seed default data ────────────────────────────────

async def _bootstrap():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        default_users = [
            {"email": "dg@clet.gov.gh",        "name": "Director General", "password": "CLET@DG2026",   "role": "dg"},
            {"email": "management@clet.gov.gh", "name": "Management User",  "password": "CLET@Mgmt2026", "role": "management"},
        ]
        for u in default_users:
            exists = (await db.execute(select(User).where(User.email == u["email"]))).scalar_one_or_none()
            if not exists:
                db.add(User(email=u["email"], name=u["name"], password_hash=hash_password(u["password"]), role=u["role"]))

        for so in ["SO1", "SO2", "SO3", "SO4"]:
            exists = (await db.execute(select(SOVisibility).where(SOVisibility.so_number == so))).scalar_one_or_none()
            if not exists:
                db.add(SOVisibility(so_number=so, is_visible=True))

        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _bootstrap()
    yield
    await engine.dispose()


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="CLET M&E Dashboard API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://dgreneral-dashboard.netlify.app"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(so_visibility.router)
app.include_router(ws.router)
app.include_router(activity_tracking.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "CLET M&E Dashboard API"}
