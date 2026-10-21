// backend/sheets/schemas/*.py に対応する最小限の型。Workers はバックエンドの Python
// モデルをそのまま使えないため、必要なフィールドだけを素朴な型で再定義する。

export interface Env {
  SPREADSHEET_ID: string;
  GOOGLE_SERVICE_ACCOUNT_JSON: string;
  GOOGLE_CALENDAR_ID?: string;
  DISCORD_BOT_TOKEN: string;
  DISCORD_TASK_CHANNEL_ADMIN_ID: string;
  DISCORD_TASK_CHANNEL_OFFICER_ID: string;
  DISCORD_TASK_CHANNEL_MEMBER_ID: string;
}

export type TaskStatus = "todo" | "doing" | "done";
export type Visibility = "admin" | "officer" | "member";

// sheets/schemas/tasks.py の Task に対応。Workers は読み取りのみ行う
// (ステータス変更やタスクの編集はアプリ本体=FastAPI側の責務のまま)。
export interface TaskRow {
  task_id: string;
  title: string;
  description: string;
  due_at: string; // ISO8601 (+09:00 固定)
  status: TaskStatus;
  visibility: Visibility;
  related_activity_id: string | null;
  reminder_offsets: string; // "-7d,-1d,-2h" 形式
  google_event_id: string | null;
  is_active: boolean;
}

// sheets/schemas/activities.py の Activity に対応。Googleカレンダー同期(calendarSync.ts)で
// 読み取りのみ行う。
export interface ActivityRow {
  activity_id: string;
  starts_at: string; // ISO8601 (+09:00)
  duration_min: number;
  location: string;
  title: string;
  description: string;
  target: string;
  google_event_id: string | null;
  is_active: boolean;
}

// sheets/schemas/tasks.py の TaskAssignee に対応。
export interface AssigneeRow {
  task_id: string;
  member_id: string | null;
  label: string | null;
}

export type ReminderChannel = "dm" | "guild";

// CLAUDE.md のリマインド仕様にある reminder_log(追記専用)の1行。
export interface ReminderLogRow {
  task_id: string;
  offset_key: string;
  channel: ReminderChannel;
  member_id: string; // guild(チャンネル投稿)行は空文字
  sent_at: string;
}
