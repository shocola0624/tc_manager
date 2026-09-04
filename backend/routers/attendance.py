from fastapi import Depends

from attendance_service import set_attendance
from auth.config import AuthSettings
from auth.dependencies import get_auth_settings, get_bot_client, get_current_user
from auth.discord_client import DiscordBotClient
from discord_bot.notifications import notify_absent_user_if_still_assigned
from repositories import (
    get_activities_repository,
    get_assignments_repository,
    get_attendance_repository,
    get_items_repository,
)
from sheets.repository import SheetRepository
from sheets.schemas import Attendance, AttendanceStatus, User

from ._common import make_list_router
from .attendance_schemas import AttendanceUpdateRequest

router = make_list_router(
    prefix="/api/attendance",
    tags=["attendance"],
    model=Attendance,
    get_repository=get_attendance_repository,
)


@router.put("/{activity_id}", response_model=Attendance)
async def set_my_attendance(
    activity_id: str,
    payload: AttendanceUpdateRequest,
    user: User = Depends(get_current_user),
    attendance_repo: SheetRepository = Depends(get_attendance_repository),
    activities_repo: SheetRepository = Depends(get_activities_repository),
    items_repo: SheetRepository = Depends(get_items_repository),
    assignments_repo: SheetRepository = Depends(get_assignments_repository),
    bot_client: DiscordBotClient = Depends(get_bot_client),
    settings: AuthSettings = Depends(get_auth_settings),
) -> Attendance:
    """自分自身の出欠のみ書き込める(CLAUDE.md §6: 出欠回答は is_active ユーザー全員)。

    Discord のボタン応答(discord_bot/router.py)と同じ attendance_service.set_attendance
    を使い、書き込みロジックを一箇所に集約する。
    """
    result = await set_attendance(
        attendance_repo,
        activity_id,
        user.discord_user_id,
        payload.status,
        bot_client=bot_client,
        log_channel_id=settings.discord_log_channel_id,
        actor_name=user.name,
    )

    if payload.status == AttendanceStatus.ABSENT:
        # 欠席に変えても持参担当のままの割り当てが残っていれば本人へDM(ベストエフォート)。
        await notify_absent_user_if_still_assigned(
            activity_id=activity_id,
            user=user,
            activities_repo=activities_repo,
            assignments_repo=assignments_repo,
            items_repo=items_repo,
            bot_client=bot_client,
        )

    return result
