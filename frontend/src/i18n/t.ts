import { locales } from "./locales";
import type { Locale } from "./resolveLocale";

type Params = Record<string, string | number>;

function lookup(dict: unknown, path: string[]): string | undefined {
  let node: unknown = dict;
  for (const segment of path) {
    if (typeof node !== "object" || node === null || !(segment in node)) {
      return undefined;
    }
    node = (node as Record<string, unknown>)[segment];
  }
  return typeof node === "string" ? node : undefined;
}

function interpolate(template: string, params?: Params): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (match, key: string) =>
    key in params ? String(params[key]) : match,
  );
}

export type Translate = (key: string, params?: Params) => string;

/**
 * ロケール1つに対する t() を作る。表示文字列は必ずこの関数を経由させ、
 * コード中に日本語をハードコードしない(CLAUDE.md §7)。
 */
export function createTranslator(locale: Locale): Translate {
  const dict = locales[locale] ?? locales.ja;
  return function t(key: string, params?: Params): string {
    const value = lookup(dict, key.split("."));
    if (value === undefined) {
      if (import.meta.env.DEV) {
        console.warn(`[i18n] missing translation key: ${key}`);
      }
      return key;
    }
    return interpolate(value, params);
  };
}
