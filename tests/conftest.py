import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


async def _create_tables(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture
def db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    asyncio.run(_create_tables(engine))
    yield engine
    asyncio.run(engine.dispose())


@pytest.fixture
def session_maker(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest.fixture
def client(session_maker):
    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)  # no `with` block: skips the real-DB lifespan
    yield test_client
    app.dependency_overrides.clear()
