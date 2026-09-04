"""フェーズ1: 読み取り専用ビューシートの一括セットアップ(CLAUDE.md §4・§9)。

同一スプレッドシート内に FILTER 数式で絞り込んだ以下の3シートを追加する。既に存在する
場合はヘッダー・数式だけを上書きする(冪等)。

- view_activities_current: 直近(過去1週間〜今後)の活動のみ
- view_attendance_current: 上記の活動に紐づく出欠のみ
- view_assignments_current: 上記の活動に紐づく割り当てログ(追記専用ログの生データ)のみ

一回限りの手動実行用スクリプト。通常のアプリのリクエストパスからは呼ばない
(sheets/client.py の create_sheet/set_formula と同じ位置づけ)。

使い方:
    cd backend && source .venv/bin/activate && python scripts/setup_read_views.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sheets.client import SheetsClient  # noqa: E402
from sheets.config import Settings  # noqa: E402

VIEW_ACTIVITIES = "view_activities_current"
VIEW_ATTENDANCE = "view_attendance_current"
VIEW_ASSIGNMENTS = "view_assignments_current"

# 実シートの列範囲(ヘッダー行を除く)。列が増えた場合はここを合わせて広げること。
_ACTIVITIES_HEADER_RANGE = "A1:M1"
_ATTENDANCE_HEADER_RANGE = "A1:D1"
_ASSIGNMENTS_HEADER_RANGE = "A1:G1"


def _ensure_sheet_exists(client: SheetsClient, existing_titles: set[str], sheet_name: str) -> None:
    if sheet_name in existing_titles:
        print(f"  {sheet_name}: already exists, updating formulas")
        return
    print(f"  {sheet_name}: creating")
    client.create_sheet(sheet_name)


def main() -> None:
    settings = Settings()
    client = SheetsClient.from_settings(settings)

    print("checking existing sheets...")
    existing_titles = set(client.list_sheet_titles())
    for name in (VIEW_ACTIVITIES, VIEW_ATTENDANCE, VIEW_ASSIGNMENTS):
        _ensure_sheet_exists(client, existing_titles, name)

    print("writing header formulas (mirror source sheet header, so column renames/additions propagate)...")
    # 単純な範囲参照(=A1:M1)は1セルに書いても自動スピルしない(スピルするのは
    # FILTER/SORT等の配列関数のみ)。ARRAYFORMULA で明示的に配列として評価させる。
    client.set_formula(VIEW_ACTIVITIES, "A1", f"=ARRAYFORMULA(activities!{_ACTIVITIES_HEADER_RANGE})")
    client.set_formula(VIEW_ATTENDANCE, "A1", f"=ARRAYFORMULA(attendance!{_ATTENDANCE_HEADER_RANGE})")
    client.set_formula(VIEW_ASSIGNMENTS, "A1", f"=ARRAYFORMULA(assignments!{_ASSIGNMENTS_HEADER_RANGE})")

    print("writing FILTER formulas...")
    # 絞り込みは時間窓のみで固定する(CLAUDE.md §9: 特定 activity_id をセルに書いてから
    # 読むような制御セル方式にしない)。ISO8601 の先頭10文字(yyyy-mm-dd)同士の文字列比較で
    # 日付だけを比べ、時刻・タイムゾーン部分の曖昧さを避ける。
    client.set_formula(
        VIEW_ACTIVITIES,
        "A2",
        '=FILTER(activities!A2:M, LEFT(activities!B2:B,10)>=TEXT(TODAY()-7,"yyyy-mm-dd"))',
    )
    # attendance/assignments は「現在の活動一覧に載っている activity_id か」で絞り込む
    # (ログ自体のタイムスタンプではなく、紐づく活動が現在窓に入っているかで判定する)。
    client.set_formula(
        VIEW_ATTENDANCE,
        "A2",
        f"=FILTER(attendance!A2:D, ISNUMBER(MATCH(attendance!A2:A, {VIEW_ACTIVITIES}!A2:A, 0)))",
    )
    client.set_formula(
        VIEW_ASSIGNMENTS,
        "A2",
        f"=FILTER(assignments!A2:G, ISNUMBER(MATCH(assignments!B2:B, {VIEW_ACTIVITIES}!A2:A, 0)))",
    )

    print("done. verifying by reading back the views:")
    for name in (VIEW_ACTIVITIES, VIEW_ATTENDANCE, VIEW_ASSIGNMENTS):
        rows = client.get_all_values(name)
        print(f"  {name}: header={rows[0] if rows else '(empty)'}, data_rows={max(len(rows) - 1, 0)}")


if __name__ == "__main__":
    main()
