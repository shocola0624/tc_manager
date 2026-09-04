from __future__ import annotations

import secrets

from fastapi import Depends

from auth.config import AuthSettings
from auth.dependencies import get_auth_settings, get_bot_client, get_current_user, require_role
from auth.discord_client import DiscordBotClient
from discord_bot.write_log import log_write
from errors import AppError
from repositories import get_budget_items_repository
from sheets.parsing import parse_records
from sheets.repository import SheetRepository
from sheets.schemas import BudgetItem, Role, User

from ._common import make_list_router
from .budget_items_schemas import BudgetItemCreateRequest

# 活動の予算は「豆 1000円」のような自由記述ラベル+金額の複数行として budget_items シートに
# 持つ(CLAUDE.md §4)。合計額はクライアント側で activity_id ごとに集計する(結合ビューは
# フロントの既存方針=出欠集計・候補件数と同じくクライアント側で計算)。
router = make_list_router(
    prefix="/api/budget-items",
    tags=["budget-items"],
    model=BudgetItem,
    get_repository=get_budget_items_repository,
)

_can_manage_budget = require_role(Role.ADMIN, Role.OFFICER)


def _generate_budget_item_id() -> str:
    return f"budget_{secrets.token_hex(6)}"


def _find_budget_item_or_404(budget_items_repo: SheetRepository, budget_item_id: str) -> BudgetItem:
    result = parse_records(budget_items_repo.read_all(), BudgetItem)
    for item in result.valid:
        if item.budget_item_id == budget_item_id:
            return item
    raise AppError(404, "budget_item_not_found", "budget item not found")


@router.post("", response_model=BudgetItem, dependencies=[Depends(_can_manage_budget)])
async def create_budget_item(
    payload: BudgetItemCreateRequest,
    user: User = Depends(get_current_user),
    budget_items_repo: SheetRepository = Depends(get_budget_items_repository),
    bot_client: DiscordBotClient = Depends(get_bot_client),
    settings: AuthSettings = Depends(get_auth_settings),
) -> BudgetItem:
    item = BudgetItem(
        budget_item_id=_generate_budget_item_id(),
        activity_id=payload.activity_id,
        label=payload.label,
        amount_jpy=payload.amount_jpy,
        is_active=True,
    )
    record = {
        "budget_item_id": item.budget_item_id,
        "activity_id": item.activity_id,
        "label": item.label,
        "amount_jpy": str(item.amount_jpy),
        "is_active": "TRUE",
    }
    await log_write(
        lambda: budget_items_repo.append(record),
        bot_client=bot_client,
        channel_id=settings.discord_log_channel_id,
        actor_name=user.name,
        actor_id=user.discord_user_id,
        sheet_name="budget_items",
        operation="append",
        record=record,
    )
    return item


@router.delete(
    "/{budget_item_id}", response_model=BudgetItem, dependencies=[Depends(_can_manage_budget)]
)
async def delete_budget_item(
    budget_item_id: str,
    user: User = Depends(get_current_user),
    budget_items_repo: SheetRepository = Depends(get_budget_items_repository),
    bot_client: DiscordBotClient = Depends(get_bot_client),
    settings: AuthSettings = Depends(get_auth_settings),
) -> BudgetItem:
    item = _find_budget_item_or_404(budget_items_repo, budget_item_id)
    await log_write(
        lambda: budget_items_repo.update_by_key(
            "budget_item_id", budget_item_id, {"is_active": "FALSE"}
        ),
        bot_client=bot_client,
        channel_id=settings.discord_log_channel_id,
        actor_name=user.name,
        actor_id=user.discord_user_id,
        sheet_name="budget_items",
        operation="update(soft delete)",
        record={"budget_item_id": budget_item_id, "is_active": "FALSE"},
    )
    return item.model_copy(update={"is_active": False})
