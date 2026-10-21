import { webcrypto } from "node:crypto";

// Vitest の Node 実行環境では(Workers の実行環境=workerd と違って)グローバルの
// `crypto` が自動では露出しないことがあるため、テスト実行時だけ明示的に補う。
// プロダクションコード(googleAuth.ts)側は Workers のグローバル `crypto` を
// 前提にしたままで変更しない。
if (typeof globalThis.crypto === "undefined") {
  Object.defineProperty(globalThis, "crypto", { value: webcrypto, configurable: true });
}
