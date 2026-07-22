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
