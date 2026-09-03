import json

import httpx
import pytest

from auth.discord_client import DiscordBotClient, DiscordOAuthClient, DiscordOAuthError


def _client_with_handler(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_build_authorize_url_requests_identify_scope_only(auth_settings):
    client = DiscordOAuthClient(auth_settings, httpx.AsyncClient())

    url = client.build_authorize_url("state123")

    assert "scope=identify" in url
    assert "client_id=client-id" in url
    assert "state=state123" in url
    assert "redirect_uri=" in url
    # client_secret はユーザーに見える認可 URL に含めてはならない
    assert "client_secret" not in url


async def test_exchange_code_returns_access_token(auth_settings):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v10/oauth2/token"
        body = request.read().decode()
        assert "client_secret=client-secret" in body
        assert "code=code123" in body
        return httpx.Response(200, json={"access_token": "tok123"})

    async with _client_with_handler(handler) as http_client:
        client = DiscordOAuthClient(auth_settings, http_client)
        token = await client.exchange_code("code123")

    assert token == "tok123"


async def test_exchange_code_raises_on_error_response(auth_settings):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="invalid_grant")

    async with _client_with_handler(handler) as http_client:
        client = DiscordOAuthClient(auth_settings, http_client)
        with pytest.raises(DiscordOAuthError):
            await client.exchange_code("bad-code")


async def test_fetch_current_user_parses_response(auth_settings):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer tok123"
        return httpx.Response(200, json={"id": "u1", "username": "alice"})

    async with _client_with_handler(handler) as http_client:
        client = DiscordOAuthClient(auth_settings, http_client)
        user = await client.fetch_current_user("tok123")

    assert user.id == "u1"
    assert user.username == "alice"


async def test_fetch_member_role_ids_returns_roles_using_bot_token(auth_settings):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bot bot-token"
        assert request.url.path == "/api/v10/guilds/guild-1/members/u1"
        return httpx.Response(200, json={"roles": ["role-officer"]})

    async with _client_with_handler(handler) as http_client:
        client = DiscordBotClient(auth_settings, http_client)
        roles = await client.fetch_member_role_ids("u1")

    assert roles == ["role-officer"]


async def test_fetch_member_role_ids_returns_none_when_not_a_guild_member(auth_settings):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    async with _client_with_handler(handler) as http_client:
        client = DiscordBotClient(auth_settings, http_client)
        roles = await client.fetch_member_role_ids("u1")

    assert roles is None


async def test_fetch_member_role_ids_raises_on_unexpected_error(auth_settings):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    async with _client_with_handler(handler) as http_client:
        client = DiscordBotClient(auth_settings, http_client)
        with pytest.raises(DiscordOAuthError):
            await client.fetch_member_role_ids("u1")


async def test_send_direct_message_opens_channel_then_posts_content(auth_settings):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        assert request.headers["authorization"] == "Bot bot-token"
        if request.url.path == "/api/v10/users/@me/channels":
            assert json.loads(request.read())["recipient_id"] == "u1"
            return httpx.Response(200, json={"id": "channel-1"})
        assert request.url.path == "/api/v10/channels/channel-1/messages"
        return httpx.Response(200, json={"id": "msg-1"})

    async with _client_with_handler(handler) as http_client:
        client = DiscordBotClient(auth_settings, http_client)
        await client.send_direct_message("u1", "hello")

    assert calls == ["/api/v10/users/@me/channels", "/api/v10/channels/channel-1/messages"]


async def test_send_direct_message_raises_when_channel_open_fails(auth_settings):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="cannot send messages to this user")

    async with _client_with_handler(handler) as http_client:
        client = DiscordBotClient(auth_settings, http_client)
        with pytest.raises(DiscordOAuthError):
            await client.send_direct_message("u1", "hello")
