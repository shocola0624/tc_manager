from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from .config import AuthSettings

_API_BASE = "https://discord.com/api/v10"
_AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
_OAUTH_SCOPE = "identify"


class DiscordOAuthError(Exception):
    """OAuth2 のコード交換・ユーザー情報取得に失敗した"""


@dataclass(frozen=True)
class DiscordUser:
    id: str
    username: str


class DiscordOAuthClient:
    """identify スコープのみを要求する OAuth2 クライアント。

    client_secret はこのクラス内(サーバー側)でのみ使用し、フロントエンドへは渡さない。
    """

    def __init__(self, settings: AuthSettings, http_client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http = http_client

    def build_authorize_url(self, state: str) -> str:
        params = {
            "client_id": self._settings.discord_client_id,
            "redirect_uri": self._settings.discord_redirect_uri,
            "response_type": "code",
            "scope": _OAUTH_SCOPE,
            "state": state,
        }
        return f"{_AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> str:
        response = await self._http.post(
            f"{_API_BASE}/oauth2/token",
            data={
                "client_id": self._settings.discord_client_id,
                "client_secret": self._settings.discord_client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self._settings.discord_redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if response.status_code != 200:
            raise DiscordOAuthError(f"token exchange failed: {response.status_code} {response.text}")
        access_token = response.json().get("access_token")
        if not access_token:
            raise DiscordOAuthError("token exchange response missing access_token")
        return access_token

    async def fetch_current_user(self, access_token: str) -> DiscordUser:
        response = await self._http.get(
            f"{_API_BASE}/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.status_code != 200:
            raise DiscordOAuthError(f"fetch current user failed: {response.status_code} {response.text}")
        body = response.json()
        return DiscordUser(id=body["id"], username=body["username"])


class DiscordBotClient:
    """Bot トークンでのサーバー間 REST 呼び出しのみを行う。Gateway (WebSocket) 接続は使わない。"""

    def __init__(self, settings: AuthSettings, http_client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http = http_client

    async def fetch_member_role_ids(self, discord_user_id: str) -> list[str] | None:
        """指定ユーザーのギルドメンバーが持つロール ID 一覧を返す。ギルド未所属(404)なら None。"""
        response = await self._http.get(
            f"{_API_BASE}/guilds/{self._settings.discord_guild_id}/members/{discord_user_id}",
            headers={"Authorization": f"Bot {self._settings.discord_bot_token}"},
        )
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise DiscordOAuthError(
                f"fetch guild member failed: {response.status_code} {response.text}"
            )
        return response.json().get("roles", [])

    async def create_message(self, channel_id: str, payload: dict) -> dict:
        """指定チャンネルへメッセージを送信する(REST API 呼び出しのみ、Gateway 不使用)。"""
        response = await self._http.post(
            f"{_API_BASE}/channels/{channel_id}/messages",
            headers={"Authorization": f"Bot {self._settings.discord_bot_token}"},
            json=payload,
        )
        if response.status_code not in (200, 201):
            raise DiscordOAuthError(
                f"create message failed: {response.status_code} {response.text}"
            )
        return response.json()

    async def send_direct_message(self, discord_user_id: str, content: str) -> None:
        """指定ユーザーとのDMチャンネルを開いてメッセージを送信する(REST呼び出しのみ)。

        相手がBotと同じギルドにいない、DMを拒否している等で失敗しうる。
        呼び出し元(discord_bot/notifications.py)で例外を握りつぶす想定。
        """
        response = await self._http.post(
            f"{_API_BASE}/users/@me/channels",
            headers={"Authorization": f"Bot {self._settings.discord_bot_token}"},
            json={"recipient_id": discord_user_id},
        )
        if response.status_code != 200:
            raise DiscordOAuthError(
                f"open DM channel failed: {response.status_code} {response.text}"
            )
        channel_id = response.json()["id"]
        await self.create_message(channel_id, {"content": content})
