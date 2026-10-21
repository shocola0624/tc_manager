from sheets.schemas import Role, Task, User

# member < officer < admin という序列で、タスクの閲覧・作成・担当者指定・ステータス変更・
# 編集・削除のすべてを「自分のロールがタスクの visibility 以上か」という1つのチェックに
# 統一する(ユーザー要件: 権限によって層を分け、下の階層は上の階層のタスクを作成できない)。
_ROLE_RANK: dict[Role, int] = {Role.MEMBER: 0, Role.OFFICER: 1, Role.ADMIN: 2}


def role_rank(role: Role) -> int:
    return _ROLE_RANK[role]


def can_access_visibility(user: User, visibility: Role) -> bool:
    return role_rank(user.role) >= role_rank(visibility)


def can_view_task(user: User, task: Task) -> bool:
    return can_access_visibility(user, task.visibility)


def can_create_task(user: User, visibility: Role) -> bool:
    return can_access_visibility(user, visibility)


def can_assign(assignee: User, visibility: Role) -> bool:
    """担当者のロールが visibility 以上であること(閲覧できない人には割り当てられない)。"""
    return can_access_visibility(assignee, visibility)


def can_modify_task(user: User, task: Task) -> bool:
    """編集・削除・ステータス変更はすべて閲覧権限と同じ基準。"""
    return can_access_visibility(user, task.visibility)
