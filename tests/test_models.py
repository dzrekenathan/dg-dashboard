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
