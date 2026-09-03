import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { authApi } from "../api/endpoints";
import { useAuth } from "../auth/AuthProvider";
import { useI18n } from "../i18n/useI18n";
import styles from "./AccountMenu.module.css";

/**
 * ヘッダーのアバターを押すと開くメニュー。今はログアウトのみだが、将来ここに
 * プロフィール情報(menuHeader)や設定などの選択肢を足していく想定の入れ物として作る。
 * アバター自体はログアウトを兼ねない(誤操作防止のため、必ずメニューを経由させる)。
 */
export function AccountMenu() {
  const { t } = useI18n();
  const { user, refetch } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const logout = useMutation({
    mutationFn: authApi.logout,
    onSuccess: () => {
      setIsOpen(false);
      refetch();
    },
  });

  useEffect(() => {
    if (!isOpen) return;

    function handleOutsideClick(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    document.addEventListener("mousedown", handleOutsideClick);
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, [isOpen]);

  return (
    <div className={styles.container} ref={containerRef}>
      <button
        type="button"
        className={styles.avatar}
        onClick={() => setIsOpen((value) => !value)}
        aria-haspopup="menu"
        aria-expanded={isOpen}
        aria-label={user?.name ?? ""}
      >
        {user?.name.slice(0, 1) ?? ""}
      </button>
      {isOpen && (
        <div className={styles.menu} role="menu">
          <div className={styles.menuHeader}>{user?.name}</div>
          <button
            type="button"
            role="menuitem"
            className={styles.menuItem}
            onClick={() => logout.mutate()}
            disabled={logout.isPending}
          >
            {t("common.logout")}
          </button>
        </div>
      )}
    </div>
  );
}
