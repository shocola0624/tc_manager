from __future__ import annotations

from dataclasses import dataclass

from fastapi import Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


@dataclass(frozen=True)
class CookieSpec:
    name: str
    salt: str
    max_age_seconds: int


# CSRF 対策用。認可 URL へのリダイレクト直前に発行し、コールバックで検証したら破棄する。
STATE_COOKIE = CookieSpec(name="tc_oauth_state", salt="oauth_state", max_age_seconds=60 * 10)

# 初回登録フォームに遷移させるためだけの、discord_user_id のみを載せた短命な cookie。
PENDING_COOKIE = CookieSpec(
    name="tc_pending_registration", salt="pending_registration", max_age_seconds=60 * 15
)

# 認証済みセッション。discord_user_id のみを載せ、role/is_active は毎リクエスト
# users シートを読み直して判定する(サーバー側に状態を持たないため)。
SESSION_COOKIE = CookieSpec(name="tc_session", salt="session", max_age_seconds=60 * 60 * 24 * 30)


class SessionSigner:
    """cookie の署名・検証を行う。サーバー側にセッションストアは持たない。"""

    def __init__(self, secret_key: str) -> None:
        self._secret_key = secret_key

    def sign(self, spec: CookieSpec, payload: dict[str, str]) -> str:
        serializer = URLSafeTimedSerializer(self._secret_key, salt=spec.salt)
        return serializer.dumps(payload)

    def unsign(self, spec: CookieSpec, token: str) -> dict[str, str] | None:
        """検証に失敗した、または有効期限切れの場合は None を返す(例外を外へ漏らさない)"""
        serializer = URLSafeTimedSerializer(self._secret_key, salt=spec.salt)
        try:
            return serializer.loads(token, max_age=spec.max_age_seconds)
        except (BadSignature, SignatureExpired):
            return None


def set_cookie(
    response: Response, spec: CookieSpec, signer: SessionSigner, payload: dict[str, str], *, secure: bool
) -> None:
    response.set_cookie(
        key=spec.name,
        value=signer.sign(spec, payload),
        max_age=spec.max_age_seconds,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )


def clear_cookie(response: Response, spec: CookieSpec) -> None:
    response.delete_cookie(key=spec.name, path="/")
