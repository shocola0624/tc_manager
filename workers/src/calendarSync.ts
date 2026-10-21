import { CalendarApiError, type CalendarEvent } from "./googleCalendar";
import type { ActivityRow, TaskRow } from "./types";

/**
 * アプリ(スプレッドシート) → Google カレンダーの一方向同期(双方向同期は実装しない)。
 *
 * 重複登録を防ぐ要: イベントIDを activity_id / task_id から決定的に生成する
 * (Calendar API は insert 時に任意の id を指定できる)。insert に成功した直後に
 * シートへの google_event_id 書き戻しが失敗しても、次回は同じ id のイベントが
 * 見つかるので update になるだけで、二重登録は起きない。google_event_id 列は
 * 「同期済みかどうか」を人間がシート上で確認するための記録として書き戻す。
 *
 * 毎時すべてのイベントを update し直さないよう、events.list で現在の状態を1回で
 * 取得し、差分があるものだけ書き込む。
 */

export type SyncSource = "activity" | "task";

/** このアプリが作ったイベントであることを示す extendedProperties.private のキー。
 * 人間が同じカレンダーに手で追加したイベントは削除対象にしない。 */
const SOURCE_PROPERTY = "tc_source";
const SOURCE_ID_PROPERTY = "tc_source_id";

const TIME_ZONE = "Asia/Tokyo";
/** タスクは期限の時刻を開始とする短い枠として登録する(開始=終了のイベントは API が拒否するため)。 */
const TASK_EVENT_DURATION_MS = 30 * 60_000;

// Google カレンダーの colorId(イベント色)。アプリ内カレンダーの配色(活動=青系、
// タスク=オレンジ系、完了タスク=灰色)に寄せる。
const COLOR_ACTIVITY = "9"; // Blueberry
const COLOR_TASK = "6"; // Tangerine
const COLOR_TASK_DONE = "8"; // Graphite

const SYNC_FOOTER = "※ このイベントはアプリから自動同期されています。編集はアプリまたはスプレッドシートで行ってください。";

/** Calendar のイベントIDに使える文字は base32hex(a-v, 0-9)のみのため、
 * "activity:<id>" を UTF-8 の16進表記にして使う(16進は base32hex の部分集合)。 */
export function eventIdFor(source: SyncSource, sourceId: string): string {
  const bytes = new TextEncoder().encode(`${source}:${sourceId}`);
  let hex = "";
  for (const byte of bytes) hex += byte.toString(16).padStart(2, "0");
  return `tc${hex}`;
}

export interface Located<T> {
  row: T;
  /** シート上の1始まりの行番号(ヘッダ行が1)。google_event_id の書き戻しに使う。 */
  rowNumber: number;
}

/** rowsToRecords の結果を検証しつつ、元の行番号を保ったまま変換する。壊れた行はスキップ。 */
export function locateRows<T>(
  records: Record<string, string>[],
  parse: (record: Record<string, string>) => T | null,
): Located<T>[] {
  const located: Located<T>[] = [];
  records.forEach((record, index) => {
    const row = parse(record);
    if (row !== null) located.push({ row, rowNumber: index + 2 });
  });
  return located;
}

export interface SyncTarget {
  source: SyncSource;
  sourceId: string;
  rowNumber: number;
  /** シートに現在書かれている google_event_id(空なら null)。 */
  currentGoogleEventId: string | null;
  event: CalendarEvent;
}

function joinDescription(parts: string[]): string {
  return [...parts.map((part) => part.trim()).filter(Boolean), SYNC_FOOTER].join("\n\n");
}

function toEventTime(ms: number): { dateTime: string; timeZone: string } {
  return { dateTime: new Date(ms).toISOString(), timeZone: TIME_ZONE };
}

function sourceProperties(source: SyncSource, sourceId: string): CalendarEvent["extendedProperties"] {
  return { private: { [SOURCE_PROPERTY]: source, [SOURCE_ID_PROPERTY]: sourceId } };
}

export function buildActivityEvent(activity: ActivityRow): CalendarEvent {
  const startMs = new Date(activity.starts_at).getTime();
  return {
    id: eventIdFor("activity", activity.activity_id),
    summary: activity.title,
    description: joinDescription([activity.description, activity.target ? `対象: ${activity.target}` : ""]),
    location: activity.location,
    colorId: COLOR_ACTIVITY,
    start: toEventTime(startMs),
    end: toEventTime(startMs + activity.duration_min * 60_000),
    status: "confirmed",
    extendedProperties: sourceProperties("activity", activity.activity_id),
  };
}

export function buildTaskEvent(task: TaskRow): CalendarEvent {
  const dueMs = new Date(task.due_at).getTime();
  const done = task.status === "done";
  return {
    id: eventIdFor("task", task.task_id),
    summary: `${done ? "✓" : "〆"} ${task.title}`,
    description: joinDescription([task.description]),
    location: "",
    colorId: done ? COLOR_TASK_DONE : COLOR_TASK,
    start: toEventTime(dueMs),
    end: toEventTime(dueMs + TASK_EVENT_DURATION_MS),
    status: "confirmed",
    extendedProperties: sourceProperties("task", task.task_id),
  };
}

/**
 * 同期すべきイベントの一覧を作る。
 *
 * - is_active=FALSE(論理削除)の行は対象外 → カレンダー上に残っていれば削除される
 * - タスクは visibility=member のものだけ。同期先カレンダーは部員全体に共有する想定のため、
 *   幹部限定(admin/officer)のタスクをカレンダー経由で漏らさない
 */
export function collectSyncTargets(input: {
  activities: Located<ActivityRow>[];
  tasks: Located<TaskRow>[];
}): SyncTarget[] {
  const targets: SyncTarget[] = [];
  for (const { row, rowNumber } of input.activities) {
    if (!row.is_active) continue;
    targets.push({
      source: "activity",
      sourceId: row.activity_id,
      rowNumber,
      currentGoogleEventId: row.google_event_id,
      event: buildActivityEvent(row),
    });
  }
  for (const { row, rowNumber } of input.tasks) {
    if (!row.is_active || row.visibility !== "member") continue;
    targets.push({
      source: "task",
      sourceId: row.task_id,
      rowNumber,
      currentGoogleEventId: row.google_event_id,
      event: buildTaskEvent(row),
    });
  }
  return targets;
}

export type SyncOperation =
  | { kind: "insert"; target: SyncTarget }
  | { kind: "update"; target: SyncTarget }
  | { kind: "delete"; eventId: string };

function normalizeText(value: string | undefined): string {
  return (value ?? "").replace(/\r\n/g, "\n").trim();
}

function timeMs(time: CalendarEventTime | undefined): number {
  return time?.dateTime ? new Date(time.dateTime).getTime() : Number.NaN;
}

type CalendarEventTime = NonNullable<CalendarEvent["start"]>;

/** 同期に関係するフィールドだけを比べる。時刻はタイムゾーン表記の違い
 * (API は "+09:00" で返し、こちらは "Z" で送る)を吸収するため実時刻で比べる。 */
export function isSameEvent(desired: CalendarEvent, actual: CalendarEvent): boolean {
  return (
    normalizeText(desired.summary) === normalizeText(actual.summary) &&
    normalizeText(desired.description) === normalizeText(actual.description) &&
    normalizeText(desired.location) === normalizeText(actual.location) &&
    (desired.colorId ?? "") === (actual.colorId ?? "") &&
    timeMs(desired.start) === timeMs(actual.start) &&
    timeMs(desired.end) === timeMs(actual.end)
  );
}

function isManagedEvent(event: CalendarEvent): boolean {
  return Boolean(event.extendedProperties?.private?.[SOURCE_PROPERTY]);
}

/** 目標状態(targets)と現在のカレンダー(existing)の差分から操作列を作る(純粋関数)。 */
export function planCalendarSync(targets: SyncTarget[], existing: CalendarEvent[]): SyncOperation[] {
  const existingById = new Map(existing.map((event) => [event.id, event]));
  const desiredIds = new Set(targets.map((target) => target.event.id));

  const operations: SyncOperation[] = [];
  for (const target of targets) {
    const actual = existingById.get(target.event.id);
    if (!actual) {
      operations.push({ kind: "insert", target });
    } else if (!isSameEvent(target.event, actual)) {
      operations.push({ kind: "update", target });
    }
  }
  for (const event of existing) {
    if (isManagedEvent(event) && !desiredIds.has(event.id)) {
      operations.push({ kind: "delete", eventId: event.id });
    }
  }
  return operations;
}

export interface CalendarSyncDeps {
  insertEvent: (event: CalendarEvent) => Promise<void>;
  updateEvent: (event: CalendarEvent) => Promise<void>;
  deleteEvent: (eventId: string) => Promise<void>;
}

export interface CalendarSyncFailure {
  operation: SyncOperation;
  error: string;
}

export interface CalendarSyncResult {
  succeeded: SyncOperation[];
  failures: CalendarSyncFailure[];
  /** 1回の実行あたりの上限を超えたため、次回以降に回した操作の数。 */
  deferred: number;
}

/**
 * 操作を1件ずつ実行する。1件の失敗が他を止めないよう個別に try/catch する
 * (reminders.ts の dispatchReminders と同じ方針)。
 *
 * maxWrites: Cloudflare Workers は1回の実行あたりのサブリクエスト数に上限がある
 * (Free プランで50)。初回同期などで大量の差分があっても上限内に収め、
 * 残りは次回の Cron に回す(差分計算は毎回やり直すので取りこぼさない)。
 */
export async function executeCalendarSync(
  operations: SyncOperation[],
  deps: CalendarSyncDeps,
  maxWrites: number,
): Promise<CalendarSyncResult> {
  const succeeded: SyncOperation[] = [];
  const failures: CalendarSyncFailure[] = [];
  const batch = operations.slice(0, maxWrites);

  for (const operation of batch) {
    try {
      if (operation.kind === "insert") {
        try {
          await deps.insertEvent(operation.target.event);
        } catch (error) {
          // 同じ id のイベントが削除済みとして残っている(論理削除→復活した行など)。
          // update(PUT)で status=confirmed を送れば復活できる。
          if (error instanceof CalendarApiError && error.status === 409) {
            await deps.updateEvent(operation.target.event);
          } else {
            throw error;
          }
        }
      } else if (operation.kind === "update") {
        await deps.updateEvent(operation.target.event);
      } else {
        await deps.deleteEvent(operation.eventId);
      }
      succeeded.push(operation);
    } catch (error) {
      failures.push({ operation, error: error instanceof Error ? error.message : String(error) });
    }
  }

  return { succeeded, failures, deferred: operations.length - batch.length };
}

export interface EventIdWriteback {
  source: SyncSource;
  rowNumber: number;
  eventId: string;
}

/**
 * シートの google_event_id 列に書き戻すべきセルを求める。
 * カレンダー上にイベントが存在すると確認できたもの(今回 insert/update に成功した、
 * または既に同期済みだった)のうち、セルの値が実際の id と異なるものだけを対象にする。
 */
export function computeEventIdWritebacks(
  targets: SyncTarget[],
  existing: CalendarEvent[],
  succeeded: SyncOperation[],
): EventIdWriteback[] {
  const presentIds = new Set(existing.map((event) => event.id));
  for (const operation of succeeded) {
    if (operation.kind !== "delete") presentIds.add(operation.target.event.id);
  }
  return targets
    .filter((target) => presentIds.has(target.event.id) && target.currentGoogleEventId !== target.event.id)
    .map((target) => ({ source: target.source, rowNumber: target.rowNumber, eventId: target.event.id }));
}
