"""
Pytest fixtures (doc 05 §10).

- db: session gắn vào một transaction ngoài; service commit = release savepoint;
  cuối test rollback toàn bộ → test không để lại dữ liệu và không phụ thuộc nhau.
- client: AsyncClient gắn app, dùng session `db`.
- auth_headers(persona): đăng nhập persona seed (mật khẩu Demo@123) → header Bearer.
"""

from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.database import get_db
from app.main import app

SEED_PASSWORD = "Demo@123"


def persona_id(nn: int) -> str:
    return f"5eed0000-0000-4000-8000-{nn:012d}"


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(get_settings().DATABASE_URL, poolclass=NullPool)
    async with engine.connect() as conn:
        outer = await conn.begin()
        session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)

        async def _override() -> AsyncGenerator[AsyncSession, None]:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

        app.dependency_overrides[get_db] = _override
        try:
            yield session
        finally:
            app.dependency_overrides.pop(get_db, None)
            await session.close()
            await outer.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient):
    async def _login(persona: str = "demo") -> dict[str, str]:
        res = await client.post(
            "/api/v1/auth/login",
            json={"email": f"{persona}@smartworkout.local", "password": SEED_PASSWORD, "device": {"platform": "web"}},
        )
        assert res.status_code == 200, res.text
        return {"Authorization": f"Bearer {res.json()['access_token']}"}

    return _login
