import { useI18n } from "../i18n/useI18n";

interface ErrorPageProps {
  code: string | null;
}

export function ErrorPage({ code }: ErrorPageProps) {
  const { t } = useI18n();

  return (
    <main>
      <h1>{t(`errors.${code ?? "unknown_error"}`)}</h1>
    </main>
  );
}
