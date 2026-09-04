from __future__ import annotations

import json
import logging

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from attendance_service import set_attendance
from auth.config import AuthSettings
from auth.dependencies import find_raw_user
from auth.discord_client import DiscordBotClient
from sheets.repository import SheetRepository
from sheets.schemas import AttendanceStatus, User

from .components import parse_attendance_custom_id
from .followup import send_followup
from .locales import translate
from .notifications import notify_absent_user_if_still_assigned
from .signature import verify_discord_signature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/discord", tags=["discord"])

# Discord Interactions API (v10) の type 定数。
_INTERACTION_TYPE_PING = 1
_INTERACTION_TYPE_MESSAGE_COMPONENT = 3

_RESPONSE_TYPE_PONG = 1
_RESPONSE_TYPE_DEFERRED_UPDATE_MESSAGE = 6


def _extract_discord_user_id(interaction: dict) -> str | None:
    """ギルド内のボタン押下は member.user.id、DM 等は user.id に入る。"""
    member_user = ((interaction.get("member") or {}).get("user")) or {}
    if member_user.get("id"):
        return member_user["id"]
    return (interaction.get("user") or {}).get("id")


def _resolve_active_user(users_repo: SheetRepository, discord_user_id: str) -> User | None:
    raw_user = find_raw_user(users_repo, discord_user_id)
    if raw_user is None:
        return None
    try:
        user = User.model_validate(raw_user)
    except ValidationError:
        return None
    if user.registered_at is None or not user.is_active:
        return None
    return user


async def _handle_attendance_button(
    *,
    activity_id: str,
    status: AttendanceStatus,
    discord_user_id: str | None,
    interaction_token: str,
    application_id: str,
    http_client: httpx.AsyncClient,
    users_repo: SheetRepository,
    attendance_repo: SheetRepository,
    activities_repo: SheetRepository,
    items_repo: SheetRepository,
    assignments_repo: SheetRepository,
    bot_client: DiscordBotClient,
    frontend_base_url: str,
    log_channel_id: str,
) -> None:
    """deferred ack を返した後にバックグラウンドで実行する(CLAUDE.md §3: 3秒制限のため
    Sheets 書き込みは同期応答に含めない)。未登録・無効ユーザーはシートへ書き込まない
    (CLAUDE.md §6: 出欠回答は is_active ユーザーのみ)。"""
    try:
        if discord_user_id is None:
            await send_followup(
                http_client, application_id, interaction_token, content=translate("ja", "followup.error")
            )
            return

        user = _resolve_active_user(users_repo, discord_user_id)
        if user is None:
            await send_followup(
                http_client,
                application_id,
                interaction_token,
                content=translate("ja", "followup.registration_required", url=frontend_base_url),
            )
            return

        await set_attendance(
            attendance_repo,
            activity_id,
            discord_user_id,
            status,
            bot_client=bot_client,
            log_channel_id=log_channel_id,
            actor_name=user.name,
        )
        await send_followup(
            http_client,
            application_id,
            interaction_token,
            content=translate(user.locale, f"followup.recorded.{status.value}"),
        )

        if status == AttendanceStatus.ABSENT:
            # 欠席に変えても持参担当のままの割り当てが残っていれば本人へ別途DM(ベストエフォート)。
            await notify_absent_user_if_still_assigned(
                activity_id=activity_id,
                user=user,
                activities_repo=activities_repo,
                assignments_repo=assignments_repo,
                items_repo=items_repo,
                bot_client=bot_client,
            )
    except Exception:
        logger.exception("failed to process attendance button press")
        try:
            await send_followup(
                http_client, application_id, interaction_token, content=translate("ja", "followup.error")
            )
        except Exception:
            logger.exception("failed to send error follow-up")


@router.post("/interactions")
async def handle_interaction(
    request: Request,
    background_tasks: BackgroundTasks,
    body: bytes = Depends(verify_discord_signature),
) -> JSONResponse:
    interaction = json.loads(body)
    interaction_type = interaction.get("type")

    if interaction_type == _INTERACTION_TYPE_PING:
        return JSONResponse({"type": _RESPONSE_TYPE_PONG})

    if interaction_type == _INTERACTION_TYPE_MESSAGE_COMPONENT:
        custom_id = ((interaction.get("data") or {}).get("custom_id")) or ""
        press = parse_attendance_custom_id(custom_id)
        if press is not None:
            settings: AuthSettings = request.app.state.auth_settings
            background_tasks.add_task(
                _handle_attendance_button,
                activity_id=press.activity_id,
                status=press.status,
                discord_user_id=_extract_discord_user_id(interaction),
                interaction_token=interaction["token"],
                application_id=settings.discord_client_id,
                http_client=request.app.state.http_client,
                users_repo=request.app.state.users_repo,
                attendance_repo=request.app.state.attendance_repo,
                activities_repo=request.app.state.activities_repo,
                items_repo=request.app.state.items_repo,
                assignments_repo=request.app.state.assignments_repo,
                bot_client=request.app.state.bot_client,
                frontend_base_url=settings.frontend_base_url,
                log_channel_id=settings.discord_log_channel_id,
            )
        # 未知の custom_id(将来の他機能のボタン)は無視して deferred ack のみ返す。
        return JSONResponse({"type": _RESPONSE_TYPE_DEFERRED_UPDATE_MESSAGE})

    return JSONResponse({"error": "unsupported_interaction_type"}, status_code=400)
