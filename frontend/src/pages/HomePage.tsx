import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  useCurrentAssignments,
  useCurrentWindowActivities,
  useCurrentWindowAttendance,
  useItems,
  useSetAttendance,
} from "../api/hooks";
import type { AttendanceStatus } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
import { isUpcoming } from "../activities/dateTime";
import { Button } from "../components/Button";
import { useI18n } from "../i18n/useI18n";
import styles from "./HomePage.module.css";

/** 活動日・持ち物へ遷移する四角いアイコンボタン(下部タブバーの代わり)。 */
function NavTiles() {
  const { t } = useI18n();
  return (
    <div className={styles.navTiles}>
      <Link to="/activities" className={styles.navTile}>
        <svg
          className={styles.navTileIcon}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.6}
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <rect x="4" y="5" width="16" height="15" rx="2" />
          <path d="M4 9.5h16" />
          <path d="M8 3v4M16 3v4" />
        </svg>
        <span className={styles.navTileLabel}>{t("nav.activities")}</span>
      </Link>
      <Link to="/items" className={styles.navTile}>
        <svg
          className={styles.navTileIcon}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.6}
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M4 8l8-4 8 4-8 4-8-4z" />
          <path d="M4 8v8l8 4 8-4V8" />
          <path d="M12 12v8" />
        </svg>
        <span className={styles.navTileLabel}>{t("nav.items")}</span>
      </Link>
    </div>
  );
}

/**
 * ログイン直後に開く画面。直近の活動1件についてのみ「出欠を回答したか」
 * 「持っていく器具は何か」を表示する(screen-reference.dc.html 画面1)。
 * 過去の活動や他人の状況はここでは扱わない。
 */
export function HomePage() {
  const { t, formatDateTime } = useI18n();
  const { user } = useAuth();
  // 直近の活動1件しか使わないため、全件取得ではなく軽量版(CLAUDE.md §9)を使う。
  const activitiesQuery = useCurrentWindowActivities();
  const attendanceQuery = useCurrentWindowAttendance();
  const assignmentsQuery = useCurrentAssignments();
  const itemsQuery = useItems();
  const setAttendance = useSetAttendance();

  const [isChangingAnswer, setIsChangingAnswer] = useState(false);

  const nextActivity = useMemo(() => {
    const now = new Date();
    return (activitiesQuery.data?.data ?? [])
      .filter((activity) => activity.is_active && isUpcoming(activity.starts_at, activity.duration_min, now))
      .sort((a, b) => a.starts_at.localeCompare(b.starts_at))[0] ?? null;
  }, [activitiesQuery.data]);

  useEffect(() => {
    setIsChangingAnswer(false);
  }, [nextActivity?.activity_id]);

  const myAttendance = useMemo(() => {
    if (!nextActivity || !user) return undefined;
    return (attendanceQuery.data?.data ?? []).find(
      (row) => row.activity_id === nextActivity.activity_id && row.discord_user_id === user.discord_user_id,
    );
  }, [attendanceQuery.data, nextActivity, user]);

  const myItemNames = useMemo(() => {
    if (!nextActivity || !user) return [];
    const itemsById = new Map((itemsQuery.data?.data ?? []).map((item) => [item.item_id, item]));
    return (assignmentsQuery.data ?? [])
      .filter(
        (slot) => slot.activity_id === nextActivity.activity_id && slot.assignee_id === user.discord_user_id,
      )
      .map((slot) => (slot.item_id ? (itemsById.get(slot.item_id)?.name ?? slot.item_id) : (slot.custom_name ?? "")));
  }, [assignmentsQuery.data, itemsQuery.data, nextActivity, user]);

  if (
    activitiesQuery.isPending ||
    attendanceQuery.isPending ||
    assignmentsQuery.isPending ||
    itemsQuery.isPending ||
    !user
  ) {
    return <p>{t("common.loading")}</p>;
  }

  if (!nextActivity) {
    return (
      <main>
        <div className={styles.hero} />
        <p className={styles.empty}>{t("home.noUpcoming")}</p>
        <NavTiles />
      </main>
    );
  }

  function handleSet(status: AttendanceStatus) {
    if (!nextActivity) return;
    setAttendance.mutate(
      { activityId: nextActivity.activity_id, status },
      { onSuccess: () => setIsChangingAnswer(false) },
    );
  }

  const status = myAttendance?.status ?? "undecided";
  const showRsvpButtons = isChangingAnswer || status === "undecided";

  return (
    <main>
      <div className={styles.hero} />
      <div className={styles.card}>
        <div className={styles.cardHeaderRow}>
          <span className={styles.cardLabel}>{t("home.nextActivityLabel")}</span>
          <span className={styles.dateTime}>
            {formatDateTime(nextActivity.starts_at, { month: "numeric", day: "numeric", weekday: "short" })}{" "}
            {formatDateTime(nextActivity.starts_at, { hour: "2-digit", minute: "2-digit", hourCycle: "h23" })}
          </span>
        </div>
        {nextActivity.location && <div className={styles.location}>{nextActivity.location}</div>}
        <h1 className={styles.title}>
          <Link to={`/activities/${nextActivity.activity_id}`} className={styles.titleLink}>
            {nextActivity.title}
          </Link>
        </h1>
        {nextActivity.description && <p className={styles.description}>{nextActivity.description}</p>}

        {showRsvpButtons ? (
          <>
            <div className={styles.statusRow}>
              <span className={`${styles.dot} ${styles.dotWarn}`} aria-hidden="true" />
              <span className={styles.statusText}>{t("home.unanswered")}</span>
            </div>
            <div className={styles.actions}>
              <Button variant="primary" disabled={setAttendance.isPending} onClick={() => handleSet("attending")}>
                {t("home.rsvpAttend")}
              </Button>
              <Button variant="secondary" disabled={setAttendance.isPending} onClick={() => handleSet("absent")}>
                {t("home.rsvpAbsent")}
              </Button>
            </div>
          </>
        ) : status === "attending" ? (
          <>
            <div className={styles.statusRow}>
              <span className={`${styles.dot} ${styles.dotPositive}`} aria-hidden="true" />
              <span className={styles.statusText}>{t("home.attendingAnswered")}</span>
            </div>
            {myItemNames.length > 0 && (
              <div className={styles.itemRow}>
                {t("home.yourItem")}: {myItemNames.join("、")}
              </div>
            )}
            <div className={styles.actions}>
              <Button variant="secondary" onClick={() => setIsChangingAnswer(true)}>
                {t("home.changeAnswer")}
              </Button>
            </div>
          </>
        ) : (
          <>
            <div className={styles.statusRow}>
              <span className={`${styles.dot} ${styles.dotMuted}`} aria-hidden="true" />
              <span className={styles.statusText}>{t("home.absentAnswered")}</span>
            </div>
            <div className={styles.actions}>
              <Button variant="secondary" onClick={() => setIsChangingAnswer(true)}>
                {t("home.changeAnswer")}
              </Button>
            </div>
          </>
        )}
      </div>

      <NavTiles />
    </main>
  );
}
