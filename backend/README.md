# Techspresso for Students — バックエンド

コーヒーサークルの管理アプリのバックエンド(FastAPI)。設計方針はリポジトリルートの `CLAUDE.md` を参照。

Google スプレッドシートがデータの正であり、このバックエンドは以下のみを担当する。

- Discord OAuth2 によるログイン・初回登録
- バリデーション付きの Sheets 書き込み口
- 横断的な結合ビューの生成(後続フェーズ)

## セットアップ

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

`.env` を編集して以下を埋める。

### Google Sheets

| 変数 | 内容 |
|---|---|
| `SPREADSHEET_ID` | 対象スプレッドシートの ID(URL の `/d/` と `/edit` の間) |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | サービスアカウントの秘密鍵 JSON ファイルへのパス。**コミットしないこと**(`.gitignore` で `secrets/` を除外済み) |

サービスアカウントを作成したら、対象スプレッドシートをそのサービスアカウントのメールアドレス(`xxx@xxx.iam.gserviceaccount.com`)に編集者として共有すること。

### Discord OAuth2 / Bot

1. [Discord Developer Portal](https://discord.com/developers/applications) で新規アプリケーションを作成する
2. **OAuth2** タブ
   - `Client ID` / `Client Secret` を控えて `.env` の `DISCORD_CLIENT_ID` / `DISCORD_CLIENT_SECRET` に設定する
   - **Redirects** にローカル開発用のリダイレクト URI を追加する:
     ```
     http://localhost:8000/auth/discord/callback
     ```
     (ポートを変える場合は `.env` の `DISCORD_REDIRECT_URI` もあわせて変更すること。本番用の URI を追加する場合もここに追記する)
   - このアプリはログインに `identify` スコープのみを要求する。他のスコープを追加する必要はない
3. **Bot** タブ
   - Bot を作成し、トークンを発行して `.env` の `DISCORD_BOT_TOKEN` に設定する
   - **特権 Gateway Intent(Server Members Intent 等)を有効にする必要はない。** このアプリは Gateway (WebSocket) 接続を使わず、ロール取得は REST API (`GET /guilds/{guild_id}/members/{user_id}`) をサーバー側から都度呼ぶだけのため(CLAUDE.md §3)
4. **OAuth2 → URL Generator** タブ
   - `SCOPES` で `bot` のみを選択(`bot` に対する追加権限は不要。メンバー情報の取得に特別な権限ビットは要らない)
   - 生成された URL を開き、Bot をサークルの Discord サーバーへ招待する
5. サークルの Discord サーバーの ID を調べて `.env` の `DISCORD_GUILD_ID` に設定する(ユーザー設定 → 詳細設定 → 開発者モードを ON にすると、サーバーアイコンを右クリックして「サーバーIDをコピー」できる)
6. `admin` / `officer` に自動割り当てたい Discord ロールをそれぞれ右クリック→「ロールIDをコピー」し、`.env` の `DISCORD_ADMIN_ROLE_ID` / `DISCORD_OFFICER_ROLE_ID` に設定する(どちらも省略可。省略した場合、そのロールへの自動昇格は行われず既定の `member` のままになる)
7. **General Information** タブの `Public Key` を控えて `.env` の `DISCORD_PUBLIC_KEY` に設定する(Interactions の Ed25519 署名検証に使う。CLAUDE.md §3)
8. アナウンス(出欠ボタン付きRSVP告知)を投稿したいテキストチャンネルの ID を調べて `.env` の `DISCORD_ANNOUNCE_CHANNEL_ID` に設定する(チャンネルを右クリック→「チャンネルIDをコピー」)。Bot をそのチャンネルに投稿できる権限(閲覧・メッセージ送信)で招待しておくこと
9. 「活動を確定する」ボタンで投稿する確定情報(器具・予算・タスク等をまとめた長文)は上記とは別のチャンネルに投稿する想定。投稿先チャンネルの ID を `.env` の `DISCORD_CONFIRM_ANNOUNCE_CHANNEL_ID` に設定する(同じチャンネルにしたい場合は `DISCORD_ANNOUNCE_CHANNEL_ID` と同じ値でよい)

ロールの自動割り当ては **ログインのたびに** Discord 側のロールと再同期される。シート上で `role` 列を手動編集しても、次回ログイン時に Discord 側の状態で上書きされる点に注意(CLAUDE.md §6)。

### Interactions エンドポイント(出欠ボタン)

Discord は Gateway (WebSocket) ではなく HTTP で Interaction を送ってくる(CLAUDE.md §3)。**General Information** タブの `Interactions Endpoint URL` に、このアプリの公開 URL + `/discord/interactions` を設定する必要がある(例: `https://xxxx.example.com/discord/interactions`)。

- 保存時に Discord から `PING` が送られてくるので、サーバーが実際に起動していて `DISCORD_PUBLIC_KEY` が正しくないと保存できない
- ローカル開発では下記の「ローカルでの動作確認」を参照してトンネリングすること
- 本番相当の URL が決まるまでは Interactions Endpoint URL を未設定のままにしておいてよい(出欠ボタン以外の機能には影響しない)

### 常駐しない構成についての既知の制約

出欠ボタン応答は「deferred response を即返す → バックグラウンドで Sheets 更新 → follow-up 送信」という非同期フローで実装しており(CLAUDE.md §3)、後段の処理は FastAPI の `BackgroundTasks`(1リクエストのライフサイクル内で完結し、常駐ワーカーを新設するものではない)で行っている。これは `uvicorn` のような常時起動プロセスを前提とした仕組みであり、将来 Cloudflare Workers / Vercel Functions のようなレスポンス送信後に処理が打ち切られる環境へ移行する場合は、`ctx.waitUntil()` 等プラットフォーム固有の仕組みへの置き換えが別途必要になる。

### セッション / フロントエンド連携

| 変数 | 内容 |
|---|---|
| `SESSION_SECRET_KEY` | セッション Cookie の署名鍵。以下で生成できる:<br>`python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `FRONTEND_BASE_URL` | フロントエンドのオリジン。ログイン完了後のリダイレクト先、および CORS の許可オリジンとして使う(例: `http://localhost:5173`) |
| `COOKIE_SECURE` | セッション Cookie の `Secure` 属性。ローカル開発(http)では `false`、本番(https)では `true` にする |

## 起動

```bash
uvicorn main:app --reload --port 8000
```

## テスト

```bash
python -m pytest
```

Sheets API・Discord API はすべてテスト内でモックしており、実際の外部サービスへは接続しない。

## ローカルでの動作確認(Interactions エンドポイント)

Discord は Interactions Endpoint URL に対して実際に HTTP POST できる必要があるため、`localhost` のままでは検証できない。トンネリングツールで一時的に公開する。

```bash
# 例1: cloudflared(アカウント登録不要ですぐ使える)
cloudflared tunnel --url http://localhost:8000

# 例2: ngrok
ngrok http 8000
```

いずれかを実行すると `https://xxxx.trycloudflare.com` のような URL が発行される。

1. `uvicorn main:app --reload --port 8000` でバックエンドを起動しておく
2. 上記のトンネリングコマンドを別ターミナルで実行し、発行された URL を控える
3. [Discord Developer Portal](https://discord.com/developers/applications) の対象アプリ → **General Information** → `Interactions Endpoint URL` に `https://xxxx.trycloudflare.com/discord/interactions` を設定して保存する
4. 保存時に Discord からその場で `PING` が送られ、`{"type": 1}` が返れば検証成功として保存される(失敗する場合はサーバーが起動しているか、`DISCORD_PUBLIC_KEY` が正しいかを確認する)
5. `POST /api/activities/{activity_id}/announce` でアナウンスを投稿し、Discord 上でボタンを押して follow-up メッセージ(自分にしか見えない)が届くことを確認する

トンネリングの URL は再起動のたびに変わる(ngrok 無料プラン・cloudflared のクイックトンネルいずれも)。検証のたびに Interactions Endpoint URL を更新すること。

## エンドポイント一覧

### フェーズ2: 認証

| メソッド/パス | 認可 | 概要 |
|---|---|---|
| `GET /auth/discord/login` | 不要 | Discord 認可 URL(scope=`identify`)へリダイレクト |
| `GET /auth/discord/callback` | 不要 | OAuth コールバック。登録状況に応じてフロントの `/register` または `/` へリダイレクト |
| `POST /auth/register` | pending cookie | 初回登録(name のみ入力。role は自動算出され本人は選べない) |
| `POST /auth/logout` | session cookie | セッション破棄 |
| `GET /auth/me` | session cookie | 現在のユーザー情報を返す |

### フェーズ6: Discordアナウンス・出欠

| メソッド/パス | 認可 | 概要 |
|---|---|---|
| `POST /api/activities/{activity_id}/announce` | admin/officer | Discordチャンネルへアナウンスを投稿し、出欠ボタンを付与。`announce_message_id` を保存 |
| `PUT /api/attendance/{activity_id}` | 全 is_active ユーザー(本人分のみ) | 自分の出欠を登録・更新する |
| `POST /discord/interactions` | Discord 署名(Ed25519) | Discord Interactions の受け口。PING応答、出欠ボタン押下の deferred ack + follow-up |
