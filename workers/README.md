# tc-manager-reminders (Cloudflare Workers)

タスクの期限リマインドのDiscord配信と、活動・タスクのGoogleカレンダーへの
一方向同期を行うCronジョブ。`backend/`(FastAPI)とは別の
デプロイ単位で、Cloudflare Workersの Cron Triggers(毎時0分)でのみ起動する
(CLAUDE.md §3: 常駐プロセスを持たない方針をここでも踏襲する)。

## 構成

```
src/
  types.ts       共通の型(Env, TaskRow, AssigneeRow, ReminderLogRow)
  googleAuth.ts  サービスアカウントのJWT(RS256)署名・アクセストークン取得
                 (Web Crypto APIで自前実装。Node の crypto は使えない)
  sheets.ts      Sheets API への薄いREST呼び出し(まとめ読み・まとめ書き)
  discord.ts     Discord REST API(チャンネル投稿・DM送信のみ、Gateway不使用)
  parsing.ts     シートの生データを型付きレコードに変換(壊れた行はスキップ)
  reminders.ts   冪等性・部分失敗を考慮したコアロジック(純粋関数が中心)
  googleCalendar.ts  Calendar API への薄いREST呼び出し(list/insert/update/delete)
  calendarSync.ts    カレンダー同期の差分計算・実行(純粋関数が中心)
  index.ts       Cron ハンドラ(scheduled)。リマインド → カレンダー同期の順に実行する
                 薄い層。片方が失敗してももう片方は実行する
```

現時点ではチャンネル投稿・DM送信の両方を実装済み。まずチャンネル投稿だけで
動作確認し、問題なければDM送信も有効なまま運用する(コード上は同時に実装済みで、
段階的に有効化したい場合は `index.ts` の `dispatchReminders` に渡す `deps` を
一時的に絞ることもできる)。

## デプロイ手順(チェックリスト)

1. `npm install`
2. スプレッドシートの準備(一回限り。既にあれば何もしないスクリプト):
   `cd ../backend && uv run python scripts/create_reminder_log_sheet.py`
   (`reminder_log` シートが無いと Cron が毎回失敗する)
3. `.prod.vars` に本番の値を記入する(`.dev.vars.example` と同じ形式。`.gitignore` 済み)
4. `npx wrangler login`(ブラウザで Cloudflare にログイン)
5. `npm run secrets:push` で `.prod.vars` の値をまとめて Cloudflare に登録する
   (必須項目が空なら登録せずに止まる。値は画面に表示しない)
6. `npm run deploy`(デプロイ前に型チェックとテストが自動で走る)
7. Cloudflare のダッシュボードで Worker の「Logs」を開き、次の毎時0分の実行結果を確認する

ローカルで試す場合は `.dev.vars` に値を書いて `npx wrangler dev --test-scheduled` を起動し、
`http://localhost:8787/__scheduled` を開くと Cron を1回だけ手動実行できる。
**`.dev.vars` に本番の Bot トークンを書いた状態で実行すると、期限を過ぎたタスクのリマインドが
実際に Discord へ送信される**ので注意(送信せずに読み込みだけ確かめたいときは、
トークンをダミー値にしておけば送信がすべて失敗し、`reminder_log` にも書き込まれない)。

## セットアップ

### 1. 依存関係のインストール

```bash
cd workers
npm install
```

### 2. Google サービスアカウント

`backend/secrets/service-account.json` と同じサービスアカウントを使い回せる
(Sheets APIのスコープは共通)。JSONファイルの中身をそのまま1つのシークレットとして
Workersに登録する(ファイルパスではなく中身の文字列を渡す点に注意)。

### 3. Discord Bot

`backend/.env` の `DISCORD_BOT_TOKEN` と同じBotを使ってもよいが、
**開発環境と本番環境でBotトークンを分けることを推奨する**(誤って開発中に
本番チャンネルへ投稿してしまう事故を防ぐため)。開発用Botを別途作成し、
検証用のDiscordサーバー・チャンネルに招待しておく。

### 4. チャンネルIDの準備

タスクの `visibility`(admin/officer/member)ごとに投稿先チャンネルを分ける
(ユーザー要件)。Discordアプリの開発者モードを有効にし、チャンネルを右クリックして
「IDをコピー」で3つ分取得する。

### 5. Googleカレンダー(同期を使う場合のみ)

`GOOGLE_CALENDAR_ID` を登録しなければカレンダー同期はスキップされ、リマインドだけが動く。

1. [Google Cloud Console](https://console.cloud.google.com/) で、サービスアカウントが
   属するプロジェクトの「APIとサービス」→「ライブラリ」から **Google Calendar API を有効化**する
2. Googleカレンダーで**同期専用の新しいカレンダーを作成**する(「他のカレンダー」→「＋」→
   「新しいカレンダーを作成」)。既存の個人カレンダーは使わない
3. 作成したカレンダーの「設定と共有」→「特定のユーザーまたはグループと共有する」で、
   サービスアカウントのメールアドレス(`service-account.json` の `client_email`)を追加し、
   権限を **「予定の変更」** にする
4. 同じ画面の「カレンダーの統合」にある **カレンダーID**(`...@group.calendar.google.com`)を
   控え、`GOOGLE_CALENDAR_ID` として登録する
5. 部員にはこのカレンダーを閲覧権限で共有する
6. `activities` シートに `google_event_id` 列を追加する(一回限り):

   ```bash
   cd backend && uv run python scripts/add_google_event_id_column.py
   ```

   (`tasks` シートには作成時から列がある)

#### 同期の仕様

- **アプリ → Google の一方向のみ**。Googleカレンダー上で予定を編集しても、次回の同期で
  シートの内容に上書きされる(説明欄にその旨を記載している)
- 対象: `is_active` が TRUE の活動すべてと、**`visibility=member` のタスクのみ**。
  幹部限定(admin/officer)のタスクは、部員に共有するカレンダーへ漏れないよう同期しない
- 色: 活動=青(Blueberry)、タスク=オレンジ(Tangerine)、完了タスク=灰色(Graphite)。
  タスクは期限時刻から30分の枠として登録し、タイトル先頭に `〆`(完了なら `✓`)を付ける
- 論理削除(`is_active=FALSE`)された行や、member 以外へ公開範囲を変えたタスクの予定は
  カレンダーから削除される。**人間が同じカレンダーに手で追加した予定は削除しない**
  (アプリが作った予定は `extendedProperties` で識別している)
- イベントIDは `activity_id`/`task_id` から決定的に生成する。そのため `google_event_id` 列への
  書き戻しが失敗したり、部員が列の値を消したりしても**二重登録は起きない**
  (列は同期済みかどうかを人が確認するための記録で、次回の同期で書き直される)
- 毎時、カレンダーの現在の状態を1回で取得して**差分があるものだけ**書き込む
- 1回の実行あたりのカレンダー書き込みは30件まで(Workers Free プランのサブリクエスト上限
  50件への対策)。初回同期などで超えた分は次回以降の実行で順に反映される

## シークレットの登録

通常は `.prod.vars` に記入して `npm run secrets:push` で一括登録する(上記チェックリスト)。
個別に登録・変更したい場合は `wrangler secret put <NAME>` で1つずつ登録する(対話的にプロンプトが出るので、
そこに値を貼り付ける。`.env` のようなファイルにシークレットを書いてコミットしない)。

```bash
cd workers

# 本番環境向け(デフォルト環境)
wrangler secret put SPREADSHEET_ID
wrangler secret put GOOGLE_SERVICE_ACCOUNT_JSON   # JSONファイルの中身を1行で貼り付け
wrangler secret put DISCORD_BOT_TOKEN
wrangler secret put DISCORD_TASK_CHANNEL_ADMIN_ID
wrangler secret put DISCORD_TASK_CHANNEL_OFFICER_ID
wrangler secret put DISCORD_TASK_CHANNEL_MEMBER_ID
wrangler secret put GOOGLE_CALENDAR_ID            # カレンダー同期を使う場合のみ
```

`GOOGLE_SERVICE_ACCOUNT_JSON` に貼り付ける値は、JSONファイルの中身をそのまま
1行(改行はJSON文字列内の `\n` のままでよい)貼り付ければよい。例:

```bash
cat backend/secrets/service-account.json | wrangler secret put GOOGLE_SERVICE_ACCOUNT_JSON
```

### 開発環境を分ける場合

Wrangler の `--env` で環境を分けられる。例えば `wrangler.toml` に
`[env.development]` セクションを追加し、開発用スプレッドシート・開発用Botで
検証してから本番のシークレットを登録する、という進め方を推奨する
(本番データに対していきなりテスト送信しないため)。

```bash
wrangler secret put DISCORD_BOT_TOKEN --env development
wrangler dev --env development   # ローカルでCronを手動発火して確認
```

`wrangler dev` 実行中は `http://localhost:8787/__scheduled` にアクセスすると
Cronハンドラを手動で1回発火できる(本番を待たずに動作確認できる)。

## デプロイ

```bash
npm run deploy
```

## テスト

```bash
npm test
```

JWT署名・リマインド抽出・冪等性・部分失敗時の挙動など、副作用のあるAPI呼び出しを
除いたロジックはすべて単体テストでカバーしている(実際のGoogle/Discordへは接続しない)。

## 既知の制約・今後の対応

- `wrangler` は v3 系を使っている(v4 系は Node 22 以上が必要なため、開発環境の
  Node バージョンによってはこのまま v3 を使い続けるか、Node を上げてから
  `npm install --save-dev wrangler@4 @cloudflare/workers-types@5` へ上げるか判断すること)
- 書き込みログ(Discordの `DISCORD_LOG_CHANNEL_ID` への通知)はユーザー要件により
  Cronの実行には適用していない(タスクの「追加」のみバックエンド側でログする)
