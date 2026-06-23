"""
One-off migration: add directorate column to users table.
Run with: uv run python migrate_directorate.py
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings

async def migrate():
    engine = create_async_engine(
        settings.database_url,
        echo=True,
        connect_args={"ssl": "require"},
    )
    async with engine.begin() as conn:
        await conn.execute(
            __import__("sqlalchemy").text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS directorate VARCHAR(20);"
            )
        )
        result = await conn.execute(
            __import__("sqlalchemy").text(
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_name = 'users' AND column_name = 'directorate';"
            )
        )
        rows = result.fetchall()
        if rows:
            print(f"\nMigration verified: {rows[0]}")
        else:
            print("\nERROR: column not found after migration!")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate())
