from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from discord_bot.write_log import log_write
from errors import AppError
from sheets.repository import SheetRepository
from sheets.schemas import User

from .config import AuthSettings
from .dependencies import (
    find_raw_user,
    get_auth_settings,
    get_bot_client,
    get_current_user,
    get_oauth_client,
    get_signer,
    get_users_repository,
    resolve_current_user,
)
from .discord_client import DiscordBotClient, DiscordOAuthClient, DiscordOAuthError
from .role_resolution import resolve_role
from .schemas import CurrentUserResponse, RegisterRequest, UpdateProfileRequest
from .session import (
    PENDING_COOKIE,
    SESSION_COOKIE,
    STATE_COOKIE,
    SessionSigner,
    clear_cookie,
    set_cookie,
)
from timeutil import now_iso8601

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/discord/login")
async def login(
    signer: SessionSigner = Depends(get_signer),
    oauth_client: DiscordOAuthClient = Depends(get_oauth_client),
    settings: AuthSettings = Depends(get_auth_settings),
) -> RedirectResponse:
    state = secrets.token_urlsafe(32)
    response = RedirectResponse(url=oauth_client.build_authorize_url(state), status_code=302)
    set_cookie(response, STATE_COOKIE, signer, {"state": state}, secure=settings.cookie_secure)
    return response


@router.get("/discord/callback")
async def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    signer: SessionSigner = Depends(get_signer),
    oauth_client: DiscordOAuthClient = Depends(get_oauth_client),
    bot_client: DiscordBotClient = Depends(get_bot_client),
    users_repo: SheetRepository = Depends(get_users_repository),
    settings: AuthSettings = Depends(get_auth_settings),
) -> RedirectResponse:
    def failure(reason: str) -> RedirectResponse:
        resp = RedirectResponse(
            url=f"{settings.frontend_base_url}/login?error={reason}", status_code=302
        )
        clear_cookie(resp, STATE_COOKIE)
        return resp

    if error is not None:
        return failure("access_denied")

    state_token = request.cookies.get(STATE_COOKIE.name)
    state_payload = signer.unsign(STATE_COOKIE, state_token) if state_token else None
    if state is None or state_payload is None or state_payload.get("state") != state:
        return failure("oauth_failed")

    if code is None:
        return failure("oauth_failed")

    try:
        access_token = await oauth_client.exchange_code(code)
        discord_user = await oauth_client.fetch_current_user(access_token)
    except DiscordOAuthError:
        return failure("oauth_failed")

    raw_user = find_raw_user(users_repo, discord_user.id)

    if raw_user is None or not raw_user.get("registered_at", "").strip():
        response = RedirectResponse(url=f"{settings.frontend_base_url}/register", status_code=302)
        clear_cookie(response, STATE_COOKIE)
        set_cookie(
            response,
            PENDING_COOKIE,
            signer,
            {"discord_user_id": discord_user.id},
            secure=settings.cookie_secure,
        )
        return response

    try:
        user = User.model_validate(raw_user)
    except ValidationError:
        return failure("invalid_user_row")

    if not user.is_active:
        return failure("inactive")

    # ログインのたびに Discord ロールと再同期する(CLAUDE.md §6)。
    # Discord 側が一時的に応答しない場合でも、既存のシート上の role でログイン自体は継続する。
    try:
        role_ids = await bot_client.fetch_member_role_ids(discord_user.id)
        resolved_role = resolve_role(role_ids, settings)
        if resolved_role != user.role:
            await log_write(
                lambda: users_repo.update_by_key(
                    "discord_user_id", discord_user.id, {"role": resolved_role.value}
                ),
                bot_client=bot_client,
                channel_id=settings.discord_log_channel_id,
                actor_name=user.name,
                actor_id=discord_user.id,
                sheet_name="users",
                operation="update(role resync)",
                record={"discord_user_id": discord_user.id, "role": resolved_role.value},
            )
    except DiscordOAuthError:
        pass

    response = RedirectResponse(url=f"{settings.frontend_base_url}/", status_code=302)
    clear_cookie(response, STATE_COOKIE)
    set_cookie(
        response,
        SESSION_COOKIE,
        signer,
        {"discord_user_id": discord_user.id},
        secure=settings.cookie_secure,
    )
    return response


@router.post("/register", response_model=CurrentUserResponse)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    signer: SessionSigner = Depends(get_signer),
    bot_client: DiscordBotClient = Depends(get_bot_client),
    users_repo: SheetRepository = Depends(get_users_repository),
    settings: AuthSettings = Depends(get_auth_settings),
) -> CurrentUserResponse:
    pending_token = request.cookies.get(PENDING_COOKIE.name)
    pending_payload = signer.unsign(PENDING_COOKIE, pending_token) if pending_token else None
    if pending_payload is None or "discord_user_id" not in pending_payload:
        raise AppError(401, "registration_session_expired", "registration session expired")
    discord_user_id = pending_payload["discord_user_id"]

    raw_user = find_raw_user(users_repo, discord_user_id)
    if raw_user is not None and raw_user.get("registered_at", "").strip():
        raise AppError(409, "already_registered", "already registered")

    # role は本人が選べない。Discord ロールから自動算出する(CLAUDE.md §6)。
    try:
        role_ids = await bot_client.fetch_member_role_ids(discord_user_id)
    except DiscordOAuthError:
        role_ids = None
    role = resolve_role(role_ids, settings)

    record = {
        "discord_user_id": discord_user_id,
        "name": payload.name,
        "role": role.value,
        "is_active": "TRUE",
        "locale": "ja",
        "registered_at": now_iso8601(),
    }
    await log_write(
        lambda: users_repo.upsert_by_key("discord_user_id", discord_user_id, record),
        bot_client=bot_client,
        channel_id=settings.discord_log_channel_id,
        actor_name=payload.name,
        actor_id=discord_user_id,
        sheet_name="users",
        operation="upsert(register)",
        record=record,
    )

    clear_cookie(response, PENDING_COOKIE)
    set_cookie(
        response,
        SESSION_COOKIE,
        signer,
        {"discord_user_id": discord_user_id},
        secure=settings.cookie_secure,
    )

    return CurrentUserResponse(
        discord_user_id=discord_user_id,
        name=payload.name,
        role=role,
        is_active=True,
        locale="ja",
    )


@router.post("/logout")
async def logout(response: Response) -> dict[str, bool]:
    clear_cookie(response, SESSION_COOKIE)
    return {"ok": True}


@router.get("/me", response_model=CurrentUserResponse)
async def me(
    request: Request,
    signer: SessionSigner = Depends(get_signer),
    users_repo: SheetRepository = Depends(get_users_repository),
) -> CurrentUserResponse:
    """フロントエンドの AuthProvider が画面状態(未ログイン/登録待ち/ログイン済み/無効)を
    判定する唯一の窓口。session cookie が無くても pending cookie があれば
    "registration_incomplete" を返し、コールバック直後の /register 表示につなげる
    (session cookie は本登録完了までは発行されないため、get_current_user だけでは
    「登録待ち」を判定できない)。"""
    session_token = request.cookies.get(SESSION_COOKIE.name)
    session_payload = signer.unsign(SESSION_COOKIE, session_token) if session_token else None
    if session_payload is not None and "discord_user_id" in session_payload:
        user = resolve_current_user(session_payload["discord_user_id"], users_repo)
        return CurrentUserResponse(
            discord_user_id=user.discord_user_id,
            name=user.name,
            role=user.role,
            is_active=user.is_active,
            locale=user.locale,
            grade=user.grade,
        )

    pending_token = request.cookies.get(PENDING_COOKIE.name)
    pending_payload = signer.unsign(PENDING_COOKIE, pending_token) if pending_token else None
    if pending_payload is not None and "discord_user_id" in pending_payload:
        raise AppError(401, "registration_incomplete", "registration incomplete")

    raise AppError(401, "not_authenticated", "not authenticated")


@router.patch("/me", response_model=CurrentUserResponse)
async def update_me(
    payload: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    users_repo: SheetRepository = Depends(get_users_repository),
    bot_client: DiscordBotClient = Depends(get_bot_client),
    settings: AuthSettings = Depends(get_auth_settings),
) -> CurrentUserResponse:
    """自分の氏名・学年のみを更新する。role/is_active/locale はここでは変更できない
    (役職はDiscordロールから自動算出、有効/無効は管理者操作のため、CLAUDE.md §6)。"""
    record = {"name": payload.name, "grade": payload.grade}
    await log_write(
        lambda: users_repo.update_by_key("discord_user_id", user.discord_user_id, record),
        bot_client=bot_client,
        channel_id=settings.discord_log_channel_id,
        actor_name=user.name,
        actor_id=user.discord_user_id,
        sheet_name="users",
        operation="update(profile)",
        record={"discord_user_id": user.discord_user_id, **record},
    )
    return CurrentUserResponse(
        discord_user_id=user.discord_user_id,
        name=payload.name,
        role=user.role,
        is_active=user.is_active,
        locale=user.locale,
        grade=payload.grade,
    )
