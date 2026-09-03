from __future__ import annotations

import pytest


class FakeSheetsClient:
    """SheetsClient のテスト用インメモリ実装。実際の Sheets API へは接続しない。"""

    def __init__(
        self,
        sheet_name: str,
        header: list[str],
        rows: list[list[str]] | None = None,
    ) -> None:
        self._sheet_name = sheet_name
        self._header = header
        self._rows: list[list[str]] = rows if rows is not None else []

    def get_all_values(self, sheet_name: str) -> list[list[str]]:
        assert sheet_name == self._sheet_name
        return [self._header, *self._rows]

    def get_header_row(self, sheet_name: str) -> list[str]:
        assert sheet_name == self._sheet_name
        return self._header

    def append_row(self, sheet_name: str, row: list[str]) -> None:
        assert sheet_name == self._sheet_name
        self._rows.append(row)

    def update_row(self, sheet_name: str, row_number_1based: int, row: list[str]) -> None:
        assert sheet_name == self._sheet_name
        index = row_number_1based - 2  # ヘッダ行を除いた 0 始まりインデックス
        assert 0 <= index < len(self._rows)
        self._rows[index] = row


@pytest.fixture
def fake_client_factory():
    return FakeSheetsClient
