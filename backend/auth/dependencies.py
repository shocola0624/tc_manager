from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Depends, Request
from pydantic import ValidationError

from errors import AppError
from repositories import get_users_repository
from sheets.repository import SheetRepository
from sheets.schemas import Role, User

from .discord_client import DiscordBotClient, DiscordOAuthClient
from .session import SESSION_COOKIE, SessionSigner

__all__ = [
    "find_raw_user",
    "identity_from_cookie",
    "resolve_current_user",
    "get_signer",
    "get_users_repository",
    "get_oauth_client",
    "get_bot_client",
    "get_auth_settings",
    "get_session_identity",
    "get_current_user",
    "require_role",
]


def find_raw_user(users_repo: SheetRepository, discord_user_id: str) -> dict[str, str] | None:
    for record in users_repo.read_all():
        if record.get("discord_user_id") == discord_user_id:
            return record
    return None


def identity_from_cookie(signer: SessionSigner, cookie_value: str | None) -> str:
    """session cookie の中身を検証し discord_user_id を返す。無効なら 401。"""
    if cookie_value is None:
        raise AppError(401, "not_authenticated", "not authenticated")
    payload = signer.unsign(SESSION_COOKIE, cookie_value)
    if payload is None or "discord_user_id" not in payload:
        raise AppError(401, "not_authenticated", "not authenticated")
    return payload["discord_user_id"]


def resolve_current_user(identity: str, users_repo: SheetRepository) -> User:
    """users シートを都度読み直し、登録完了・is_active を検査したうえで返す。"""
    raw = find_raw_user(users_repo, identity)
    if raw is None:
        raise AppError(401, "user_not_found", "user not found")
    try:
        user = User.model_validate(raw)
    except ValidationError as exc:
        raise AppError(403, "invalid_user_row", "invalid user row") from exc
    if user.registered_at is None:
        raise AppError(403, "registration_incomplete", "registration incomplete")
    if not user.is_active:
        raise AppError(403, "inactive_user", "inactive user")
    return user


def get_signer(request: Request) -> SessionSigner:
    return request.app.state.signer


def get_oauth_client(request: Request) -> DiscordOAuthClient:
    return request.app.state.oauth_client


def get_bot_client(request: Request) -> DiscordBotClient:
    return request.app.state.bot_client


def get_auth_settings(request: Request):
    return request.app.state.auth_settings


async def get_session_identity(
    request: Request, signer: SessionSigner = Depends(get_signer)
) -> str:
    return identity_from_cookie(signer, request.cookies.get(SESSION_COOKIE.name))


async def get_current_user(
    identity: str = Depends(get_session_identity),
    users_repo: SheetRepository = Depends(get_users_repository),
) -> User:
    return resolve_current_user(identity, users_repo)


def require_role(*roles: Role) -> Callable[..., Awaitable[User]]:
    """指定した role のいずれかを持つユーザーのみ通す依存関数を返す"""

    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise AppError(403, "insufficient_role", "insufficient role")
        return user

    return dependency
