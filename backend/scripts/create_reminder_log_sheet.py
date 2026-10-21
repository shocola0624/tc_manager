"""リマインド配信(workers/)向け: reminder_log シートの新規作成(CLAUDE.md §8)。

reminder_log は Workers の Cron が送信済みリマインドを追記するログ(追記専用)。
シートが存在しないと Cron が毎回失敗するため、デプロイ前に一度だけ実行する。

既に存在する場合は何もしない(冪等)。既存シートのヘッダーやデータには触れない
(create_tasks_sheets.py と違い、既存シートのヘッダーを上書きしない)。

一回限りの手動実行用スクリプト。通常のアプリのリクエストパスからは呼ばない
(CLAUDE.md §1: シート構造は人間が作る)。

使い方:
    cd backend && uv run python scripts/create_reminder_log_sheet.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sheets.client import SheetsClient  # noqa: E402
from sheets.config import Settings  # noqa: E402

SHEET_NAME = "reminder_log"
# workers/src/index.ts の REMINDER_LOG_HEADER と一致させる
HEADER = ["task_id", "offset_key", "channel", "member_id", "sent_at"]


def main() -> None:
    settings = Settings()
    client = SheetsClient.from_settings(settings)

    if SHEET_NAME in client.list_sheet_titles():
        print(f"'{SHEET_NAME}' already exists; nothing to do (header={client.get_header_row(SHEET_NAME)})")
        return

    client.create_sheet(SHEET_NAME)
    client.update_row(SHEET_NAME, 1, HEADER)
    print(f"created '{SHEET_NAME}': header={client.get_header_row(SHEET_NAME)}")


if __name__ == "__main__":
    main()
