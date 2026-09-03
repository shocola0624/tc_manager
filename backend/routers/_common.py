from collections.abc import Callable
from typing import TypeVar

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth.dependencies import get_current_user
from envelope import InvalidRowOut, ListResponse
from sheets.parsing import parse_records
from sheets.repository import SheetRepository

T = TypeVar("T", bound=BaseModel)


def make_list_router(
    *,
    prefix: str,
    tags: list[str],
    model: type[T],
    get_repository: Callable[..., SheetRepository],
) -> APIRouter:
    """各リソース用ルーターの雛形。

    シート全体を読み、モデルで検証し、正常行と不正な行を ListResponse に詰めて返す
    一覧エンドポイントのみを持つ。書き込み・role 別の制限はフェーズ4以降で個別に追加する。
    """
    router = APIRouter(prefix=prefix, tags=tags, dependencies=[Depends(get_current_user)])

    @router.get("", response_model=ListResponse[model])
    async def list_records(repo: SheetRepository = Depends(get_repository)) -> ListResponse[model]:
        result = parse_records(repo.read_all(), model)
        return ListResponse(
            data=result.valid,
            invalid_rows=[InvalidRowOut.from_invalid_row(row) for row in result.invalid],
        )

    return router
