import { computeEndTimeIso } from "../activities/dateTime";
import type { Activity, Task } from "../api/types";
import type { CalendarEvent } from "./types";

/** 活動日を CalendarEvent に変換する。 */
export function activityToEvent(activity: Activity): CalendarEvent {
  return {
    source: "activity",
    source_id: activity.activity_id,
    title: activity.title,
    starts_at: activity.starts_at,
    ends_at: computeEndTimeIso(activity.starts_at, activity.duration_min),
    kind: "activity",
  };
}

/** タスクを CalendarEvent に変換する。期限(due_at)を開始日時として扱う
 * (タスクに期間の概念はないため ends_at は持たない)。完了済みは kind を
 * 変えて薄色表示に回す(ユーザー要件)。 */
export function taskToEvent(task: Task): CalendarEvent {
  return {
    source: "task",
    source_id: task.task_id,
    title: task.title,
    starts_at: task.due_at,
    kind: task.status === "done" ? "task_done" : "task",
  };
}
