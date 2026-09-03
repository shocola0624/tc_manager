import iconUrl from "../assets/icon.jpg";
import { useI18n } from "../i18n/useI18n";
import { AccountMenu } from "./AccountMenu";
import styles from "./TopHeader.module.css";

/** ワードマーク＋アバターの上部ヘッダー(タブのルート画面のみ表示、screen-reference.dc.html 画面1)。 */
export function TopHeader() {
  const { t } = useI18n();

  return (
    <header className={styles.header}>
      <span className={styles.brand}>
        <img src={iconUrl} alt="" className={styles.brandIcon} />
        <span className={styles.wordmark}>{t("app.wordmark")}</span>
      </span>
      <AccountMenu />
    </header>
  );
}
