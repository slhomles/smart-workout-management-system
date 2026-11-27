"""Entry point của AI service: `uvicorn app.main:app --port 8001` (cwd = ai-services/)."""

import secrets

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import RequestResponseEndpoint

from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import REQUEST_ID_HEADER, register_exception_handlers
from app.core.logging import setup_logging


async def _request_id(request: Request, call_next: RequestResponseEndpoint) -> Response:
    rid = request.headers.get(REQUEST_ID_HEADER) or f"req_{secrets.token_hex(4)}"
    request.state.request_id = rid
    response = await call_next(request)
    response.headers[REQUEST_ID_HEADER] = rid
    return response


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)
    app = FastAPI(title=settings.APP_NAME, version="0.1.0")
    app.middleware("http")(_request_id)
    register_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
