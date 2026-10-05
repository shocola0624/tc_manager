import { useMemo, useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { ApiError } from "../api/client";
import { authApi } from "../api/endpoints";
import { useAttendance, useItems } from "../api/hooks";
import type { Category, CurrentUser } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
import { Button } from "../components/Button";
import { DetailHeader } from "../components/DetailHeader";
import { useI18n } from "../i18n/useI18n";
import styles from "./ProfilePage.module.css";

const CATEGORIES: Category[] = [
  "dripper",
  "grinder",
  "scale",
  "kettle",
  "pot",
  "scoop",
  "thermometer",
  "server",
  "other",
];

/** 自分のアカウント情報を表示・編集する画面(ヘッダーのアバターメニューから遷移)。 */
export function ProfilePage() {
  const { t } = useI18n();
  const { user, refetch } = useAuth();
  const attendanceQuery = useAttendance();
  const itemsQuery = useItems();

  const [name, setName] = useState(user?.name ?? "");
  const [grade, setGrade] = useState(user?.grade ?? "");

  const updateProfile = useMutation<CurrentUser, ApiError, { name: string; grade: string }>({
    mutationFn: (payload) => authApi.updateProfile(payload),
    onSuccess: () => refetch(),
  });

  const attendingCount = useMemo(() => {
    if (!user) return 0;
    return (attendanceQuery.data?.data ?? []).filter(
      (row) => row.discord_user_id === user.discord_user_id && row.status === "attending",
    ).length;
  }, [attendanceQuery.data, user]);

  const myItems = useMemo(() => {
    if (!user) return [];
    return (itemsQuery.data?.data ?? []).filter(
      (item) => item.owner_id === user.discord_user_id && item.is_active,
    );
  }, [itemsQuery.data, user]);

  const categoryCounts = useMemo(() => {
    const counts = new Map<Category, number>();
    for (const item of myItems) {
      counts.set(item.category, (counts.get(item.category) ?? 0) + 1);
    }
    return counts;
  }, [myItems]);

  if (!user || attendanceQuery.isPending || itemsQuery.isPending) {
    return <p>{t("common.loading")}</p>;
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    updateProfile.mutate({ name, grade });
  }

  return (
    <>
      <DetailHeader label={t("profile.title")} fallbackTo="/" />
      <main>
        <form className={styles.form} onSubmit={handleSubmit}>
          <div className={styles.fieldStack}>
            <label className={styles.field}>
              <span className={styles.fieldLabel}>{t("profile.nameLabel")}</span>
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                required
                minLength={1}
                maxLength={100}
              />
            </label>
            <label className={styles.field}>
              <span className={styles.fieldLabel}>{t("profile.gradeLabel")}</span>
              <input
                value={grade}
                onChange={(event) => setGrade(event.target.value)}
                placeholder={t("profile.gradePlaceholder")}
                maxLength={20}
              />
            </label>
          </div>

          <div className={styles.saveRow}>
            {updateProfile.isError && (
              <span className={styles.errorText} role="alert">
                {t(`errors.${updateProfile.error.code}`)}
              </span>
            )}
            {updateProfile.isSuccess && !updateProfile.isPending && (
              <span className={styles.successText}>{t("profile.saveSuccess")}</span>
            )}
            <Button type="submit" variant="primary" disabled={updateProfile.isPending}>
              {updateProfile.isPending ? t("profile.saving") : t("profile.saveButton")}
            </Button>
          </div>

          <div className={styles.statsRow}>
            <div className={styles.statCell}>
              <span className={styles.fieldLabel}>{t("profile.attendanceCountLabel")}</span>
              <div className={styles.statValue}>
                {attendingCount}
                <span className={styles.statUnit}>{t("profile.attendanceCountUnit")}</span>
              </div>
            </div>
            <div className={styles.statCell}>
              <span className={styles.fieldLabel}>{t("profile.itemsCountLabel")}</span>
              <div className={styles.statValue}>
                {myItems.length}
                <span className={styles.statUnit}>{t("profile.itemsCountUnit")}</span>
              </div>
            </div>
          </div>

          <div className={styles.categoriesHeaderRow}>
            <span className={styles.sectionTitle}>{t("profile.categoriesTitle")}</span>
            <div className={styles.legend}>
              <span className={styles.legendItem}>
                <span className={`${styles.legendDot} ${styles.legendDotPositive}`} />
                {t("profile.categoryLegendRegistered")}
              </span>
              <span className={styles.legendItem}>
                <span className={`${styles.legendDot} ${styles.legendDotMuted}`} />
                {t("profile.categoryLegendUnregistered")}
              </span>
            </div>
          </div>
          <div className={styles.categoryChips}>
            {CATEGORIES.map((category) => {
              const count = categoryCounts.get(category) ?? 0;
              return (
                <span
                  key={category}
                  className={`${styles.categoryChip} ${count > 0 ? styles.categoryChipActive : ""}`}
                >
                  {t(`categories.${category}`)}
                  {count > 0 && <b className={styles.categoryChipCount}>{count}</b>}
                </span>
              );
            })}
          </div>
        </form>
      </main>
    </>
  );
}
