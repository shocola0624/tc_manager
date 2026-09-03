from urllib.parse import parse_qs, urlparse

from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth.dependencies import (
    get_auth_settings,
    get_bot_client,
    get_oauth_client,
    get_signer,
    get_users_repository,
)
from auth.discord_client import DiscordUser
from auth.router import router as auth_router
from auth.session import SESSION_COOKIE, SessionSigner
from errors import install_exception_handlers

ACTIVE_USER_ROW = {
    "discord_user_id": "u1",
    "name": "Alice",
    "role": "member",
    "is_active": "TRUE",
    "locale": "ja",
    "registered_at": "2026-01-01T00:00:00+09:00",
}


class FakeOAuthClient:
    def __init__(self, discord_user: DiscordUser) -> None:
        self.discord_user = discord_user

    def build_authorize_url(self, state: str) -> str:
        return f"https://discord.com/oauth2/authorize?state={state}"

    async def exchange_code(self, code: str) -> str:
        return "access-token"

    async def fetch_current_user(self, access_token: str) -> DiscordUser:
        return self.discord_user


class FakeBotClient:
    def __init__(self, role_ids: list[str] | None) -> None:
        self.role_ids = role_ids

    async def fetch_member_role_ids(self, discord_user_id: str) -> list[str] | None:
        return self.role_ids


def _login_state(login_response) -> str:
    """login のリダイレクト先 URL(Discord 認可 URL)から生の state を取り出す。

    tc_oauth_state cookie の値は署名済みトークンであり、Discord に渡す生の state
    そのものではないため、混同しないよう明示的に区別する。
    """
    location = login_response.headers["location"]
    return parse_qs(urlparse(location).query)["state"][0]


def _build_client(users_repo, auth_settings, oauth_client, bot_client) -> TestClient:
    app = FastAPI()
    install_exception_handlers(app)
    app.include_router(auth_router)
    app.dependency_overrides[get_signer] = lambda: SessionSigner(auth_settings.session_secret_key)
    app.dependency_overrides[get_users_repository] = lambda: users_repo
    app.dependency_overrides[get_oauth_client] = lambda: oauth_client
    app.dependency_overrides[get_bot_client] = lambda: bot_client
    app.dependency_overrides[get_auth_settings] = lambda: auth_settings
    return TestClient(app)


def test_login_redirects_to_discord_and_sets_state_cookie(users_repo, auth_settings):
    client = _build_client(
        users_repo, auth_settings, FakeOAuthClient(DiscordUser("u1", "alice")), FakeBotClient([])
    )

    response = client.get("/auth/discord/login", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"].startswith("https://discord.com/oauth2/authorize")
    assert "tc_oauth_state" in response.cookies


def test_callback_redirects_new_user_to_register_with_pending_cookie(users_repo, auth_settings):
    client = _build_client(
        users_repo, auth_settings, FakeOAuthClient(DiscordUser("u1", "alice")), FakeBotClient([])
    )
    login_response = client.get("/auth/discord/login", follow_redirects=False)
    state = _login_state(login_response)

    response = client.get(f"/auth/discord/callback?code=abc&state={state}", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "http://localhost:5173/register"
    assert "tc_pending_registration" in response.cookies
    assert "tc_session" not in response.cookies


def test_callback_rejects_mismatched_state(users_repo, auth_settings):
    client = _build_client(
        users_repo, auth_settings, FakeOAuthClient(DiscordUser("u1", "alice")), FakeBotClient([])
    )
    client.get("/auth/discord/login", follow_redirects=False)

    response = client.get("/auth/discord/callback?code=abc&state=wrong", follow_redirects=False)

    assert response.status_code == 302
    assert "error=oauth_failed" in response.headers["location"]
    assert "tc_session" not in response.cookies


def test_callback_rejects_inactive_user(users_repo, auth_settings):
    users_repo.append({**ACTIVE_USER_ROW, "is_active": "FALSE"})
    client = _build_client(
        users_repo, auth_settings, FakeOAuthClient(DiscordUser("u1", "alice")), FakeBotClient([])
    )
    login_response = client.get("/auth/discord/login", follow_redirects=False)
    state = _login_state(login_response)

    response = client.get(f"/auth/discord/callback?code=abc&state={state}", follow_redirects=False)

    assert response.status_code == 302
    assert "error=inactive" in response.headers["location"]
    assert "tc_session" not in response.cookies


def test_callback_resyncs_role_on_login_when_changed(users_repo, auth_settings):
    users_repo.append(ACTIVE_USER_ROW)
    client = _build_client(
        users_repo,
        auth_settings,
        FakeOAuthClient(DiscordUser("u1", "alice")),
        FakeBotClient(["role-admin"]),
    )
    login_response = client.get("/auth/discord/login", follow_redirects=False)
    state = _login_state(login_response)

    response = client.get(f"/auth/discord/callback?code=abc&state={state}", follow_redirects=False)

    assert response.status_code == 302
    assert "tc_session" in response.cookies
    assert users_repo.read_all()[0]["role"] == "admin"


def test_callback_does_not_write_when_role_unchanged(users_repo, auth_settings):
    users_repo.append(ACTIVE_USER_ROW)
    client = _build_client(
        users_repo, auth_settings, FakeOAuthClient(DiscordUser("u1", "alice")), FakeBotClient([])
    )
    login_response = client.get("/auth/discord/login", follow_redirects=False)
    state = _login_state(login_response)

    client.get(f"/auth/discord/callback?code=abc&state={state}", follow_redirects=False)

    assert users_repo.read_all()[0]["role"] == "member"


def test_register_creates_user_row_with_computed_role_and_sets_session(users_repo, auth_settings):
    client = _build_client(
        users_repo,
        auth_settings,
        FakeOAuthClient(DiscordUser("u1", "alice")),
        FakeBotClient(["role-officer"]),
    )
    login_response = client.get("/auth/discord/login", follow_redirects=False)
    state = _login_state(login_response)
    client.get(f"/auth/discord/callback?code=abc&state={state}", follow_redirects=False)

    response = client.post("/auth/register", json={"name": "Alice"})

    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "officer"
    assert "tc_session" in response.cookies

    stored = users_repo.read_all()
    assert len(stored) == 1
    assert stored[0]["role"] == "officer"
    assert stored[0]["is_active"] == "TRUE"
    assert stored[0]["locale"] == "ja"
    assert stored[0]["registered_at"] != ""


def test_register_without_pending_cookie_is_rejected(users_repo, auth_settings):
    client = _build_client(
        users_repo, auth_settings, FakeOAuthClient(DiscordUser("u1", "alice")), FakeBotClient([])
    )

    response = client.post("/auth/register", json={"name": "Alice"})

    assert response.status_code == 401


def test_register_twice_is_rejected_as_conflict(users_repo, auth_settings):
    client = _build_client(
        users_repo, auth_settings, FakeOAuthClient(DiscordUser("u1", "alice")), FakeBotClient([])
    )
    login_response = client.get("/auth/discord/login", follow_redirects=False)
    state = _login_state(login_response)
    client.get(f"/auth/discord/callback?code=abc&state={state}", follow_redirects=False)
    client.post("/auth/register", json={"name": "Alice"})

    # 別タブ等でもう一度 register を叩いても pending cookie はもう無いので 401 になる
    response = client.post("/auth/register", json={"name": "Alice again"})

    assert response.status_code == 401


def test_logout_clears_session_cookie(users_repo, auth_settings):
    client = _build_client(
        users_repo, auth_settings, FakeOAuthClient(DiscordUser("u1", "alice")), FakeBotClient([])
    )

    response = client.post("/auth/logout")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_me_returns_current_user_when_session_valid(users_repo, auth_settings):
    users_repo.append(ACTIVE_USER_ROW)
    client = _build_client(
        users_repo, auth_settings, FakeOAuthClient(DiscordUser("u1", "alice")), FakeBotClient([])
    )
    signer = SessionSigner(auth_settings.session_secret_key)
    client.cookies.set(SESSION_COOKIE.name, signer.sign(SESSION_COOKIE, {"discord_user_id": "u1"}))

    response = client.get("/auth/me")

    assert response.status_code == 200
    assert response.json()["discord_user_id"] == "u1"


def test_me_without_session_returns_401(users_repo, auth_settings):
    client = _build_client(
        users_repo, auth_settings, FakeOAuthClient(DiscordUser("u1", "alice")), FakeBotClient([])
    )

    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_me_with_pending_cookie_but_no_session_returns_registration_incomplete(
    users_repo, auth_settings
):
    """Discord 認証後、本登録前は session cookie ではなく pending cookie しか無い。
    このとき /auth/me は not_authenticated ではなく registration_incomplete を返す必要がある
    (フロントエンドの AuthProvider はこれを見て /register 画面へ遷移する)。"""
    client = _build_client(
        users_repo, auth_settings, FakeOAuthClient(DiscordUser("u1", "alice")), FakeBotClient([])
    )
    login_response = client.get("/auth/discord/login", follow_redirects=False)
    state = _login_state(login_response)
    client.get(f"/auth/discord/callback?code=abc&state={state}", follow_redirects=False)

    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "registration_incomplete"


def test_me_after_completing_registration_returns_current_user(users_repo, auth_settings):
    client = _build_client(
        users_repo, auth_settings, FakeOAuthClient(DiscordUser("u1", "alice")), FakeBotClient([])
    )
    login_response = client.get("/auth/discord/login", follow_redirects=False)
    state = _login_state(login_response)
    client.get(f"/auth/discord/callback?code=abc&state={state}", follow_redirects=False)
    client.post("/auth/register", json={"name": "Alice"})

    response = client.get("/auth/me")

    assert response.status_code == 200
    assert response.json()["discord_user_id"] == "u1"
