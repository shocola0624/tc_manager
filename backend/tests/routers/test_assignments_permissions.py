from routers.assignments_permissions import can_assign
from sheets.schemas import Role, User


def _user(**overrides) -> User:
    defaults = dict(
        discord_user_id="u1",
        name="Alice",
        role=Role.MEMBER,
        is_active=True,
        locale="ja",
        registered_at="2026-01-01T00:00:00+09:00",
    )
    defaults.update(overrides)
    return User(**defaults)


def test_unassigned_slot_is_always_allowed():
    assert can_assign(None, is_system_default=False, actor=_user()) is True


def test_assigning_yourself_is_always_allowed():
    actor = _user(discord_user_id="u1")
    assert can_assign("u1", is_system_default=False, actor=actor) is True


def test_system_default_assignee_is_allowed_for_anyone():
    actor = _user(discord_user_id="u1", role=Role.MEMBER)
    assert can_assign("owner1", is_system_default=True, actor=actor) is True


def test_member_cannot_assign_someone_else():
    actor = _user(discord_user_id="u1", role=Role.MEMBER)
    assert can_assign("u2", is_system_default=False, actor=actor) is False


def test_officer_can_assign_someone_else():
    actor = _user(discord_user_id="u1", role=Role.OFFICER)
    assert can_assign("u2", is_system_default=False, actor=actor) is True


def test_admin_can_assign_someone_else():
    actor = _user(discord_user_id="u1", role=Role.ADMIN)
    assert can_assign("u2", is_system_default=False, actor=actor) is True
