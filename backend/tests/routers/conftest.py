import pytest

from sheets.schemas import Role, User


@pytest.fixture
def active_user() -> User:
    return User(
        discord_user_id="u1",
        name="Alice",
        role=Role.MEMBER,
        is_active=True,
        locale="ja",
        registered_at="2026-01-01T00:00:00+09:00",
    )
