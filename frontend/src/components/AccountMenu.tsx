import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { authApi } from "../api/endpoints";
import { useAuth } from "../auth/AuthProvider";
import { useI18n } from "../i18n/useI18n";
import styles from "./AccountMenu.module.css";
import { PersonIcon } from "./icons";

/**
 * ヘッダーのアバターを押すと開くメニュー。プロフィールとログアウトの入り口。
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
        <PersonIcon className={styles.avatarIcon} />
      </button>
      {isOpen && (
        <div className={styles.menu} role="menu">
          <div className={styles.menuHeader}>{user?.name}</div>
          <Link to="/profile" role="menuitem" className={styles.menuItem} onClick={() => setIsOpen(false)}>
            {t("profile.menuLabel")}
          </Link>
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
