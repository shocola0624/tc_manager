// 対応ロケール一覧。将来言語を追加するときはここに 1 件足すだけでよい。
export const SUPPORTED_LOCALES = ["ja"] as const;
export type Locale = (typeof SUPPORTED_LOCALES)[number];

const DEFAULT_LOCALE: Locale = "ja";

function isSupportedLocale(value: string): value is Locale {
  return (SUPPORTED_LOCALES as readonly string[]).includes(value);
}

function primaryTag(tag: string): string {
  return tag.split("-")[0]?.toLowerCase() ?? "";
}

/**
 * ロケール解決順序(CLAUDE.md §7): users.locale -> Accept-Language(ブラウザ) -> 既定 ja
 */
export function resolveLocale(
  userLocale: string | null | undefined,
  browserLanguages: readonly string[] = [],
): Locale {
  if (userLocale) {
    const primary = primaryTag(userLocale);
    if (isSupportedLocale(primary)) {
      return primary;
    }
  }

  for (const lang of browserLanguages) {
    const primary = primaryTag(lang);
    if (isSupportedLocale(primary)) {
      return primary;
    }
  }

  return DEFAULT_LOCALE;
}
