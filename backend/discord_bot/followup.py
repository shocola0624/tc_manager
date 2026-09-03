from __future__ import annotations

import httpx

_API_BASE = "https://discord.com/api/v10"
_EPHEMERAL_FLAG = 1 << 6


async def send_followup(
    http_client: httpx.AsyncClient,
    application_id: str,
    interaction_token: str,
    *,
    content: str,
    ephemeral: bool = True,
) -> None:
    """deferred ack の follow-up メッセージを送る。interaction token 自体が認可情報のため
    Bot トークンは不要(CLAUDE.md §3: 3秒の応答期限に間に合わない前提の非同期フロー)。"""
    payload: dict = {"content": content}
    if ephemeral:
        payload["flags"] = _EPHEMERAL_FLAG
    await http_client.post(
        f"{_API_BASE}/webhooks/{application_id}/{interaction_token}",
        json=payload,
    )
