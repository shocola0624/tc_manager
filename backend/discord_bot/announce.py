from __future__ import annotations

from datetime import datetime

from auth.discord_client import DiscordBotClient
from sheets.repository import SheetRepository
from sheets.schemas import Activity

from .components import build_attendance_action_row
from .locales import translate
from .write_log import log_write

# CLAUDE.md §7-5: 保存形式(ISO8601)と表示形式は分離する。フロントは Intl.DateTimeFormat を
# 使うが、バックエンドから Discord へ投稿する文言に JS の Intl 相当はないため、ja 固定の
# 簡易フォーマッタをここに閉じ込める(多言語化する際はこの関数だけを差し替えればよい)。
_WEEKDAY_JA = ["月", "火", "水", "木", "金", "土", "日"]


def _format_datetime_ja(dt: datetime) -> str:
    weekday = _WEEKDAY_JA[dt.weekday()]
    return f"{dt.month}/{dt.day}({weekday}) {dt.hour:02d}:{dt.minute:02d}〜"


def build_announcement_payload(activity: Activity) -> dict:
    if activity.location:
        body = translate(
            "ja",
            "announce.body",
            title=activity.title,
            datetime=_format_datetime_ja(activity.starts_at),
            location=activity.location,
        )
    else:
        body = translate(
            "ja",
            "announce.body.no_location",
            title=activity.title,
            datetime=_format_datetime_ja(activity.starts_at),
        )
    return {
        "content": body,
        "components": [build_attendance_action_row(activity.activity_id)],
    }


async def announce_activity(
    activity: Activity,
    *,
    bot_client: DiscordBotClient,
    activities_repo: SheetRepository,
    channel_id: str,
    log_channel_id: str,
    actor_name: str,
    actor_id: str,
) -> str:
    """チャンネルへアナウンスを投稿し、announce_message_id を保存して message_id を返す。"""
    payload = build_announcement_payload(activity)
    message = await bot_client.create_message(channel_id, payload)
    message_id = message["id"]
    await log_write(
        lambda: activities_repo.update_by_key(
            "activity_id", activity.activity_id, {"announce_message_id": message_id}
        ),
        bot_client=bot_client,
        channel_id=log_channel_id,
        actor_name=actor_name,
        actor_id=actor_id,
        sheet_name="activities",
        operation="update",
        record={"activity_id": activity.activity_id, "announce_message_id": message_id},
    )
    return message_id
