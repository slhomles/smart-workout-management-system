from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.errors import BadRequestError, register_exception_handlers


class Payload(BaseModel):
    value: int


def _app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/echo")
    async def echo(body: Payload) -> Payload:
        return body

    @app.get("/bad")
    async def bad() -> None:
        raise BadRequestError("Ảnh không đọc được", [{"field": "image", "message": "hỏng", "code": "invalid"}])

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("chi tiết nội bộ")

    return app


def test_unknown_route_uses_http_status_code(client: TestClient) -> None:
    res = client.get("/khong-co")

    assert res.status_code == 404
    assert res.json()["error"]["code"] == "http_404"


def test_validation_error_lists_fields() -> None:
    res = TestClient(_app()).post("/echo", json={"value": "abc"})

    assert res.status_code == 422
    error = res.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"][0]["field"] == "value"


def test_app_error_keeps_code_and_details() -> None:
    res = TestClient(_app()).get("/bad")

    assert res.status_code == 400
    assert res.json()["error"]["code"] == "bad_request"
    assert res.json()["error"]["details"] == [{"field": "image", "message": "hỏng", "code": "invalid"}]


def test_unexpected_error_hides_internal_message() -> None:
    res = TestClient(_app(), raise_server_exceptions=False).get("/boom")

    assert res.status_code == 500
    assert res.json()["error"]["code"] == "internal_error"
    assert "chi tiết nội bộ" not in res.text
