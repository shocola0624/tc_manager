from sheets.schemas import Role, User


def can_assign(resolved_assignee_id: str | None, *, is_system_default: bool, actor: User) -> bool:
    """持参担当(assignee_id)を指名できるかの判定(CLAUDE.md §6)。

    - 未割り当て(None): 誰でもよい
    - 自分自身を担当にする: 誰でもよい
    - システムが自動決定した既定値(storage=owner かつ所有者が出席する場合の所有者自身):
      本人の同意を要する「指名」ではなく自然な既定なので誰でもよい
    - それ以外(明示的に他人を指名する): admin/officer のみ
    """
    if resolved_assignee_id is None:
        return True
    if resolved_assignee_id == actor.discord_user_id:
        return True
    if is_system_default:
        return True
    return actor.role in (Role.ADMIN, Role.OFFICER)
