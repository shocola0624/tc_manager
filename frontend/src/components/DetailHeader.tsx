import { useNavigate } from "react-router-dom";
import styles from "./DetailHeader.module.css";

interface DetailHeaderProps {
  label: string;
  fallbackTo: string;
}

/** 戻る矢印＋ラベルのヘッダー(プッシュ画面用、screen-reference.dc.html 画面2/3)。 */
export function DetailHeader({ label, fallbackTo }: DetailHeaderProps) {
  const navigate = useNavigate();

  function handleBack() {
    if (window.history.length > 1) {
      navigate(-1);
    } else {
      navigate(fallbackTo);
    }
  }

  return (
    <header className={styles.header}>
      <button type="button" className={styles.back} onClick={handleBack} aria-label={label}>
        ←
      </button>
      <span className={styles.label}>{label}</span>
    </header>
  );
}
