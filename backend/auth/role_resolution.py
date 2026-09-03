from collections.abc import Sequence

from sheets.schemas import Role

from .config import AuthSettings


def resolve_role(role_ids: Sequence[str] | None, settings: AuthSettings) -> Role:
    """Discord のロール ID 一覧から admin/officer/member を決定する純粋関数。

    - role_ids が None(ギルド未所属)の場合は member
    - DISCORD_ADMIN_ROLE_ID を持っていれば admin(officer より優先)
    - DISCORD_OFFICER_ROLE_ID を持っていれば officer
    - どちらも該当しなければ member
    """
    if not role_ids:
        return Role.MEMBER

    if settings.discord_admin_role_id and settings.discord_admin_role_id in role_ids:
        return Role.ADMIN
    if settings.discord_officer_role_id and settings.discord_officer_role_id in role_ids:
        return Role.OFFICER
    return Role.MEMBER
