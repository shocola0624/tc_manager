# Techspresso for Students

コーヒーサークルの「ユーザー / 持ち物 / 活動日 / 出欠 / 器具割り当て」を管理する Web アプリ。

- **バックエンド**: FastAPI (Python)
- **フロントエンド**: React + TypeScript (Vite)
- **データストア**: Google スプレッドシート(Sheets API v4)— アプリではなく**シートがデータの正**
- **認証・通知**: Discord OAuth2 ログイン、Discord Interactions(HTTP Webhook、Gateway/WebSocket は不使用)

設計方針・データモデル・アーキテクチャ上の制約は [`CLAUDE.md`](./CLAUDE.md) に集約している。実装で迷ったら常にそこへ戻ること。

## 構成

```
backend/    FastAPI アプリ本体。セットアップ手順は backend/README.md
frontend/   React + TypeScript(Vite)フロントエンド。セットアップ手順は frontend/README.md
CLAUDE.md   設計原則・データモデル・アーキテクチャ制約(このリポジトリの一次資料)
```

各ディレクトリの README に、環境変数・Discord アプリ設定・テスト実行方法などの詳細を置いている。

- [backend/README.md](./backend/README.md) — Google Sheets / Discord OAuth2・Bot / Interactions エンドポイントの設定、起動・テスト方法
- [frontend/README.md](./frontend/README.md) — セットアップ、テスト・型チェック・Lint、ディレクトリ構成と規約

## クイックスタート

バックエンドとフロントエンドを別ターミナルでそれぞれ起動する(バックエンドを先に)。

```bash
# ターミナル1: バックエンド
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # Google Sheets / Discord の各値を埋める(backend/README.md 参照)
uvicorn main:app --reload --port 8000
```

```bash
# ターミナル2: フロントエンド
cd frontend
npm install
cp .env.example .env
npm run dev
```

`http://localhost:5173` で開く。Discord の出欠ボタン(Interactions)をローカルで検証する場合は、[backend/README.md の「ローカルでの動作確認」](./backend/README.md#ローカルでの動作確認interactions-エンドポイント)を参照してトンネリングすること。

## テスト

```bash
# バックエンド
cd backend && python -m pytest

# フロントエンド
cd frontend && npm test && npx tsc -b && npm run lint && npm run build
```
