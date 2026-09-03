import { CIRCLE_OWNER_ID } from "../api/types";
import type { CurrentUser, Item } from "../api/types";

/**
 * routers/items_permissions.py の can_edit_item と同じ規則(CLAUDE.md §6 権限)。
 * サーバー側が最終的な認可を行うが、UI 側でも同じ規則でボタンの出し分けをする。
 */
export function canEditItem(item: Item, user: CurrentUser): boolean {
  if (item.owner_id === user.discord_user_id) {
    return true;
  }
  if (item.owner_id === CIRCLE_OWNER_ID) {
    return user.role === "admin" || user.role === "officer";
  }
  return user.role === "admin";
}

/** 登録フォームで「サークル所有」を選べるかどうか(admin/officer のみ)。 */
export function canSetOwnerCircle(user: CurrentUser): boolean {
  return user.role === "admin" || user.role === "officer";
}
