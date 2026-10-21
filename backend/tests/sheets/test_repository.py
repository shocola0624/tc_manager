import pytest

from sheets.exceptions import DuplicateKeyError, RowNotFoundError
from sheets.repository import AppendOnlyRepository, SheetRepository


def test_read_all_maps_by_column_name_not_position(fake_client_factory):
    client = fake_client_factory(
        "users",
        header=["role", "discord_user_id", "name"],
        rows=[["member", "u1", "Alice"]],
    )
    repo = SheetRepository(client, "users")

    assert repo.read_all() == [{"role": "member", "discord_user_id": "u1", "name": "Alice"}]


def test_read_all_returns_empty_list_for_header_only_sheet(fake_client_factory):
    client = fake_client_factory("users", header=["discord_user_id", "name"], rows=[])
    repo = SheetRepository(client, "users")

    assert repo.read_all() == []


def test_append_writes_columns_in_sheet_order(fake_client_factory):
    client = fake_client_factory("users", header=["role", "discord_user_id", "name"], rows=[])
    repo = SheetRepository(client, "users")

    repo.append({"discord_user_id": "u1", "name": "Alice", "role": "member"})

    assert client._rows == [["member", "u1", "Alice"]]


def test_update_by_key_merges_into_existing_row_without_clobbering_other_columns(fake_client_factory):
    client = fake_client_factory(
        "users",
        header=["discord_user_id", "name", "role"],
        rows=[["u1", "Alice", "member"]],
    )
    repo = SheetRepository(client, "users")

    repo.update_by_key("discord_user_id", "u1", {"role": "officer"})

    assert client._rows == [["u1", "Alice", "officer"]]


def test_update_by_key_raises_when_not_found(fake_client_factory):
    client = fake_client_factory("users", header=["discord_user_id", "name"], rows=[])
    repo = SheetRepository(client, "users")

    with pytest.raises(RowNotFoundError):
        repo.update_by_key("discord_user_id", "missing", {"name": "x"})


def test_update_by_key_raises_on_duplicate_key(fake_client_factory):
    client = fake_client_factory(
        "users",
        header=["discord_user_id", "name"],
        rows=[["u1", "Alice"], ["u1", "Bob"]],
    )
    repo = SheetRepository(client, "users")

    with pytest.raises(DuplicateKeyError):
        repo.update_by_key("discord_user_id", "u1", {"name": "Carol"})


def test_update_by_keys_supports_composite_key(fake_client_factory):
    client = fake_client_factory(
        "attendance",
        header=["activity_id", "discord_user_id", "status"],
        rows=[["a1", "u1", "undecided"], ["a1", "u2", "undecided"]],
    )
    repo = SheetRepository(client, "attendance")

    repo.update_by_keys(["activity_id", "discord_user_id"], ["a1", "u2"], {"status": "attending"})

    assert client._rows == [["a1", "u1", "undecided"], ["a1", "u2", "attending"]]


def test_upsert_by_key_appends_when_missing(fake_client_factory):
    client = fake_client_factory("users", header=["discord_user_id", "name"], rows=[])
    repo = SheetRepository(client, "users")

    repo.upsert_by_key("discord_user_id", "u1", {"name": "Alice"})

    assert client._rows == [["u1", "Alice"]]


def test_upsert_by_key_updates_when_present(fake_client_factory):
    client = fake_client_factory("users", header=["discord_user_id", "name"], rows=[["u1", "Alice"]])
    repo = SheetRepository(client, "users")

    repo.upsert_by_key("discord_user_id", "u1", {"name": "Alice B"})

    assert client._rows == [["u1", "Alice B"]]


def test_replace_all_clears_then_rewrites_every_row(fake_client_factory):
    client = fake_client_factory(
        "task_assignees",
        header=["task_id", "member_id"],
        rows=[["t1", "u1"], ["t2", "u2"]],
    )
    repo = SheetRepository(client, "task_assignees")

    repo.replace_all([{"task_id": "t1", "member_id": "u3"}, {"task_id": "t3", "member_id": "u4"}])

    assert client._rows == [["t1", "u3"], ["t3", "u4"]]


def test_append_only_repository_forbids_update_and_upsert(fake_client_factory):
    client = fake_client_factory("assignments", header=["activity_id"], rows=[])
    repo = AppendOnlyRepository(client, "assignments")

    with pytest.raises(NotImplementedError):
        repo.update_by_key("activity_id", "a1", {})
    with pytest.raises(NotImplementedError):
        repo.upsert_by_key("activity_id", "a1", {})
    with pytest.raises(NotImplementedError):
        repo.replace_all([])


def test_append_only_repository_still_allows_read_and_append(fake_client_factory):
    client = fake_client_factory("assignments", header=["activity_id"], rows=[])
    repo = AppendOnlyRepository(client, "assignments")

    repo.append({"activity_id": "a1"})

    assert repo.read_all() == [{"activity_id": "a1"}]
