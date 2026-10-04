import { Link } from "react-router-dom";
import iconUrl from "../assets/icon.jpg";
import { useI18n } from "../i18n/useI18n";
import { AccountMenu } from "./AccountMenu";
import styles from "./TopHeader.module.css";

/** ワードマーク＋アバターの上部ヘッダー(全画面で表示)。ワードマークはホームへのリンクを兼ねる。 */
export function TopHeader() {
  const { t } = useI18n();

  return (
    <header className={styles.header}>
      <Link to="/" className={styles.brand}>
        <img src={iconUrl} alt="" className={styles.brandIcon} />
        <span className={styles.wordmark}>{t("app.wordmark")}</span>
      </Link>
      <AccountMenu />
    </header>
  );
}
