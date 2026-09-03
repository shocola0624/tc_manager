from __future__ import annotations

from sheets.repository import SheetRepository
from sheets.schemas import Attendance, AttendanceStatus
from timeutil import now_iso8601


def set_attendance(
    attendance_repo: SheetRepository,
    activity_id: str,
    discord_user_id: str,
    status: AttendanceStatus,
) -> Attendance:
    """Discord のボタン応答・Web からの自己申告の両方から呼ばれる出欠の upsert。

    (activity_id, discord_user_id) で一意(CLAUDE.md §4)。既存行があれば更新、
    なければ追加する SheetRepository.upsert_by_keys にそのまま委譲する。
    """
    updated_at = now_iso8601()
    attendance_repo.upsert_by_keys(
        ["activity_id", "discord_user_id"],
        [activity_id, discord_user_id],
        {"status": status.value, "updated_at": updated_at},
    )
    return Attendance(
        activity_id=activity_id,
        discord_user_id=discord_user_id,
        status=status,
        updated_at=updated_at,
    )
