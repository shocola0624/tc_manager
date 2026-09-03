import type { Locale } from "../resolveLocale";
import ja from "./ja.json";

// 将来言語を追加するときは、辞書ファイルを足してここに 1 行加えるだけでよい。
export const locales: Record<Locale, typeof ja> = { ja };
export type TranslationDict = typeof ja;
