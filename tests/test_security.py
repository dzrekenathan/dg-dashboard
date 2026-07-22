import asyncio

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.security import create_access_token, require_role
from app.models import User, UserRole


def _make_user(session_maker, role, directorate=None, email="person@gslaw.edu.gh"):
    async def scenario():
        async with session_maker() as session:
            user = User(email=email, name="Person", google_id="g-1", role=role, directorate=directorate)
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user
    return asyncio.run(scenario())


def _mount_probe_route(app, session_maker):
    from app.database import get_db

    async def override_get_db():
        async with session_maker() as session:
            yield session
    app.dependency_overrides[get_db] = override_get_db

    @app.get("/__probe/staff-or-admin")
    async def probe(user: User = Depends(require_role(UserRole.STAFF, UserRole.SUPER_ADMIN))):
        return {"email": user.email}


def test_require_role_allows_matching_role(session_maker):
    user = _make_user(session_maker, UserRole.STAFF)
    app = FastAPI()
    _mount_probe_route(app, session_maker)
    token = create_access_token({"sub": user.id, "role": user.role.value})

    response = TestClient(app).get("/__probe/staff-or-admin", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "person@gslaw.edu.gh"


def test_require_role_rejects_non_matching_role(session_maker):
    user = _make_user(session_maker, UserRole.DG, email="dg@gslaw.edu.gh")
    app = FastAPI()
    _mount_probe_route(app, session_maker)
    token = create_access_token({"sub": user.id, "role": user.role.value})

    response = TestClient(app).get("/__probe/staff-or-admin", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
