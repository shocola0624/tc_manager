import type { ActivityRow, AssigneeRow, ReminderChannel, ReminderLogRow, TaskRow, TaskStatus, Visibility } from "./types";

const TASK_STATUSES: TaskStatus[] = ["todo", "doing", "done"];
const VISIBILITIES: Visibility[] = ["admin", "officer", "member"];
const REMINDER_CHANNELS: ReminderChannel[] = ["dm", "guild"];

function parseBoolDefaultTrue(value: string): boolean {
  const normalized = value.trim().toLowerCase();
  if (normalized === "") return true;
  return normalized === "true" || normalized === "1" || normalized === "yes";
}

/**
 * tasks シートの1行を検証する。人間がセルを直接編集して壊した行は例外を投げず
 * null を返してスキップする(CLAUDE.md §8: 読み取り時に握りつぶさない、は
 * アプリ側のUIで可視化する責務であり、Workers は「安全にスキップしてログに残す」
 * 側を担う。壊れた行で Cron 全体を落とさないことを優先する)。
 */
export function parseTaskRow(record: Record<string, string>): TaskRow | null {
  const taskId = record.task_id?.trim();
  const title = record.title?.trim();
  const dueAt = record.due_at?.trim();
  const status = record.status?.trim();
  const visibility = record.visibility?.trim();
  if (!taskId || !title || !dueAt) return null;
  if (!TASK_STATUSES.includes(status as TaskStatus)) return null;
  if (!VISIBILITIES.includes(visibility as Visibility)) return null;
  if (Number.isNaN(new Date(dueAt).getTime())) return null;

  return {
    task_id: taskId,
    title,
    description: record.description ?? "",
    due_at: dueAt,
    status: status as TaskStatus,
    visibility: visibility as Visibility,
    related_activity_id: record.related_activity_id?.trim() || null,
    reminder_offsets: record.reminder_offsets ?? "",
    google_event_id: record.google_event_id?.trim() || null,
    is_active: parseBoolDefaultTrue(record.is_active ?? ""),
  };
}

/** activities シートの1行を検証する。壊れた行は parseTaskRow と同じく null を返してスキップする。 */
export function parseActivityRow(record: Record<string, string>): ActivityRow | null {
  const activityId = record.activity_id?.trim();
  const title = record.title?.trim();
  const startsAt = record.starts_at?.trim();
  const durationRaw = record.duration_min?.trim() ?? "";
  if (!activityId || !title || !startsAt) return null;
  if (Number.isNaN(new Date(startsAt).getTime())) return null;
  if (!/^\d+$/.test(durationRaw)) return null;

  return {
    activity_id: activityId,
    starts_at: startsAt,
    duration_min: Number(durationRaw),
    location: record.location?.trim() ?? "",
    title,
    description: record.description ?? "",
    target: record.target?.trim() ?? "",
    google_event_id: record.google_event_id?.trim() || null,
    is_active: parseBoolDefaultTrue(record.is_active ?? ""),
  };
}

export function parseAssigneeRow(record: Record<string, string>): AssigneeRow | null {
  const taskId = record.task_id?.trim();
  const memberId = record.member_id?.trim() || null;
  const label = record.label?.trim() || null;
  if (!taskId) return null;
  if ((memberId === null) === (label === null)) return null; // どちらか一方だけ
  return { task_id: taskId, member_id: memberId, label };
}

export function parseReminderLogRow(record: Record<string, string>): ReminderLogRow | null {
  const taskId = record.task_id?.trim();
  const offsetKey = record.offset_key?.trim();
  const channel = record.channel?.trim();
  if (!taskId || !offsetKey) return null;
  if (!REMINDER_CHANNELS.includes(channel as ReminderChannel)) return null;
  return {
    task_id: taskId,
    offset_key: offsetKey,
    channel: channel as ReminderChannel,
    member_id: record.member_id ?? "",
    sent_at: record.sent_at ?? "",
  };
}

export function parseTaskRows(records: Record<string, string>[]): TaskRow[] {
  return records.map(parseTaskRow).filter((row): row is TaskRow => row !== null);
}

export function parseAssigneeRows(records: Record<string, string>[]): AssigneeRow[] {
  return records.map(parseAssigneeRow).filter((row): row is AssigneeRow => row !== null);
}

export function parseReminderLogRows(records: Record<string, string>[]): ReminderLogRow[] {
  return records.map(parseReminderLogRow).filter((row): row is ReminderLogRow => row !== null);
}
