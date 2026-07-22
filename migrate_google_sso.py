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
