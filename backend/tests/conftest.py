"""
Pytest fixtures (doc 05 §10).

- db: session gắn vào một transaction ngoài; service commit = release savepoint;
  cuối test rollback toàn bộ → test không để lại dữ liệu và không phụ thuộc nhau.
- client: AsyncClient gắn app, dùng session `db`.
- auth_headers(persona): header Bearer của persona seed (token tạo trực tiếp, xem bên dưới).

Tốc độ: DB dùng chung nằm trên VM (doc 05 §8.2), mỗi truy vấn mất ~100 ms qua mạng. Vì vậy cả phiên
test dùng MỘT event loop và MỘT kết nối DB: mở kết nối mới cho từng test tốn 2–4 giây (SQLAlchemy và
asyncpg chạy lại các truy vấn khởi tạo, đọc lại kiểu enum/citext). Mỗi test vẫn có transaction riêng
và rollback ở cuối, nên vẫn cô lập dữ liệu như trước.
"""

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app

SEED_PASSWORD = "Demo@123"


def persona_id(nn: int) -> str:
    return f"5eed0000-0000-4000-8000-{nn:012d}"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    # Mọi test async chạy chung event loop của phiên, để dùng lại được kết nối DB dùng chung.
    session_loop = pytest.mark.asyncio(loop_scope="session")
    for item in items:
        if pytest_asyncio.is_async_test(item):
            item.add_marker(session_loop, append=False)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_connection() -> AsyncGenerator[AsyncConnection, None]:
    engine = create_async_engine(get_settings().DATABASE_URL, poolclass=NullPool)
    async with engine.connect() as conn:
        yield conn
    await engine.dispose()


@pytest_asyncio.fixture
async def db(db_connection: AsyncConnection) -> AsyncGenerator[AsyncSession, None]:
    outer = await db_connection.begin()
    session = AsyncSession(bind=db_connection, join_transaction_mode="create_savepoint", expire_on_commit=False)

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


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_headers(db: AsyncSession):
    """Token tạo trực tiếp thay vì gọi /auth/login: đăng nhập thật tốn bcrypt + ~10 truy vấn mỗi lần.

    get_current_user chỉ cần `sub` là user còn hoạt động; quyền luôn đọc từ DB (doc 04 §2.4), không từ
    claim `roles`. Luồng đăng nhập thật được kiểm tra riêng trong test_auth_api.py.
    """

    async def _headers(persona: str = "demo") -> dict[str, str]:
        user_id = await db.scalar(
            text("SELECT id FROM auth.users WHERE email = :email AND deleted_at IS NULL"),
            {"email": f"{persona}@smartworkout.local"},
        )
        assert user_id is not None, f"không có persona seed '{persona}'"
        token = create_access_token(user_id=user_id, roles=[], device_id=uuid.uuid4())
        return {"Authorization": f"Bearer {token}"}

    return _headers
