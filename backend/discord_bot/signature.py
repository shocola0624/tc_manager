from __future__ import annotations

from fastapi import Request
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from auth.config import AuthSettings
from errors import AppError

_SIGNATURE_HEADER = "X-Signature-Ed25519"
_TIMESTAMP_HEADER = "X-Signature-Timestamp"


async def verify_discord_signature(request: Request) -> bytes:
    """Ed25519 署名を検証し、検証済みの生の request body を返す(CLAUDE.md §3)。

    これを省くと誰でも偽の Interaction を送信できるため必須。検証失敗時は
    401 を返す(署名なし・不正な署名・タイムスタンプ欠落のいずれも同一の扱い)。
    """
    settings: AuthSettings = request.app.state.auth_settings
    signature = request.headers.get(_SIGNATURE_HEADER)
    timestamp = request.headers.get(_TIMESTAMP_HEADER)
    body = await request.body()

    if signature is None or timestamp is None:
        raise AppError(401, "invalid_discord_signature", "missing signature headers")

    try:
        verify_key = VerifyKey(bytes.fromhex(settings.discord_public_key))
        verify_key.verify(timestamp.encode() + body, bytes.fromhex(signature))
    except (BadSignatureError, ValueError) as exc:
        raise AppError(401, "invalid_discord_signature", "signature verification failed") from exc

    return body
