import asyncio

from datetime import date as date_cls

from sqlalchemy import text

from app.models import User, UserRole, Directorate, SystemProgress, PhaseDeadline


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


def test_system_progress_defaults(session_maker):
    async def scenario():
        async with session_maker() as session:
            row = SystemProgress(system_code="S014")
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    row = asyncio.run(scenario())
    assert row.status == "Not Started"
    assert row.progress_pct == 0


def test_phase_deadline_round_trips_date(session_maker):
    async def scenario():
        async with session_maker() as session:
            row = PhaseDeadline(phase=1, deadline=date_cls(2026, 6, 30))
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

    row = asyncio.run(scenario())
    assert row.phase == 1
    assert row.deadline == date_cls(2026, 6, 30)
