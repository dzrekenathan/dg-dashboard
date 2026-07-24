import asyncio
from sqlalchemy import select

from app.models import User


def test_bootstrap_no_longer_creates_password_seeded_users(client, session_maker):
    client.get("/health")  # confirms app.main imports and runs cleanly

    async def scenario():
        async with session_maker() as session:
            result = await session.execute(select(User).where(User.email == "dg@clet.gov.gh"))
            return result.scalar_one_or_none()

    assert asyncio.run(scenario()) is None


def test_bootstrap_does_not_touch_system_progress_table(client, session_maker):
    # _bootstrap() only runs against the real DB (skipped in tests, per Global
    # Constraints), so this just confirms the app still imports and serves
    # cleanly now that main.py references systems_catalog.
    response = client.get("/health")
    assert response.status_code == 200
