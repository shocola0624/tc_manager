from __future__ import annotations

from auth.discord_client import DiscordBotClient
from discord_bot.write_log import log_write
from sheets.repository import SheetRepository
from sheets.schemas import Attendance, AttendanceStatus
from timeutil import now_iso8601


async def set_attendance(
    attendance_repo: SheetRepository,
    activity_id: str,
    discord_user_id: str,
    status: AttendanceStatus,
    *,
    bot_client: DiscordBotClient,
    log_channel_id: str,
    actor_name: str,
) -> Attendance:
    """Discord のボタン応答・Web からの自己申告の両方から呼ばれる出欠の upsert。

    (activity_id, discord_user_id) で一意(CLAUDE.md §4)。既存行があれば更新、
    なければ追加する SheetRepository.upsert_by_keys にそのまま委譲する。
    書き込みの成功・失敗は Discord のログチャンネルへ通知する(呼び出し元2箇所で
    ロジックを共有するため、ここに集約する)。
    """
    updated_at = now_iso8601()
    record = {
        "activity_id": activity_id,
        "discord_user_id": discord_user_id,
        "status": status.value,
        "updated_at": updated_at,
    }
    await log_write(
        lambda: attendance_repo.upsert_by_keys(
            ["activity_id", "discord_user_id"],
            [activity_id, discord_user_id],
            {"status": status.value, "updated_at": updated_at},
        ),
        bot_client=bot_client,
        channel_id=log_channel_id,
        actor_name=actor_name,
        actor_id=discord_user_id,
        sheet_name="attendance",
        operation="upsert",
        record=record,
    )
    return Attendance(
        activity_id=activity_id,
        discord_user_id=discord_user_id,
        status=status,
        updated_at=updated_at,
    )
