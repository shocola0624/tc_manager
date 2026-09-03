import pytest
from fastapi import HTTPException

from auth.dependencies import (
    find_raw_user,
    identity_from_cookie,
    require_role,
    resolve_current_user,
)
from auth.session import SESSION_COOKIE, SessionSigner
from sheets.schemas import Role, User


def test_identity_from_cookie_missing_raises_401():
    signer = SessionSigner("secret")

    with pytest.raises(HTTPException) as exc:
        identity_from_cookie(signer, None)

    assert exc.value.status_code == 401


def test_identity_from_cookie_invalid_raises_401():
    signer = SessionSigner("secret")

    with pytest.raises(HTTPException) as exc:
        identity_from_cookie(signer, "garbage")

    assert exc.value.status_code == 401


def test_identity_from_cookie_valid_returns_discord_user_id():
    signer = SessionSigner("secret")
    token = signer.sign(SESSION_COOKIE, {"discord_user_id": "u1"})

    assert identity_from_cookie(signer, token) == "u1"


def _add_user(users_repo, **overrides: str) -> None:
    row = {
        "discord_user_id": "u1",
        "name": "Alice",
        "role": "member",
        "is_active": "TRUE",
        "locale": "ja",
        "registered_at": "2026-01-01T00:00:00+09:00",
    }
    row.update(overrides)
    users_repo.append(row)


def test_resolve_current_user_returns_user_for_active_registered_row(users_repo):
    _add_user(users_repo)

    user = resolve_current_user("u1", users_repo)

    assert user.discord_user_id == "u1"
    assert user.role == Role.MEMBER


def test_resolve_current_user_raises_401_when_row_missing(users_repo):
    with pytest.raises(HTTPException) as exc:
        resolve_current_user("missing", users_repo)

    assert exc.value.status_code == 401


def test_resolve_current_user_raises_403_when_registration_incomplete(users_repo):
    _add_user(users_repo, registered_at="")

    with pytest.raises(HTTPException) as exc:
        resolve_current_user("u1", users_repo)

    assert exc.value.status_code == 403


def test_resolve_current_user_raises_403_when_inactive(users_repo):
    _add_user(users_repo, is_active="FALSE")

    with pytest.raises(HTTPException) as exc:
        resolve_current_user("u1", users_repo)

    assert exc.value.status_code == 403


def test_resolve_current_user_raises_403_on_invalid_row(users_repo):
    _add_user(users_repo, role="unknown_role")

    with pytest.raises(HTTPException) as exc:
        resolve_current_user("u1", users_repo)

    assert exc.value.status_code == 403


def test_find_raw_user_returns_none_when_absent(users_repo):
    assert find_raw_user(users_repo, "nope") is None


def test_find_raw_user_returns_row_when_present(users_repo):
    _add_user(users_repo)

    assert find_raw_user(users_repo, "u1")["name"] == "Alice"


def _user(role: Role) -> User:
    return User(
        discord_user_id="u1",
        name="Alice",
        role=role,
        is_active=True,
        locale="ja",
        registered_at="2026-01-01T00:00:00+09:00",
    )


async def test_require_role_allows_matching_role():
    dependency = require_role(Role.ADMIN, Role.OFFICER)

    user = await dependency(_user(Role.OFFICER))

    assert user.role == Role.OFFICER


async def test_require_role_rejects_other_roles():
    dependency = require_role(Role.ADMIN)

    with pytest.raises(HTTPException) as exc:
        await dependency(_user(Role.MEMBER))

    assert exc.value.status_code == 403
