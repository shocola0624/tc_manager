from __future__ import annotations

import secrets

from fastapi import Depends

from auth.config import AuthSettings
from auth.dependencies import get_auth_settings, get_bot_client, get_current_user, require_role
from auth.discord_client import DiscordBotClient, DiscordOAuthError
from discord_bot.announce import announce_activity
from discord_bot.confirm_announce import confirm_activity
from discord_bot.write_log import log_write
from envelope import InvalidRowOut, ListResponse
from errors import AppError
from repositories import (
    get_activities_current_window_repository,
    get_activities_repository,
    get_assignments_repository,
    get_budget_items_repository,
    get_items_repository,
    get_users_repository,
)
from sheets.parsing import parse_records
from sheets.repository import SheetRepository, ViewBackedRepository
from sheets.schemas import Activity, Role, User

from ._common import make_list_router
from .activities_schemas import ActivityCreateRequest, ActivityUpdateRequest

router = make_list_router(
    prefix="/api/activities",
    tags=["activities"],
    model=Activity,
    get_repository=get_activities_repository,
)

_can_manage_activities = require_role(Role.ADMIN, Role.OFFICER)


@router.get("/current-window", response_model=ListResponse[Activity])
async def list_current_window_activities(
    repo: ViewBackedRepository = Depends(get_activities_current_window_repository),
) -> ListResponse[Activity]:
    """直近(過去1週間〜今後)の活動のみを返す軽量版一覧(CLAUDE.md §4・§9)。ホーム画面など
    「次の活動」だけが必要な画面向け。過去の活動を広く見る操作(活動一覧の「過去」タブ等)
    には使わず、常に全件を返す GET /api/activities を使うこと。"""
    result = parse_records(repo.read_all(), Activity)
    return ListResponse(
        data=result.valid,
        invalid_rows=[InvalidRowOut.from_invalid_row(row) for row in result.invalid],
    )


def _generate_activity_id() -> str:
    return f"activity_{secrets.token_hex(6)}"


def _find_activity_or_404(activities_repo: SheetRepository, activity_id: str) -> Activity:
    result = parse_records(activities_repo.read_all(), Activity)
    for activity in result.valid:
        if activity.activity_id == activity_id:
            return activity
    raise AppError(404, "activity_not_found", "activity not found")


@router.post("", response_model=Activity, dependencies=[Depends(_can_manage_activities)])
async def create_activity(
    payload: ActivityCreateRequest,
    user: User = Depends(get_current_user),
    activities_repo: SheetRepository = Depends(get_activities_repository),
    bot_client: DiscordBotClient = Depends(get_bot_client),
    settings: AuthSettings = Depends(get_auth_settings),
) -> Activity:
    activity = Activity(
        activity_id=_generate_activity_id(),
        starts_at=payload.starts_at,
        duration_min=payload.duration_min,
        location=payload.location,
        title=payload.title,
        description=payload.description,
        target=payload.target,
        owner_id=payload.owner_id,
        tasks=payload.tasks,
        note=payload.note,
        announce_message_id=None,
        is_active=True,
    )
    record = {
        "activity_id": activity.activity_id,
        "starts_at": activity.starts_at.isoformat(),
        "duration_min": str(activity.duration_min),
        "location": activity.location,
        "title": activity.title,
        "description": activity.description,
        "target": activity.target,
        "owner_id": activity.owner_id,
        "tasks": activity.tasks,
        "note": activity.note,
        "announce_message_id": "",
        "is_active": "TRUE",
    }
    await log_write(
        lambda: activities_repo.append(record),
        bot_client=bot_client,
        channel_id=settings.discord_log_channel_id,
        actor_name=user.name,
        actor_id=user.discord_user_id,
        sheet_name="activities",
        operation="append",
        record=record,
    )
    return activity


@router.patch(
    "/{activity_id}", response_model=Activity, dependencies=[Depends(_can_manage_activities)]
)
async def update_activity(
    activity_id: str,
    payload: ActivityUpdateRequest,
    user: User = Depends(get_current_user),
    activities_repo: SheetRepository = Depends(get_activities_repository),
    bot_client: DiscordBotClient = Depends(get_bot_client),
    settings: AuthSettings = Depends(get_auth_settings),
) -> Activity:
    activity = _find_activity_or_404(activities_repo, activity_id)
    updates = payload.model_dump(exclude_unset=True)
    updated = activity.model_copy(update=updates)

    record = {
        "starts_at": updated.starts_at.isoformat(),
        "duration_min": str(updated.duration_min),
        "location": updated.location,
        "title": updated.title,
        "description": updated.description,
        "target": updated.target,
        "owner_id": updated.owner_id,
        "tasks": updated.tasks,
        "note": updated.note,
    }
    await log_write(
        lambda: activities_repo.update_by_key("activity_id", activity_id, record),
        bot_client=bot_client,
        channel_id=settings.discord_log_channel_id,
        actor_name=user.name,
        actor_id=user.discord_user_id,
        sheet_name="activities",
        operation="update",
        record={"activity_id": activity_id, **record},
    )
    return updated


@router.delete(
    "/{activity_id}", response_model=Activity, dependencies=[Depends(_can_manage_activities)]
)
async def delete_activity(
    activity_id: str,
    user: User = Depends(get_current_user),
    activities_repo: SheetRepository = Depends(get_activities_repository),
    bot_client: DiscordBotClient = Depends(get_bot_client),
    settings: AuthSettings = Depends(get_auth_settings),
) -> Activity:
    activity = _find_activity_or_404(activities_repo, activity_id)
    await log_write(
        lambda: activities_repo.update_by_key("activity_id", activity_id, {"is_active": "FALSE"}),
        bot_client=bot_client,
        channel_id=settings.discord_log_channel_id,
        actor_name=user.name,
        actor_id=user.discord_user_id,
        sheet_name="activities",
        operation="update(soft delete)",
        record={"activity_id": activity_id, "is_active": "FALSE"},
    )
    return activity.model_copy(update={"is_active": False})


@router.post(
    "/{activity_id}/announce", response_model=Activity, dependencies=[Depends(_can_manage_activities)]
)
async def announce(
    activity_id: str,
    user: User = Depends(get_current_user),
    activities_repo: SheetRepository = Depends(get_activities_repository),
    bot_client: DiscordBotClient = Depends(get_bot_client),
    settings: AuthSettings = Depends(get_auth_settings),
) -> Activity:
    """Discord チャンネルへアナウンスを投稿し、出欠ボタンを付与する(CLAUDE.md §6)。

    何度でも呼び出せる(再投稿するたびに announce_message_id は最新のメッセージで
    上書きされる。過去に投稿済みのメッセージのボタンも custom_id に activity_id を
    埋め込んでいるため引き続き機能する)。
    """
    activity = _find_activity_or_404(activities_repo, activity_id)
    try:
        await announce_activity(
            activity,
            bot_client=bot_client,
            activities_repo=activities_repo,
            channel_id=settings.discord_announce_channel_id,
            log_channel_id=settings.discord_log_channel_id,
            actor_name=user.name,
            actor_id=user.discord_user_id,
        )
    except DiscordOAuthError as exc:
        raise AppError(502, "discord_announce_failed", str(exc)) from exc
    return _find_activity_or_404(activities_repo, activity_id)


@router.post(
    "/{activity_id}/confirm", response_model=Activity, dependencies=[Depends(_can_manage_activities)]
)
async def confirm(
    activity_id: str,
    activities_repo: SheetRepository = Depends(get_activities_repository),
    users_repo: SheetRepository = Depends(get_users_repository),
    assignments_repo: SheetRepository = Depends(get_assignments_repository),
    items_repo: SheetRepository = Depends(get_items_repository),
    budget_items_repo: SheetRepository = Depends(get_budget_items_repository),
    bot_client: DiscordBotClient = Depends(get_bot_client),
    settings: AuthSettings = Depends(get_auth_settings),
) -> Activity:
    """確定情報(日時・場所・器具・予算・タスク等)をまとめて別チャンネルへ投稿する。
    出欠ボタン付きのRSVP告知(announce)とは別物で、何度でも押し直せる。
    """
    activity = _find_activity_or_404(activities_repo, activity_id)
    try:
        await confirm_activity(
            activity,
            bot_client=bot_client,
            users_repo=users_repo,
            assignments_repo=assignments_repo,
            items_repo=items_repo,
            budget_items_repo=budget_items_repo,
            channel_id=settings.discord_confirm_announce_channel_id,
        )
    except DiscordOAuthError as exc:
        raise AppError(502, "discord_announce_failed", str(exc)) from exc
    return activity
