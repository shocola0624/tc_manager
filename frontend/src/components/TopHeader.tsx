import { Link, useLocation } from "react-router-dom";
import iconUrl from "../assets/icon.jpg";
import { useI18n } from "../i18n/useI18n";
import { AccountMenu } from "./AccountMenu";
import styles from "./TopHeader.module.css";

/**
 * ワードマーク＋ナビゲーション＋アバターの上部ヘッダー(全画面で表示)。ワードマークは
 * ホームへのリンクを兼ね、活動日・持ち物のテキストリンクでどの画面からも直接遷移できる。
 */
export function TopHeader() {
  const { t } = useI18n();
  const location = useLocation();

  return (
    <header className={styles.header}>
      <div className={styles.leftGroup}>
        <Link to="/" className={styles.brand}>
          <img src={iconUrl} alt="" className={styles.brandIcon} />
          <span className={styles.wordmark}>{t("app.wordmark")}</span>
        </Link>
        <nav className={styles.nav}>
          <Link
            to="/activities"
            className={styles.navButton}
            aria-current={location.pathname === "/activities" ? "page" : undefined}
          >
            {t("nav.activities")}
          </Link>
          <Link
            to="/items"
            className={styles.navButton}
            aria-current={location.pathname === "/items" ? "page" : undefined}
          >
            {t("nav.items")}
          </Link>
          <Link
            to="/tasks"
            className={styles.navButton}
            aria-current={location.pathname === "/tasks" ? "page" : undefined}
          >
            {t("nav.tasks")}
          </Link>
          <Link
            to="/calendar"
            className={styles.navButton}
            aria-current={location.pathname === "/calendar" ? "page" : undefined}
          >
            {t("nav.calendar")}
          </Link>
        </nav>
      </div>
      <AccountMenu />
    </header>
  );
}
