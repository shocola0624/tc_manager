from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

_STATUS_CODE_FALLBACK_CODES = {
    401: "not_authenticated",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
}


class AppError(HTTPException):
    """業務エラー用の例外。code は安定した機械可読キーで、フロントは t(`errors.${code}`) で表示文言に変換する。

    detail は非翻訳のデバッグ用文字列であり、UI にそのまま出す前提ではない。
    """

    def __init__(self, status_code: int, code: str, detail: str | None = None) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.code = code


def _error_response(status_code: int, code: str, detail: str | None) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "detail": detail}})


async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code = getattr(exc, "code", None) or _STATUS_CODE_FALLBACK_CODES.get(exc.status_code, "error")
    detail = exc.detail if isinstance(exc.detail, str) else None
    return _error_response(exc.status_code, code, detail)


async def _validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return _error_response(422, "validation_error", str(exc))


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error while processing %s %s", request.method, request.url.path)
    return _error_response(500, "internal_error", None)


def install_exception_handlers(app: FastAPI) -> None:
    """アプリ全体のエラーレスポンス形式を {"error": {"code": ..., "detail": ...}} に統一する"""
    app.add_exception_handler(HTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)
