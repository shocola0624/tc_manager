import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useActivities, useTasks } from "../api/hooks";
import type { Task } from "../api/types";
import { DetailHeader } from "../components/DetailHeader";
import { useI18n } from "../i18n/useI18n";
import { useUserDirectory } from "../users/useUserDirectory";
import { activityToEvent, taskToEvent } from "./eventSources";
import { addMonths, dateKey, getMonthGrid, jstDateKeyFromIso, type MonthCursor } from "./monthGrid";
import type { CalendarEvent } from "./types";
import styles from "./CalendarPage.module.css";

const WEEKDAY_KEYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"] as const;
const MAX_VISIBLE_PER_DAY = 3;

function thisMonthCursor(): MonthCursor {
  const now = new Date();
  return { year: now.getFullYear(), month: now.getMonth() };
}

interface TaskEventPillProps {
  task: Task;
  kind: "task" | "task_done";
  nameById: Map<string, string>;
}

/** タスクのイベント。クリック、またはPCではカーソルを合わせるだけで説明・担当者を
 * 吹き出し表示する(タスクには活動のような個別詳細画面がまだ無いため)。 */
function TaskEventPill({ task, kind, nameById }: TaskEventPillProps) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleOutsideClick(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleOutsideClick);
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, [open]);

  const assigneeNames = task.assignees.map((assignee) =>
    assignee.member_id ? (nameById.get(assignee.member_id) ?? assignee.member_id) : assignee.label,
  );

  return (
    <div
      ref={containerRef}
      className={styles.eventPillWrapper}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        className={`${styles.eventPill} ${styles[`eventPill_${kind}`]}`}
        onClick={() => setOpen(true)}
      >
        {task.title}
      </button>
      {open && (
        <div className={styles.eventPopover} role="tooltip">
          <div className={styles.eventPopoverTitle}>{task.title}</div>
          <p className={styles.eventPopoverDescription}>{task.description || t("calendar.noDescription")}</p>
          <p className={styles.eventPopoverAssignees}>
            {t("tasks.formAssignees")}: {assigneeNames.length > 0 ? assigneeNames.join("、") : t("tasks.assigneesEmpty")}
          </p>
        </div>
      )}
    </div>
  );
}

/**
 * カレンダー月表示。活動日・タスク期限を同じ面に出す。イベントの取得元は
 * eventSources.ts の変換関数だけが知っていて、このコンポーネントは
 * CalendarEvent(source/source_id/title/starts_at/ends_at/kind)だけを見る
 * (新しいイベント種別を足してもここは変更不要)。タスクの吹き出し表示だけは
 * source_id から元の Task を引き直して説明・担当者を補う。
 */
export function CalendarPage() {
  const { t, formatDateTime } = useI18n();
  const activitiesQuery = useActivities();
  const tasksQuery = useTasks();
  const { nameById, isPending: usersPending } = useUserDirectory();
  const [cursor, setCursor] = useState<MonthCursor>(thisMonthCursor);

  const activeTasks = useMemo(
    () => (tasksQuery.data?.data ?? []).filter((task) => task.is_active),
    [tasksQuery.data],
  );
  const tasksById = useMemo(() => new Map(activeTasks.map((task) => [task.task_id, task])), [activeTasks]);

  const events = useMemo<CalendarEvent[]>(() => {
    const activityEvents = (activitiesQuery.data?.data ?? [])
      .filter((activity) => activity.is_active)
      .map(activityToEvent);
    const taskEvents = activeTasks.map(taskToEvent);
    return [...activityEvents, ...taskEvents];
  }, [activitiesQuery.data, activeTasks]);

  const eventsByDate = useMemo(() => {
    const map = new Map<string, CalendarEvent[]>();
    for (const event of events) {
      const key = jstDateKeyFromIso(event.starts_at);
      const list = map.get(key) ?? [];
      list.push(event);
      map.set(key, list);
    }
    for (const list of map.values()) {
      list.sort((a, b) => a.starts_at.localeCompare(b.starts_at));
    }
    return map;
  }, [events]);

  if (activitiesQuery.isPending || tasksQuery.isPending || usersPending) {
    return <p>{t("common.loading")}</p>;
  }

  const days = getMonthGrid(cursor);
  const monthLabelIso = `${cursor.year}-${String(cursor.month + 1).padStart(2, "0")}-01T12:00:00+09:00`;
  const todayKey = dateKey(new Date());

  return (
    <>
      <DetailHeader label={t("calendar.title")} fallbackTo="/" />
      <main>
        <div className={styles.toolbar}>
          <button
            type="button"
            className={styles.navButton}
            onClick={() => setCursor((current) => addMonths(current, -1))}
            aria-label={t("calendar.prevMonth")}
          >
            ←
          </button>
          <span className={styles.monthLabel}>
            {formatDateTime(monthLabelIso, { year: "numeric", month: "long" })}
          </span>
          <button
            type="button"
            className={styles.navButton}
            onClick={() => setCursor((current) => addMonths(current, 1))}
            aria-label={t("calendar.nextMonth")}
          >
            →
          </button>
        </div>

        <div className={styles.legend}>
          <span className={styles.legendItem}>
            <span className={`${styles.dot} ${styles.dot_activity}`} />
            {t("calendar.legendActivity")}
          </span>
          <span className={styles.legendItem}>
            <span className={`${styles.dot} ${styles.dot_task}`} />
            {t("calendar.legendTask")}
          </span>
          <span className={styles.legendItem}>
            <span className={`${styles.dot} ${styles.dot_task_done}`} />
            {t("calendar.legendTaskDone")}
          </span>
        </div>

        <div className={styles.weekdayRow}>
          {WEEKDAY_KEYS.map((key) => (
            <div key={key} className={styles.weekdayCell}>
              {t(`calendar.weekday.${key}`)}
            </div>
          ))}
        </div>

        <div className={styles.grid}>
          {days.map((day) => {
            const key = dateKey(day);
            const isCurrentMonth = day.getMonth() === cursor.month;
            const dayEvents = eventsByDate.get(key) ?? [];
            const visible = dayEvents.slice(0, MAX_VISIBLE_PER_DAY);
            const overflow = dayEvents.length - visible.length;
            return (
              <div
                key={key}
                className={[
                  styles.dayCell,
                  isCurrentMonth ? "" : styles.dayCellOutside,
                  key === todayKey ? styles.dayCellToday : "",
                ].join(" ")}
              >
                <div className={styles.dayNumber}>{day.getDate()}</div>
                <div className={styles.eventList}>
                  {visible.map((event) => {
                    if (event.source === "activity") {
                      return (
                        <Link
                          key={`${event.source}-${event.source_id}`}
                          to={`/activities/${event.source_id}`}
                          className={`${styles.eventPill} ${styles[`eventPill_${event.kind}`]}`}
                          title={event.title}
                        >
                          {event.title}
                        </Link>
                      );
                    }
                    const task = tasksById.get(event.source_id);
                    if (!task) return null;
                    return (
                      <TaskEventPill
                        key={`${event.source}-${event.source_id}`}
                        task={task}
                        kind={event.kind as "task" | "task_done"}
                        nameById={nameById}
                      />
                    );
                  })}
                  {overflow > 0 && (
                    <span className={styles.overflow}>{t("calendar.moreEvents", { count: overflow })}</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </main>
    </>
  );
}
