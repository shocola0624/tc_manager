from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import NoReturn

from .client import SheetsClient
from .columns import build_column_index, record_to_row, row_to_record
from .exceptions import DuplicateKeyError, RowNotFoundError

logger = logging.getLogger(__name__)


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

    def replace_all(self, records: Sequence[Mapping[str, str]]) -> None:
        """全データ行をクリアしてから records を書き直す。

        task_assignees のような小さな join シート専用。1タスクの担当者編集のように
        低頻度・低競合な操作でのみ使うこと(update_by_key と違い対象行を特定しないため、
        書き込み中に他の行への同時編集があれば失われうる。assignments のような高頻度・
        高競合な表には絶対に使わない。CLAUDE.md §4 の read-modify-write 回避の例外として、
        低リスクと判断できる範囲に限定する)。
        """
        column_index = build_column_index(self._client.get_header_row(self._sheet_name))
        self._client.clear_values(self._sheet_name)
        rows = [record_to_row(record, column_index) for record in records]
        self._client.append_rows(self._sheet_name, rows)

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

    def replace_all(self, *args: object, **kwargs: object) -> NoReturn:
        raise NotImplementedError("assignments シートは追記専用です")


class ViewBackedRepository:
    """パフォーマンス最適化用の読み取り専用ビュー(CLAUDE.md §4・§9)から読み、
    失敗時は必ず元のシートへフォールバックする。

    ビューは Sheets 側の FILTER 数式が生成する派生データであり正ではない。壊れていても
    空でも存在しなくてもアプリは動作しなければならない、という §9 の原則をこのクラス1つに
    集約する。書き込みメソッドは意図的に持たない — 書き込みは常に元のシートの
    SheetRepository を直接使うこと。
    """

    def __init__(self, client: SheetsClient, *, source_sheet_name: str, view_sheet_name: str) -> None:
        self._source = SheetRepository(client, source_sheet_name)
        self._view = SheetRepository(client, view_sheet_name)
        self._view_sheet_name = view_sheet_name

    def read_all(self) -> list[dict[str, str]]:
        try:
            rows = self._view.read_all()
        except Exception:
            logger.warning("view sheet %s is unreadable; falling back to source sheet", self._view_sheet_name)
            return self._source.read_all()
        if not rows:
            # 空は「本当に該当データが0件」と「ビューが壊れている/未セットアップ」を
            # 区別できないため、安全側(フルスキャン)に倒す。性能改善は保証ではなく
            # あくまでキャッシュとしての最適化(§9)。
            return self._source.read_all()
        return rows
