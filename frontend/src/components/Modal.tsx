import { useEffect, type ReactNode } from "react";
import { useI18n } from "../i18n/useI18n";
import styles from "./Modal.module.css";

interface ModalProps {
  title: string;
  onClose: () => void;
  children: ReactNode;
}

/** 中央配置の小さいダイアログ(screen-reference.dc(1).html の持ち物登録モーダル)。
 * 背景クリックと Escape で閉じる。フォームの実体は呼び出し側が children で渡す。 */
export function Modal({ title, onClose, children }: ModalProps) {
  const { t } = useI18n();

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div className={styles.backdrop} onClick={onClose}>
      <div className={styles.dialog} onClick={(event) => event.stopPropagation()}>
        <div className={styles.header}>
          <span className={styles.title}>{title}</span>
          <button type="button" className={styles.close} onClick={onClose} aria-label={t("common.close")}>
            ×
          </button>
        </div>
        <div className={styles.body}>{children}</div>
      </div>
    </div>
  );
}
