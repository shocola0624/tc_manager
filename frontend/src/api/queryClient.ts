import { QueryClient } from "@tanstack/react-query";

/**
 * CLAUDE.md §3 の方針(ブラウザ側キャッシュ・起動時取得・書き込み成功時とリロード時のみ更新・
 * ポーリング/リアルタイム同期はしない)をそのまま体現する設定。
 *
 * 自動再取得をすべて切っているため、一度取得したデータは明示的に invalidateQueries を
 * 呼ぶまで裏で再取得されない。
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: Infinity,
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
      refetchOnMount: false,
      retry: 1,
    },
  },
});

/**
 * 明示的な「再読み込み」操作から呼ぶ規約。
 * 書き込み成功時は各 mutation 側で該当 queryKey だけを invalidateQueries すること
 * (全体無効化はしない)。
 */
export function refreshAll(): Promise<void> {
  return queryClient.invalidateQueries();
}
