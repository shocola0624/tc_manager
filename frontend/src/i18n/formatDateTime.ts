import type { Locale } from "./resolveLocale";

const BCP47_TAGS: Record<Locale, string> = { ja: "ja-JP" };

// サークルの活動は物理的に日本国内で行われる前提のため、閲覧者のブラウザの
// ローカルタイムゾーンに関わらず常に日本時間で表示する。
const TIME_ZONES: Record<Locale, string> = { ja: "Asia/Tokyo" };

const DEFAULT_OPTIONS: Intl.DateTimeFormatOptions = {
  dateStyle: "medium",
  timeStyle: "short",
};

/**
 * ISO 8601(保存形式)を画面表示用に整形する。日付整形をハードコードせず、
 * 必ず Intl.DateTimeFormat 経由でロケールを渡す(CLAUDE.md §7)。
 */
export function formatDateTime(
  iso: string,
  locale: Locale,
  options: Intl.DateTimeFormatOptions = DEFAULT_OPTIONS,
): string {
  const date = new Date(iso);
  const resolvedOptions: Intl.DateTimeFormatOptions = {
    timeZone: TIME_ZONES[locale],
    ...options,
  };
  return new Intl.DateTimeFormat(BCP47_TAGS[locale] ?? locale, resolvedOptions).format(date);
}
