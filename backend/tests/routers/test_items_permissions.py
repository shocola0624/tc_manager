from routers.items_permissions import can_edit_item, can_set_owner
from sheets.schemas import CIRCLE_OWNER_ID, Category, Item, Role, Storage, User


def _item(**overrides) -> Item:
    defaults = dict(
        item_id="item_1",
        owner_id="u1",
        name="V60",
        maker="Hario",
        category=Category.DRIPPER,
        storage=Storage.OWNER,
        note="",
        is_active=True,
    )
    defaults.update(overrides)
    return Item(**defaults)


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


def test_owner_can_edit_own_item():
    assert can_edit_item(_item(owner_id="u1"), _user(discord_user_id="u1", role=Role.MEMBER))


def test_member_cannot_edit_others_item():
    assert not can_edit_item(_item(owner_id="u2"), _user(discord_user_id="u1", role=Role.MEMBER))


def test_admin_can_edit_others_item():
    assert can_edit_item(_item(owner_id="u2"), _user(discord_user_id="u1", role=Role.ADMIN))


def test_officer_cannot_edit_others_item():
    assert not can_edit_item(_item(owner_id="u2"), _user(discord_user_id="u1", role=Role.OFFICER))


def test_officer_can_edit_circle_item():
    assert can_edit_item(
        _item(owner_id=CIRCLE_OWNER_ID), _user(discord_user_id="u1", role=Role.OFFICER)
    )


def test_admin_can_edit_circle_item():
    assert can_edit_item(
        _item(owner_id=CIRCLE_OWNER_ID), _user(discord_user_id="u1", role=Role.ADMIN)
    )


def test_member_cannot_edit_circle_item():
    assert not can_edit_item(
        _item(owner_id=CIRCLE_OWNER_ID), _user(discord_user_id="u1", role=Role.MEMBER)
    )


def test_anyone_can_set_self_as_owner():
    assert can_set_owner("u1", _user(discord_user_id="u1", role=Role.MEMBER))


def test_member_cannot_set_circle_as_owner():
    assert not can_set_owner(CIRCLE_OWNER_ID, _user(discord_user_id="u1", role=Role.MEMBER))


def test_officer_can_set_circle_as_owner():
    assert can_set_owner(CIRCLE_OWNER_ID, _user(discord_user_id="u1", role=Role.OFFICER))


def test_admin_can_set_circle_as_owner():
    assert can_set_owner(CIRCLE_OWNER_ID, _user(discord_user_id="u1", role=Role.ADMIN))


def test_nobody_can_set_another_specific_user_as_owner():
    assert not can_set_owner("u2", _user(discord_user_id="u1", role=Role.ADMIN))
