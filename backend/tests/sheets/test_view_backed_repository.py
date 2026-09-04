from sheets.repository import ViewBackedRepository


class MultiSheetFakeClient:
    """複数シート名を扱えるテスト用フェイク。ViewBackedRepository は同一クライアントに
    対して source/view という2つの異なるシート名でアクセスするため、単一シート名前提の
    conftest.py の FakeSheetsClient では表現できない。"""

    def __init__(self, sheets: dict[str, tuple[list[str], list[list[str]]]]) -> None:
        self._sheets = sheets

    def get_all_values(self, sheet_name: str) -> list[list[str]]:
        if sheet_name not in self._sheets:
            raise RuntimeError(f"no such sheet: {sheet_name}")
        header, rows = self._sheets[sheet_name]
        return [header, *rows]

    def get_header_row(self, sheet_name: str) -> list[str]:
        if sheet_name not in self._sheets:
            raise RuntimeError(f"no such sheet: {sheet_name}")
        return self._sheets[sheet_name][0]

    def append_row(self, sheet_name: str, row: list[str]) -> None:
        raise NotImplementedError("ViewBackedRepository は書き込みを行わない")

    def update_row(self, sheet_name: str, row_number_1based: int, row: list[str]) -> None:
        raise NotImplementedError("ViewBackedRepository は書き込みを行わない")


def test_reads_from_view_when_it_has_data():
    client = MultiSheetFakeClient(
        {
            "activities": (["activity_id", "title"], [["a1", "old"], ["a2", "old"]]),
            "view_activities_current": (["activity_id", "title"], [["a2", "current"]]),
        }
    )
    repo = ViewBackedRepository(
        client, source_sheet_name="activities", view_sheet_name="view_activities_current"
    )

    assert repo.read_all() == [{"activity_id": "a2", "title": "current"}]


def test_falls_back_to_source_when_view_sheet_is_missing():
    client = MultiSheetFakeClient(
        {
            "activities": (["activity_id", "title"], [["a1", "old"]]),
            # view_activities_current は登録しない(取得失敗を模す)。
        }
    )
    repo = ViewBackedRepository(
        client, source_sheet_name="activities", view_sheet_name="view_activities_current"
    )

    assert repo.read_all() == [{"activity_id": "a1", "title": "old"}]


def test_falls_back_to_source_when_view_is_empty():
    """空データは「本当に0件」と「ビューが壊れている」を区別できないため安全側に倒す(CLAUDE.md §9)。"""
    client = MultiSheetFakeClient(
        {
            "activities": (["activity_id", "title"], [["a1", "old"]]),
            "view_activities_current": (["activity_id", "title"], []),
        }
    )
    repo = ViewBackedRepository(
        client, source_sheet_name="activities", view_sheet_name="view_activities_current"
    )

    assert repo.read_all() == [{"activity_id": "a1", "title": "old"}]
