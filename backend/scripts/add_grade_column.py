"""プロフィール画面向け: users シートに grade(学年)列を追加する(CLAUDE.md §8)。

既にヘッダーに grade が存在する場合は何もしない(冪等)。既存の列や行データには
一切触れず、ヘッダー行の末尾に 1 セル追記するだけ。

一回限りの手動実行用スクリプト。通常のアプリのリクエストパスからは呼ばない
(sheets/client.py の create_sheet/set_formula と同じ位置づけ。CLAUDE.md §1: シート構造は
人間が作る)。

使い方:
    cd backend && source .venv/bin/activate && python scripts/add_grade_column.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sheets.client import SheetsClient  # noqa: E402
from sheets.config import Settings  # noqa: E402

SHEET_NAME = "users"
COLUMN_NAME = "grade"


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
