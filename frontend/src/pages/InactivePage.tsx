import { useI18n } from "../i18n/useI18n";

export function InactivePage() {
  const { t } = useI18n();

  return (
    <main>
      <h1>{t("auth.inactiveTitle")}</h1>
      <p>{t("auth.inactiveDescription")}</p>
    </main>
  );
}
