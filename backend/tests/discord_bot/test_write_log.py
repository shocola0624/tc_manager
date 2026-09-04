from discord_bot.write_log import log_write


class FakeBotClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[str, dict]] = []

    async def create_message(self, channel_id: str, payload: dict) -> dict:
        self.calls.append((channel_id, payload))
        if self.fail:
            raise RuntimeError("discord unavailable")
        return {"id": "msg-1"}


async def test_successful_write_posts_success_embed_with_actor_and_record():
    bot_client = FakeBotClient()
    written = []

    await log_write(
        lambda: written.append("done"),
        bot_client=bot_client,
        channel_id="log-channel",
        actor_name="Alice",
        actor_id="u1",
        sheet_name="items",
        operation="append",
        record={"item_id": "item_1", "name": "V60"},
    )

    assert written == ["done"]
    assert len(bot_client.calls) == 1
    channel_id, payload = bot_client.calls[0]
    assert channel_id == "log-channel"
    embed = payload["embeds"][0]
    assert embed["title"] == "✅ items.append"
    assert "Alice (u1)" in embed["description"]
    assert "item_id: item_1" in embed["fields"][0]["value"]
    assert "name: V60" in embed["fields"][0]["value"]


async def test_failed_write_posts_failure_embed_and_reraises():
    bot_client = FakeBotClient()

    def _boom():
        raise ValueError("boom")

    try:
        await log_write(
            _boom,
            bot_client=bot_client,
            channel_id="log-channel",
            actor_name="Alice",
            actor_id="u1",
            sheet_name="items",
            operation="update",
            record={"item_id": "item_1"},
        )
        raise AssertionError("expected ValueError to propagate")
    except ValueError:
        pass

    assert len(bot_client.calls) == 1
    embed = bot_client.calls[0][1]["embeds"][0]
    assert embed["title"] == "❌ items.update 失敗"
    assert "Alice (u1)" in embed["description"]
    assert "item_id: item_1" in embed["fields"][0]["value"]
    assert "boom" in embed["fields"][1]["value"]


async def test_discord_post_failure_does_not_mask_write_result():
    bot_client = FakeBotClient(fail=True)
    written = []

    # 書き込み自体は成功しているので、Discordへのログ投稿が失敗しても例外を送出しない。
    await log_write(
        lambda: written.append("done"),
        bot_client=bot_client,
        channel_id="log-channel",
        actor_name="Alice",
        actor_id="u1",
        sheet_name="items",
        operation="append",
        record={"item_id": "item_1"},
    )

    assert written == ["done"]
