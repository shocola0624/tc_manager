"""タスク管理機能向け: tasks / task_assignees シートの新規作成(CLAUDE.md §8)。

既に存在する場合はヘッダーだけ合わせて上書きする(冪等)。データ行には一切触れない。

一回限りの手動実行用スクリプト。通常のアプリのリクエストパスからは呼ばない
(sheets/client.py の create_sheet/set_formula、scripts/setup_read_views.py と同じ位置づけ。
CLAUDE.md §1: シート構造は人間が作る)。

使い方:
    cd backend && source .venv/bin/activate && python scripts/create_tasks_sheets.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sheets.client import SheetsClient  # noqa: E402
from sheets.config import Settings  # noqa: E402

TASKS_SHEET = "tasks"
TASK_ASSIGNEES_SHEET = "task_assignees"

TASKS_HEADER = [
    "task_id",
    "title",
    "description",
    "due_at",
    "status",
    "visibility",
    "related_activity_id",
    "reminder_offsets",
    "google_event_id",
    "is_active",
    "created_by",
    "created_at",
    "updated_at",
]
TASK_ASSIGNEES_HEADER = ["task_id", "member_id", "label"]


def _ensure_sheet(client: SheetsClient, existing_titles: set[str], sheet_name: str, header: list[str]) -> None:
    if sheet_name not in existing_titles:
        print(f"  {sheet_name}: creating")
        client.create_sheet(sheet_name)
    else:
        print(f"  {sheet_name}: already exists, updating header only")
    client.update_row(sheet_name, 1, header)


def main() -> None:
    settings = Settings()
    client = SheetsClient.from_settings(settings)

    print("checking existing sheets...")
    existing_titles = set(client.list_sheet_titles())

    _ensure_sheet(client, existing_titles, TASKS_SHEET, TASKS_HEADER)
    _ensure_sheet(client, existing_titles, TASK_ASSIGNEES_SHEET, TASK_ASSIGNEES_HEADER)

    print("done. verifying by reading back the headers:")
    for name in (TASKS_SHEET, TASK_ASSIGNEES_SHEET):
        print(f"  {name}: header={client.get_header_row(name)}")


if __name__ == "__main__":
    main()
