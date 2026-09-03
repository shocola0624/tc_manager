from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import NoReturn

from .client import SheetsClient
from .columns import build_column_index, record_to_row, row_to_record
from .exceptions import DuplicateKeyError, RowNotFoundError


class SheetRepository:
    """列名ベースの読み書きを提供する汎用リポジトリ。列順には依存しない。

    ヘッダ行はアクセスのたびに取得する(常駐プロセスを持たないため、
    インスタンスをまたいだキャッシュは意味を持たない)。
    """

    def __init__(self, client: SheetsClient, sheet_name: str) -> None:
        self._client = client
        self._sheet_name = sheet_name

    def read_all(self) -> list[dict[str, str]]:
        rows = self._client.get_all_values(self._sheet_name)
        if not rows:
            return []
        column_index = build_column_index(rows[0])
        return [row_to_record(row, column_index) for row in rows[1:]]

    def append(self, record: Mapping[str, str]) -> None:
        column_index = build_column_index(self._client.get_header_row(self._sheet_name))
        self._client.append_row(self._sheet_name, record_to_row(record, column_index))

    def update_by_key(self, key_column: str, key_value: str, record: Mapping[str, str]) -> None:
        self.update_by_keys([key_column], [key_value], record)

    def update_by_keys(
        self,
        key_columns: Sequence[str],
        key_values: Sequence[str],
        record: Mapping[str, str],
    ) -> None:
        row_number, existing, column_index = self._find_row(key_columns, key_values)
        merged = {**existing, **record}
        self._client.update_row(self._sheet_name, row_number, record_to_row(merged, column_index))

    def upsert_by_key(self, key_column: str, key_value: str, record: Mapping[str, str]) -> None:
        self.upsert_by_keys([key_column], [key_value], record)

    def upsert_by_keys(
        self,
        key_columns: Sequence[str],
        key_values: Sequence[str],
        record: Mapping[str, str],
    ) -> None:
        try:
            self.update_by_keys(key_columns, key_values, record)
        except RowNotFoundError:
            full_record = {**dict(zip(key_columns, key_values, strict=True)), **record}
            self.append(full_record)

    def _find_row(
        self, key_columns: Sequence[str], key_values: Sequence[str]
    ) -> tuple[int, dict[str, str], dict[str, int]]:
        rows = self._client.get_all_values(self._sheet_name)
        if not rows:
            raise RowNotFoundError(
                f"{self._sheet_name}: key={dict(zip(key_columns, key_values, strict=True))} が見つかりません"
            )
        column_index = build_column_index(rows[0])

        matches: list[tuple[int, dict[str, str]]] = []
        for offset, row in enumerate(rows[1:]):
            record = row_to_record(row, column_index)
            if all(record.get(col) == val for col, val in zip(key_columns, key_values, strict=True)):
                row_number_1based = offset + 2  # +1 ヘッダ行, +1 1始まり
                matches.append((row_number_1based, record))

        if not matches:
            raise RowNotFoundError(
                f"{self._sheet_name}: key={dict(zip(key_columns, key_values, strict=True))} が見つかりません"
            )
        if len(matches) > 1:
            raise DuplicateKeyError(
                f"{self._sheet_name}: key={dict(zip(key_columns, key_values, strict=True))} が複数行に一致しました"
            )

        row_number, record = matches[0]
        return row_number, record, column_index


class AppendOnlyRepository(SheetRepository):
    """assignments シート専用。追記(append)のみを許可し、
    read-modify-write になる update/upsert を封じる(CLAUDE.md §4)。"""

    def update_by_key(self, *args: object, **kwargs: object) -> NoReturn:
        raise NotImplementedError("assignments シートは追記専用です")

    def update_by_keys(self, *args: object, **kwargs: object) -> NoReturn:
        raise NotImplementedError("assignments シートは追記専用です")

    def upsert_by_key(self, *args: object, **kwargs: object) -> NoReturn:
        raise NotImplementedError("assignments シートは追記専用です")

    def upsert_by_keys(self, *args: object, **kwargs: object) -> NoReturn:
        raise NotImplementedError("assignments シートは追記専用です")
