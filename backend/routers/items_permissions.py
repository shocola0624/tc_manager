from sheets.schemas import CIRCLE_OWNER_ID, Item, Role, User


def can_edit_item(item: Item, user: User) -> bool:
    """編集・削除の許可判定(CLAUDE.md §6 権限)。

    - 自分の持ち物: 本人
    - 他人の持ち物: admin のみ
    - サークル所有物: admin / officer
    """
    if item.owner_id == user.discord_user_id:
        return True
    if item.owner_id == CIRCLE_OWNER_ID:
        return user.role in (Role.ADMIN, Role.OFFICER)
    return user.role == Role.ADMIN


def can_set_owner(owner_id: str, user: User) -> bool:
    """登録時に指定できる owner_id かどうか。

    自分自身は誰でも指定できる。CIRCLE は admin/officer のみ。
    他人の discord_user_id を指定すること(代理登録)はフェーズ4のスコープ外として許可しない。
    """
    if owner_id == user.discord_user_id:
        return True
    if owner_id == CIRCLE_OWNER_ID:
        return user.role in (Role.ADMIN, Role.OFFICER)
    return False
