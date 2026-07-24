from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import settings
from app.database import engine, AsyncSessionLocal
from app.database import Base
from app.models import SOVisibility, PhaseDeadline
from app.routers import auth, tasks, so_visibility, ws, activity_tracking, systems_status, admin
from app.systems_catalog import load_phase_deadlines_seed


# ── Startup: create tables + seed default data ────────────────────────────────

async def _bootstrap():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        for so in ["SO1", "SO2", "SO3", "SO4"]:
            exists = (await db.execute(select(SOVisibility).where(SOVisibility.so_number == so))).scalar_one_or_none()
            if not exists:
                db.add(SOVisibility(so_number=so, is_visible=True))

        for phase, deadline in load_phase_deadlines_seed().items():
            exists = (await db.execute(select(PhaseDeadline).where(PhaseDeadline.phase == phase))).scalar_one_or_none()
            if not exists:
                db.add(PhaseDeadline(phase=phase, deadline=deadline))

        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _bootstrap()
    yield
    await engine.dispose()


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="GSL M&E Dashboard API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://dgreneral-dashboard.netlify.app", "*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(so_visibility.router)
app.include_router(ws.router)
app.include_router(activity_tracking.router)
app.include_router(systems_status.router)
app.include_router(admin.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "GSL M&E Dashboard API"}