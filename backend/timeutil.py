from datetime import datetime, timedelta, timezone

# アプリは現時点で日本語のみ提供する(CLAUDE.md §7)。日時カラムは ISO 8601 + タイムゾーンで
# 格納する規約(CLAUDE.md §4)のため、書き込み時刻はすべて JST で統一する。
JST = timezone(timedelta(hours=9))


def now_iso8601() -> str:
    return datetime.now(JST).isoformat()
