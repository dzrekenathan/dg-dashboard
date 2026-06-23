"""
Run once to seed initial users.
    uv run python -m app.seed
"""
import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal, engine
from app.database import Base
from app.models import User, SOVisibility
from app.core.security import hash_password


USERS = [
    {"email": "dg@clet.gov.gh",           "name": "Director General",        "password": "CLET@DG2026",    "role": "dg",         "directorate": None},
    {"email": "gsl@clet.gov.gh",           "name": "GSL Management",          "password": "CLET@GSL2026",   "role": "management", "directorate": "GSL"},
    {"email": "dti@clet.gov.gh",           "name": "DTI Management",          "password": "CLET@DTI2026",   "role": "management", "directorate": "DTI"},
    {"email": "cdt@clet.gov.gh",           "name": "CDT Management",          "password": "CLET@CDT2026",   "role": "management", "directorate": "CDT"},
    {"email": "aqai@clet.gov.gh",          "name": "AQAI Management",         "password": "CLET@AQAI2026",  "role": "management", "directorate": "AQAI"},
    {"email": "lrks@clet.gov.gh",          "name": "LRKS Management",         "password": "CLET@LRKS2026",  "role": "management", "directorate": "LRKS"},
    {"email": "ccp@clet.gov.gh",           "name": "CCP Management",          "password": "CLET@CCP2026",   "role": "management", "directorate": "CCP"},
    {"email": "pc@clet.gov.gh",            "name": "P&C Management",          "password": "CLET@PC2026",    "role": "management", "directorate": "P&C"},
    {"email": "rmf@clet.gov.gh",           "name": "RMF Management",          "password": "CLET@RMF2026",   "role": "management", "directorate": "RMF"},
    {"email": "sfl@clet.gov.gh",           "name": "SF&L Management",         "password": "CLET@SFL2026",   "role": "management", "directorate": "SF&L"},
    {"email": "ca@clet.gov.gh",            "name": "C&A Management",          "password": "CLET@CA2026",    "role": "management", "directorate": "C&A"},
    {"email": "management@clet.gov.gh",    "name": "Management User",         "password": "CLET@Mgmt2026",  "role": "management", "directorate": None},
]

SOS = ["SO1", "SO2", "SO3", "SO4"]


async def seed():
    # Create tables if they don't exist yet
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Seed users
        for u in USERS:
            exists = await db.execute(select(User).where(User.email == u["email"]))
            if not exists.scalar_one_or_none():
                db.add(User(
                    email=u["email"],
                    name=u["name"],
                    password_hash=hash_password(u["password"]),
                    role=u["role"],
                    directorate=u["directorate"],
                ))
                print(f"  ✓ Created user: {u['email']}")
            else:
                print(f"  – User already exists: {u['email']}")

        # Seed SO visibility
        for so in SOS:
            exists = await db.execute(select(SOVisibility).where(SOVisibility.so_number == so))
            if not exists.scalar_one_or_none():
                db.add(SOVisibility(so_number=so, is_visible=True))
                print(f"  ✓ Created visibility row: {so}")

        await db.commit()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
