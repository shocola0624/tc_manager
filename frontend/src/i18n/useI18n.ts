import { useMemo } from "react";
import { useAuth } from "../auth/AuthProvider";
import { formatDateTime as formatDateTimeForLocale } from "./formatDateTime";
import { resolveLocale } from "./resolveLocale";
import { createTranslator } from "./t";

/**
 * ロケール解決(users.locale -> Accept-Language -> ja)と t() / formatDateTime を
 * まとめて提供するフック。AuthProvider の内側で使うこと。
 */
export function useI18n() {
  const { user } = useAuth();

  const locale = useMemo(
    () => resolveLocale(user?.locale ?? null, navigator.languages),
    [user?.locale],
  );

  const t = useMemo(() => createTranslator(locale), [locale]);

  const formatDateTime = useMemo(
    () =>
      (iso: string, options?: Intl.DateTimeFormatOptions) =>
        formatDateTimeForLocale(iso, locale, options),
    [locale],
  );

  return { locale, t, formatDateTime };
}
