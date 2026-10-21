"""タスク担当の部門指定向け: task_assignees シートに label 列を追加する(CLAUDE.md §8)。

既にヘッダーに label が存在する場合は何もしない(冪等)。既存の列や行データには
一切触れず、ヘッダー行の末尾に 1 セル追記するだけ。

一回限りの手動実行用スクリプト。通常のアプリのリクエストパスからは呼ばない
(scripts/add_grade_column.py と同じ位置づけ。CLAUDE.md §1: シート構造は人間が作る)。

使い方:
    cd backend && source .venv/bin/activate && python scripts/add_task_assignee_label_column.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sheets.client import SheetsClient  # noqa: E402
from sheets.config import Settings  # noqa: E402

SHEET_NAME = "task_assignees"
COLUMN_NAME = "label"


def main() -> None:
    settings = Settings()
    client = SheetsClient.from_settings(settings)

    header = client.get_header_row(SHEET_NAME)
    print(f"current header: {header}")

    if COLUMN_NAME in header:
        print(f"'{COLUMN_NAME}' column already exists; nothing to do")
        return

    new_header = [*header, COLUMN_NAME]
    client.update_row(SHEET_NAME, 1, new_header)
    print(f"added '{COLUMN_NAME}' column: {new_header}")


if __name__ == "__main__":
    main()
