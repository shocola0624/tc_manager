from typing import Generic, TypeVar

from pydantic import BaseModel

from sheets.parsing import InvalidRow

T = TypeVar("T", bound=BaseModel)


class InvalidRowOut(BaseModel):
    row_number: int
    raw: dict[str, str]
    reason: str

    @classmethod
    def from_invalid_row(cls, row: InvalidRow) -> "InvalidRowOut":
        return cls(row_number=row.row_number, raw=row.raw, reason=row.reason)


class ListResponse(BaseModel, Generic[T]):
    data: list[T]
    invalid_rows: list[InvalidRowOut] = []
