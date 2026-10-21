import type { Task } from "../api/types";

/** 期限切れかどうか。完了済みのタスクは期限を過ぎていても対象外にする
 * (すでに終わっているものを警告表示する意味がないため)。 */
export function isTaskOverdue(task: Pick<Task, "due_at" | "status">, now: Date = new Date()): boolean {
  if (task.status === "done") return false;
  return new Date(task.due_at).getTime() < now.getTime();
}
