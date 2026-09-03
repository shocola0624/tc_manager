from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from errors import AppError, install_exception_handlers


def _build_client() -> TestClient:
    app = FastAPI()
    install_exception_handlers(app)

    @app.get("/app-error")
    async def raise_app_error():
        raise AppError(403, "insufficient_role", "nope")

    @app.get("/plain-http-error")
    async def raise_plain():
        raise HTTPException(status_code=404)

    @app.get("/boom")
    async def raise_boom():
        raise RuntimeError("boom")

    # /boom は意図的に未処理の例外を投げて汎用ハンドラを検証する。
    # TestClient は既定でサーバー側例外を再送出するため、ここでは無効化する。
    return TestClient(app, raise_server_exceptions=False)


def test_app_error_uses_its_explicit_code():
    client = _build_client()

    response = client.get("/app-error")

    assert response.status_code == 403
    assert response.json() == {"error": {"code": "insufficient_role", "detail": "nope"}}


def test_plain_http_exception_falls_back_to_status_code_name():
    client = _build_client()

    response = client.get("/plain-http-error")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_unhandled_exception_returns_generic_internal_error_without_leaking_detail():
    client = _build_client()

    response = client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {"error": {"code": "internal_error", "detail": None}}
