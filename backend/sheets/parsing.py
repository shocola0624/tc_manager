from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class InvalidRow:
    """人間の直接編集による不正値(未知のコード値、必須項目の空欄など)を持つ行。

    例外で落とさず、呼び出し元が UI 上で「不正な行」として提示できるようにする。
    """

    row_number: int  # シート上の絶対行番号(ヘッダ込み、1始まり)
    raw: dict[str, str]
    reason: str


@dataclass(frozen=True)
class ParseResult(Generic[T]):
    valid: list[T]
    invalid: list[InvalidRow]


def parse_records(
    records: Sequence[Mapping[str, str]],
    model: type[T],
    *,
    start_row_number: int = 2,
) -> ParseResult[T]:
    """SheetRepository.read_all() の結果を Pydantic モデルへ変換する。

    1件でも不正なら例外を投げず、その行だけ invalid に振り分けて処理を続ける。
    """
    valid: list[T] = []
    invalid: list[InvalidRow] = []

    for offset, record in enumerate(records):
        row_number = start_row_number + offset
        try:
            valid.append(model.model_validate(record))
        except ValidationError as exc:
            invalid.append(
                InvalidRow(row_number=row_number, raw=dict(record), reason=str(exc))
            )

    return ParseResult(valid=valid, invalid=invalid)
