import { Outlet } from "react-router-dom";
import { TopHeader } from "./TopHeader";

/**
 * ログイン済みエリア共通のレイアウト。全画面で上部ヘッダー(ワードマーク＋アバター)を
 * 表示する。活動詳細・器具の選択などのプッシュ画面では、その下に各ページ自身が
 * DetailHeader(戻る矢印)を重ねて描画する。
 */
export function AppLayout() {
  return (
    <>
      <TopHeader />
      <Outlet />
    </>
  );
}
