"""
Request ID + access log JSON (doc 05 §7.5, Claude_api_respone.md §6).

- X-Request-ID: nhận từ client hoặc tự sinh `req_<8 hex>`, luôn trả lại trong response.
- Log JSON: timestamp, level, request_id, method, path, status, duration_ms, user_id.
- KHÔNG log body, token, header Authorization.
"""

import json
import logging
import secrets
import time
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"

access_logger = logging.getLogger("app.access")


def new_request_id() -> str:
    return f"req_{secrets.token_hex(4)}"


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = incoming if 0 < len(incoming) <= 64 else new_request_id()
        request.state.request_id = request_id
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            access_logger.info(
                json.dumps(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "level": "INFO",
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status": status,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                        "user_id": getattr(request.state, "user_id", None),
                    },
                    ensure_ascii=False,
                )
            )
