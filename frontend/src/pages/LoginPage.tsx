import { authApi } from "../api/endpoints";
import buttonStyles from "../components/Button.module.css";
import { useI18n } from "../i18n/useI18n";

export function LoginPage() {
  const { t } = useI18n();

  return (
    <main>
      <h1>{t("auth.loginTitle")}</h1>
      <p>{t("auth.loginDescription")}</p>
      {/* OAuth はリダイレクトを伴う実ナビゲーション。fetch では扱わない */}
      <a href={authApi.loginUrl()} className={`${buttonStyles.button} ${buttonStyles.primary}`}>
        {t("auth.loginButton")}
      </a>
    </main>
  );
}
