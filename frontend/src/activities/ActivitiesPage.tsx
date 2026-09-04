import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useActivities, useAttendance } from "../api/hooks";
import { useAuth } from "../auth/AuthProvider";
import { Button } from "../components/Button";
import { DetailHeader } from "../components/DetailHeader";
import { InvalidRowsWarning } from "../components/InvalidRowsWarning";
import { Modal } from "../components/Modal";
import { useI18n } from "../i18n/useI18n";
import { useUserDirectory } from "../users/useUserDirectory";
import { ActivityForm } from "./ActivityForm";
import styles from "./ActivitiesPage.module.css";
import { computeEndTimeIso, isUpcoming } from "./dateTime";
import { canManageActivities } from "./permissions";

type Tab = "upcoming" | "past";

/** 活動日一覧。各行から活動詳細画面(出欠・器具の準備状況)へ遷移する。 */
export function ActivitiesPage() {
  const { t, formatDateTime } = useI18n();
  const { user } = useAuth();
  const activitiesQuery = useActivities();
  const attendanceQuery = useAttendance();
  const { activeUsers, isPending: usersPending } = useUserDirectory();

  const [tab, setTab] = useState<Tab>("upcoming");
  const [showCreateModal, setShowCreateModal] = useState(false);

  // 削除(is_active=FALSE)された活動は一覧からは常に除く。
  const activeActivities = useMemo(
    () => (activitiesQuery.data?.data ?? []).filter((activity) => activity.is_active),
    [activitiesQuery.data],
  );

  const visibleActivities = useMemo(() => {
    const now = new Date();
    return activeActivities
      .filter((activity) =>
        tab === "upcoming"
          ? isUpcoming(activity.starts_at, activity.duration_min, now)
          : !isUpcoming(activity.starts_at, activity.duration_min, now),
      )
      .sort((a, b) => a.starts_at.localeCompare(b.starts_at));
  }, [activeActivities, tab]);

  // 活動別の出席予定人数(CLAUDE.md §3: キャッシュ済みデータをクライアント側で集計)。
  const attendingCountByActivityId = useMemo(() => {
    const counts = new Map<string, number>();
    for (const row of attendanceQuery.data?.data ?? []) {
      if (row.status !== "attending") continue;
      counts.set(row.activity_id, (counts.get(row.activity_id) ?? 0) + 1);
    }
    return counts;
  }, [attendanceQuery.data]);

  if (activitiesQuery.isPending || attendanceQuery.isPending || usersPending) {
    return <p>{t("common.loading")}</p>;
  }

  if (!user) {
    return null;
  }

  const canManage = canManageActivities(user);

  return (
    <>
      <DetailHeader label={t("activities.title")} fallbackTo="/" />
      <main>
        {activitiesQuery.data && <InvalidRowsWarning invalidRows={activitiesQuery.data.invalid_rows} />}

        <nav className={styles.tabs}>
          <button
            type="button"
            className={`${styles.tab} ${tab === "upcoming" ? styles.tabActive : ""}`}
            onClick={() => setTab("upcoming")}
          >
            {t("activities.tabUpcoming")}
          </button>
          <button
            type="button"
            className={`${styles.tab} ${tab === "past" ? styles.tabActive : ""}`}
            onClick={() => setTab("past")}
          >
            {t("activities.tabPast")}
          </button>
        </nav>

        {canManage && (
          <div className={styles.createSection}>
            <Button variant="cta" onClick={() => setShowCreateModal(true)}>
              {t("activities.addButton")}
            </Button>
          </div>
        )}

        {visibleActivities.length === 0 ? (
          <p className={styles.empty}>{t("activities.emptyList")}</p>
        ) : (
          <ul className={styles.list}>
            {visibleActivities.map((activity) => (
              <li key={activity.activity_id}>
                <Link to={`/activities/${activity.activity_id}`} className={styles.row}>
                  <div className={styles.rowHeader}>
                    <div className={styles.dateTime}>
                      {formatDateTime(activity.starts_at, { month: "numeric", day: "numeric", weekday: "short" })}{" "}
                      {formatDateTime(activity.starts_at, { hour: "2-digit", minute: "2-digit", hourCycle: "h23" })}
                      {"–"}
                      {formatDateTime(computeEndTimeIso(activity.starts_at, activity.duration_min), {
                        hour: "2-digit",
                        minute: "2-digit",
                        hourCycle: "h23",
                      })}
                    </div>
                    <div className={styles.attendingCount}>
                      {t("activities.tallyAttending")}
                      <b>{attendingCountByActivityId.get(activity.activity_id) ?? 0}</b>
                    </div>
                  </div>
                  <div className={styles.title}>{activity.title}</div>
                  {activity.description && (
                    <div className={styles.description}>{activity.description}</div>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </main>

      {showCreateModal && (
        <Modal title={t("activities.modalAddTitle")} onClose={() => setShowCreateModal(false)}>
          <ActivityForm
            mode="create"
            currentUserId={user.discord_user_id}
            activeUsers={activeUsers}
            onDone={() => setShowCreateModal(false)}
          />
        </Modal>
      )}
    </>
  );
}
