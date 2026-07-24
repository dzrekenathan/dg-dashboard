import asyncio

from app.core.security import create_access_token
from app.models import User, UserRole, Directorate


def _make_user(session_maker, role, directorate=None, email="person@gslaw.edu.gh"):
    async def scenario():
        async with session_maker() as session:
            user = User(email=email, name="Person", google_id="g-1", role=role, directorate=directorate)
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user
    return asyncio.run(scenario())


def _auth_header(user):
    token = create_access_token({"sub": user.id, "role": user.role.value})
    return {"Authorization": f"Bearer {token}"}


def test_get_status_empty_list(client):
    response = client.get("/systems/status")
    assert response.status_code == 401  # no auth header -> requires login


def test_staff_can_update_own_directorate_system(client, session_maker):
    user = _make_user(session_maker, UserRole.STAFF, Directorate.DTI)

    response = client.patch(
        "/systems/status/S205",
        json={"status": "In Progress", "progress_pct": 40},
        headers=_auth_header(user),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["system_code"] == "S205"
    assert body["status"] == "In Progress"
    assert body["progress_pct"] == 40

    listing = client.get("/systems/status", headers=_auth_header(user))
    assert listing.status_code == 200
    assert any(row["system_code"] == "S205" for row in listing.json())


def test_staff_cannot_update_other_directorate_system(client, session_maker):
    user = _make_user(session_maker, UserRole.STAFF, Directorate.GSL, email="gsl@gslaw.edu.gh")

    # S205 resolves to DTI (cluster C11), not GSL
    response = client.patch(
        "/systems/status/S205",
        json={"status": "Completed"},
        headers=_auth_header(user),
    )

    assert response.status_code == 403


def test_dg_can_update_any_system(client, session_maker):
    user = _make_user(session_maker, UserRole.DG, email="dg@gslaw.edu.gh")

    response = client.patch(
        "/systems/status/S205",
        json={"status": "Completed", "progress_pct": 100},
        headers=_auth_header(user),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "Completed"


def test_get_deadlines_returns_seeded_rows(client, session_maker):
    user = _make_user(session_maker, UserRole.STAFF, Directorate.DTI)
    response = client.get("/systems/deadlines", headers=_auth_header(user))
    assert response.status_code == 200
    assert response.json() == []  # nothing seeded in the isolated test DB


def test_staff_cannot_update_deadline(client, session_maker):
    user = _make_user(session_maker, UserRole.STAFF, Directorate.DTI)
    response = client.patch(
        "/systems/deadlines/1",
        json={"deadline": "2026-06-30"},
        headers=_auth_header(user),
    )
    assert response.status_code == 403


def test_registrar_can_update_deadline_and_it_broadcasts(client, session_maker, monkeypatch):
    broadcasts = []

    async def fake_broadcast(message):
        broadcasts.append(message)

    from app.core import ws_manager
    monkeypatch.setattr(ws_manager.manager, "broadcast", fake_broadcast)

    user = _make_user(session_maker, UserRole.REGISTRAR, email="registrar@gslaw.edu.gh")

    response = client.patch(
        "/systems/deadlines/2",
        json={"deadline": "2026-09-30"},
        headers=_auth_header(user),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["phase"] == 2
    assert body["deadline"] == "2026-09-30"
    assert len(broadcasts) == 1
    assert broadcasts[0]["type"] == "PHASE_DEADLINE_UPDATED"
    assert broadcasts[0]["payload"]["phase"] == 2
