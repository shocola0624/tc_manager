from envelope import InvalidRowOut, ListResponse
from sheets.parsing import InvalidRow
from sheets.schemas import Role, User


def test_invalid_row_out_mirrors_invalid_row():
    row = InvalidRow(row_number=5, raw={"discord_user_id": ""}, reason="1 validation error")

    out = InvalidRowOut.from_invalid_row(row)

    assert out.row_number == 5
    assert out.raw == {"discord_user_id": ""}
    assert out.reason == "1 validation error"


def test_list_response_defaults_invalid_rows_to_empty_list():
    user = User(
        discord_user_id="u1",
        name="Alice",
        role=Role.MEMBER,
        is_active=True,
        locale="ja",
        registered_at="2026-01-01T00:00:00+09:00",
    )

    response = ListResponse[User](data=[user])

    assert response.data == [user]
    assert response.invalid_rows == []
