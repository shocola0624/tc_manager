from __future__ import annotations

import secrets

from fastapi import Depends

from auth.dependencies import get_current_user
from errors import AppError
from repositories import get_items_repository
from sheets.parsing import parse_records
from sheets.repository import SheetRepository
from sheets.schemas import Item, User

from ._common import make_list_router
from .items_permissions import can_edit_item, can_set_owner
from .items_schemas import ItemCreateRequest, ItemUpdateRequest

router = make_list_router(
    prefix="/api/items", tags=["items"], model=Item, get_repository=get_items_repository
)


def _generate_item_id() -> str:
    return f"item_{secrets.token_hex(6)}"


def _find_item_or_404(items_repo: SheetRepository, item_id: str) -> Item:
    result = parse_records(items_repo.read_all(), Item)
    for item in result.valid:
        if item.item_id == item_id:
            return item
    raise AppError(404, "item_not_found", "item not found")


@router.post("", response_model=Item)
async def create_item(
    payload: ItemCreateRequest,
    user: User = Depends(get_current_user),
    items_repo: SheetRepository = Depends(get_items_repository),
) -> Item:
    owner_id = payload.owner_id or user.discord_user_id
    if not can_set_owner(owner_id, user):
        raise AppError(403, "owner_not_allowed", "cannot set this owner_id")

    item = Item(
        item_id=_generate_item_id(),
        owner_id=owner_id,
        name=payload.name,
        maker=payload.maker,
        category=payload.category,
        storage=payload.storage,
        note=payload.note,
        is_active=True,
    )
    items_repo.append(
        {
            "item_id": item.item_id,
            "owner_id": item.owner_id,
            "name": item.name,
            "maker": item.maker,
            "category": item.category.value,
            "storage": item.storage.value,
            "note": item.note,
            "is_active": "TRUE",
        }
    )
    return item


@router.patch("/{item_id}", response_model=Item)
async def update_item(
    item_id: str,
    payload: ItemUpdateRequest,
    user: User = Depends(get_current_user),
    items_repo: SheetRepository = Depends(get_items_repository),
) -> Item:
    item = _find_item_or_404(items_repo, item_id)
    if not can_edit_item(item, user):
        raise AppError(403, "forbidden_item_edit", "cannot edit this item")

    updates = payload.model_dump(exclude_unset=True)
    updated = item.model_copy(update=updates)

    items_repo.update_by_key(
        "item_id",
        item_id,
        {
            "name": updated.name,
            "maker": updated.maker,
            "category": updated.category.value,
            "storage": updated.storage.value,
            "note": updated.note,
        },
    )
    return updated


@router.delete("/{item_id}", response_model=Item)
async def delete_item(
    item_id: str,
    user: User = Depends(get_current_user),
    items_repo: SheetRepository = Depends(get_items_repository),
) -> Item:
    item = _find_item_or_404(items_repo, item_id)
    if not can_edit_item(item, user):
        raise AppError(403, "forbidden_item_edit", "cannot edit this item")

    items_repo.update_by_key("item_id", item_id, {"is_active": "FALSE"})
    return item.model_copy(update={"is_active": False})
