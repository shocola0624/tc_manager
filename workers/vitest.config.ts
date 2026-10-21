import { defineConfig } from "vitest/config";

// 実行環境(workerd)との差異が問題になるのは googleAuth.ts の SubtleCrypto 呼び出しだけで、
// Web Crypto は Node 18+ にも標準搭載されているため、単体テストは素の Node 環境で動かす
// (@cloudflare/vitest-pool-workers のような実行環境エミュレーションは導入しない)。
export default defineConfig({
  test: {
    environment: "node",
    setupFiles: ["./vitest.setup.ts"],
  },
});
