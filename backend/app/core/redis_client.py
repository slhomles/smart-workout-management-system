"""
Kết nối Redis async dùng chung (doc 05 §7.2 mục 3): cache quyền, rate limit.

Redis KHÔNG phải nguồn dữ liệu chính (design-overview §2): mất Redis không được làm mất dữ liệu,
nên nơi gọi phải chịu được lỗi Redis (xem permission_service).

Mỗi event loop một client: client của redis.asyncio gắn với loop đã tạo ra nó, nên nếu dùng chung
giữa các loop (vd mỗi test một loop) sẽ lỗi "Event loop is closed".
"""

import asyncio
from weakref import WeakKeyDictionary

from redis.asyncio import Redis

from app.core.config import get_settings

_clients: "WeakKeyDictionary[asyncio.AbstractEventLoop, Redis]" = WeakKeyDictionary()


def get_redis() -> Redis:
    """Client Redis của event loop hiện tại (tạo khi cần). Dùng làm FastAPI dependency hoặc gọi trực tiếp."""
    loop = asyncio.get_running_loop()
    client = _clients.get(loop)
    if client is None:
        settings = get_settings()
        client = Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
        )
        _clients[loop] = client
    return client


async def close_redis() -> None:
    """Đóng client của event loop hiện tại (gọi khi tắt ứng dụng)."""
    client = _clients.pop(asyncio.get_running_loop(), None)
    if client is not None:
        await client.aclose()
