from attendance_service import set_attendance
from sheets.repository import SheetRepository
from sheets.schemas import AttendanceStatus

ATTENDANCE_HEADER = ["activity_id", "discord_user_id", "status", "updated_at"]


class FakeBotClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def create_message(self, channel_id: str, payload: dict) -> dict:
        self.calls.append((channel_id, payload))
        return {"id": "msg-1"}


def _repo(fake_client_factory, rows=None) -> SheetRepository:
    client = fake_client_factory("attendance", header=ATTENDANCE_HEADER, rows=rows or [])
    return SheetRepository(client, "attendance")


async def test_set_attendance_appends_when_no_existing_row(fake_client_factory):
    repo = _repo(fake_client_factory)
    bot_client = FakeBotClient()

    result = await set_attendance(
        repo,
        "activity_1",
        "u1",
        AttendanceStatus.ATTENDING,
        bot_client=bot_client,
        log_channel_id="log-channel-1",
        actor_name="Alice",
    )

    assert result.status == AttendanceStatus.ATTENDING
    stored = repo.read_all()
    assert len(stored) == 1
    assert stored[0]["activity_id"] == "activity_1"
    assert stored[0]["discord_user_id"] == "u1"
    assert stored[0]["status"] == "attending"
    assert stored[0]["updated_at"]

    assert len(bot_client.calls) == 1
    channel_id, payload = bot_client.calls[0]
    assert channel_id == "log-channel-1"
    assert "Alice" in payload["embeds"][0]["description"]


async def test_set_attendance_updates_existing_row_in_place(fake_client_factory):
    repo = _repo(
        fake_client_factory,
        rows=[["activity_1", "u1", "undecided", "2026-01-01T00:00:00+09:00"]],
    )
    bot_client = FakeBotClient()

    await set_attendance(
        repo,
        "activity_1",
        "u1",
        AttendanceStatus.ABSENT,
        bot_client=bot_client,
        log_channel_id="log-channel-1",
        actor_name="Alice",
    )

    stored = repo.read_all()
    assert len(stored) == 1
    assert stored[0]["status"] == "absent"


async def test_set_attendance_is_keyed_by_activity_and_user(fake_client_factory):
    repo = _repo(
        fake_client_factory,
        rows=[["activity_1", "u1", "attending", "2026-01-01T00:00:00+09:00"]],
    )
    bot_client = FakeBotClient()

    await set_attendance(
        repo,
        "activity_1",
        "u2",
        AttendanceStatus.ATTENDING,
        bot_client=bot_client,
        log_channel_id="log-channel-1",
        actor_name="Bob",
    )

    stored = repo.read_all()
    assert len(stored) == 2


async def test_set_attendance_posts_failure_log_and_reraises_when_write_fails(fake_client_factory):
    repo = _repo(fake_client_factory)

    def _boom(*args, **kwargs):
        raise RuntimeError("sheets unavailable")

    repo.upsert_by_keys = _boom  # type: ignore[method-assign]
    bot_client = FakeBotClient()

    try:
        await set_attendance(
            repo,
            "activity_1",
            "u1",
            AttendanceStatus.ATTENDING,
            bot_client=bot_client,
            log_channel_id="log-channel-1",
            actor_name="Alice",
        )
        raise AssertionError("expected RuntimeError to propagate")
    except RuntimeError:
        pass

    assert len(bot_client.calls) == 1
    embed = bot_client.calls[0][1]["embeds"][0]
    assert "失敗" in embed["title"]
    assert "sheets unavailable" in embed["fields"][1]["value"]
