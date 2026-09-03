from datetime import datetime, timedelta, timezone

from discord_bot.announce import announce_activity, build_announcement_payload
from sheets.repository import SheetRepository
from sheets.schemas import Activity

JST = timezone(timedelta(hours=9))

ACTIVITIES_HEADER = [
    "activity_id",
    "starts_at",
    "duration_min",
    "location",
    "title",
    "description",
    "target",
    "owner_id",
    "tasks",
    "note",
    "announce_message_id",
    "is_active",
]


def _activity(**overrides) -> Activity:
    defaults = dict(
        activity_id="activity_1",
        starts_at=datetime(2026, 9, 10, 14, 0, tzinfo=JST),
        duration_min=120,
        location="部室",
        title="定例会",
        description="",
        target="",
        owner_id="o1",
        tasks="",
        note="",
        announce_message_id=None,
        is_active=True,
    )
    defaults.update(overrides)
    return Activity(**defaults)


def test_build_announcement_payload_includes_title_datetime_and_location():
    payload = build_announcement_payload(_activity())

    assert "定例会" in payload["content"]
    assert "9/10(木) 14:00〜" in payload["content"]
    assert "部室" in payload["content"]
    assert len(payload["components"]) == 1
    assert len(payload["components"][0]["components"]) == 3


def test_build_announcement_payload_omits_location_line_when_blank():
    payload = build_announcement_payload(_activity(location=""))

    assert "場所" not in payload["content"]


class FakeBotClient:
    def __init__(self, message_id: str = "msg-1") -> None:
        self.message_id = message_id
        self.calls: list[tuple[str, dict]] = []

    async def create_message(self, channel_id: str, payload: dict) -> dict:
        self.calls.append((channel_id, payload))
        return {"id": self.message_id}


async def test_announce_activity_saves_message_id(fake_client_factory):
    sheet = fake_client_factory(
        "activities",
        header=ACTIVITIES_HEADER,
        rows=[
            [
                "activity_1",
                "2026-09-10T14:00:00+09:00",
                "120",
                "部室",
                "定例会",
                "",
                "",
                "o1",
                "",
                "",
                "",
                "TRUE",
            ]
        ],
    )
    repo = SheetRepository(sheet, "activities")
    bot_client = FakeBotClient(message_id="msg-99")

    message_id = await announce_activity(
        _activity(), bot_client=bot_client, activities_repo=repo, channel_id="channel-1"
    )

    assert message_id == "msg-99"
    assert bot_client.calls[0][0] == "channel-1"
    stored = repo.read_all()
    assert stored[0]["announce_message_id"] == "msg-99"
