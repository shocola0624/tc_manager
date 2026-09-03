import { Outlet, useLocation } from "react-router-dom";
import { TopHeader } from "./TopHeader";

/**
 * ログイン済みエリア共通のレイアウト。ホーム画面(パス "/")でのみ上部ヘッダー
 * (ワードマーク＋アバター)を表示する。それ以外の画面(活動一覧・持ち物一覧・
 * 活動詳細・器具の選択)は、ホームの四角いアイコンや戻る矢印から遷移するプッシュ画面
 * として扱い、各ページ自身が DetailHeader(戻る矢印)を描画する。
 */
export function AppLayout() {
  const location = useLocation();
  const isHome = location.pathname === "/";

  return (
    <>
      {isHome && <TopHeader />}
      <Outlet />
    </>
  );
}
