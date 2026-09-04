from __future__ import annotations

import logging
from collections.abc import Callable, Mapping

from auth.discord_client import DiscordBotClient

logger = logging.getLogger(__name__)

_COLOR_SUCCESS = 0x57F287
_COLOR_FAILURE = 0xED4245
_MAX_FIELD_LEN = 1000


def _format_record(record: Mapping[str, str]) -> str:
    if not record:
        return "(なし)"
    text = "\n".join(f"{key}: {value}" for key, value in record.items())
    return text[:_MAX_FIELD_LEN]


async def _post_write_log(
    bot_client: DiscordBotClient,
    channel_id: str,
    *,
    actor_name: str,
    actor_id: str,
    sheet_name: str,
    operation: str,
    record: Mapping[str, str],
    error: Exception | None,
) -> None:
    """スプレッドシートへの書き込み結果を Discord のログチャンネルへ投稿する。

    運用者向けの内部診断ログであり、CLAUDE.md §7 が対象とする部員向け表示文言では
    ないため translate() は通さない(エラー内容自体が非翻訳の技術的文字列でもある)。
    投稿自体の失敗(チャンネル未設定・Bot権限不足等)は握りつぶし、呼び出し元の
    書き込み結果には影響させない(discord_bot/notifications.py と同じベストエフォート方針)。
    """
    if error is None:
        embed = {
            "color": _COLOR_SUCCESS,
            "title": f"✅ {sheet_name}.{operation}",
            "description": f"実行者: {actor_name} ({actor_id})",
            "fields": [{"name": "書き込み内容", "value": f"```\n{_format_record(record)}\n```"}],
        }
    else:
        embed = {
            "color": _COLOR_FAILURE,
            "title": f"❌ {sheet_name}.{operation} 失敗",
            "description": f"実行者: {actor_name} ({actor_id})",
            "fields": [
                {"name": "試みた書き込み内容", "value": f"```\n{_format_record(record)}\n```"},
                {"name": "エラー", "value": f"```\n{str(error)[:_MAX_FIELD_LEN]}\n```"},
            ],
        }
    try:
        await bot_client.create_message(channel_id, {"embeds": [embed]})
    except Exception:
        logger.exception("failed to post write log to discord")


async def log_write(
    write_fn: Callable[[], None],
    *,
    bot_client: DiscordBotClient,
    channel_id: str,
    actor_name: str,
    actor_id: str,
    sheet_name: str,
    operation: str,
    record: Mapping[str, str],
) -> None:
    """スプレッドシートへの書き込みを実行し、成功・失敗のいずれも Discord のログ
    チャンネルへ通知する(CLAUDE.md 追加要件: 全書き込みの実行者・内容・失敗理由をログする)。

    write_fn 内で例外が発生した場合は失敗ログを投稿したうえで例外を再送出する。
    呼び出し元の既存のエラーハンドリング(AppError への変換等)は変えない。
    """
    try:
        write_fn()
    except Exception as exc:
        await _post_write_log(
            bot_client,
            channel_id,
            actor_name=actor_name,
            actor_id=actor_id,
            sheet_name=sheet_name,
            operation=operation,
            record=record,
            error=exc,
        )
        raise
    else:
        await _post_write_log(
            bot_client,
            channel_id,
            actor_name=actor_name,
            actor_id=actor_id,
            sheet_name=sheet_name,
            operation=operation,
            record=record,
            error=None,
        )
