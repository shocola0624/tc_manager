# Techspresso for Students — フロントエンド

React + TypeScript(Vite)。設計方針はリポジトリルートの `CLAUDE.md` を参照。

## セットアップ

```bash
cd frontend
npm install
cp .env.example .env   # 必要なら VITE_API_BASE_URL をバックエンドの URL に合わせて変更
npm run dev
```

バックエンド(`../backend`)を先に起動しておくこと。

## テスト・型チェック・Lint

```bash
npm test       # Vitest(i18n・API クライアントなど純粋ロジックの単体テスト)
npx tsc -b     # 型チェック
npm run lint   # ESLint
```

## ディレクトリ

```
src/
  api/        API クライアント・型定義・TanStack Query フック
  auth/       認証状態(AuthProvider)
  i18n/       t() / ロケール解決 / 日付整形
  components/ 画面をまたいで使う共通コンポーネント
  pages/      ログイン・登録・無効ユーザー・エラー・ホームの各画面
  router.tsx  認証状態に応じたルーティング
```

## 規約

- **表示文字列は必ず `useI18n().t()` を経由する。** 日本語のハードコードは書かない(`src/i18n/locales/ja.json` に追記する)
- **日時の表示整形は `useI18n().formatDateTime()` を使う。** ISO 8601(保存形式)をそのまま画面に出さない
- **ブラウザキャッシュは TanStack Query(`src/api/queryClient.ts`)に一本化する。** 自動再取得は既定で無効化しているため、書き込み成功時は該当する `queryKey` を `invalidateQueries`、明示的な再読み込み操作では `refreshAll()` を呼ぶ
- **一覧系のレスポンスは `ListResponse<T>` 形式。** `invalid_rows` が含まれる場合は `components/InvalidRowsWarning` で表示する
