import {
  collectSyncTargets,
  computeEventIdWritebacks,
  executeCalendarSync,
  locateRows,
  planCalendarSync,
  type SyncSource,
} from "./calendarSync";
import { getAccessToken, parseServiceAccountJson } from "./googleAuth";
import { deleteEvent, insertEvent, listEvents, updateEvent } from "./googleCalendar";
import { postChannelMessage, sendDirectMessage } from "./discord";
import { parseActivityRow, parseAssigneeRows, parseReminderLogRows, parseTaskRow, parseTaskRows } from "./parsing";
import { computeReminderJobs, dispatchReminders, type ReminderDeps } from "./reminders";
import { appendRows, batchGetValues, batchUpdateCells, recordToRow, rowsToRecords, type CellUpdate } from "./sheets";
import type { Env, Visibility } from "./types";

const SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets";
const CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events";
const TASKS_SHEET = "tasks";
const TASK_ASSIGNEES_SHEET = "task_assignees";
const REMINDER_LOG_SHEET = "reminder_log";
const ACTIVITIES_SHEET = "activities";
const GOOGLE_EVENT_ID_COLUMN = "google_event_id";
/** 1回の Cron 実行で行うカレンダー書き込みの上限(Workers のサブリクエスト上限対策。
 * 超えた分は次回に回る。calendarSync.ts の executeCalendarSync 参照)。 */
const MAX_CALENDAR_WRITES_PER_RUN = 30;
const REMINDER_LOG_HEADER = ["task_id", "offset_key", "channel", "member_id", "sent_at"];

function channelIdFor(env: Env): (visibility: Visibility) => string {
  const byVisibility: Record<Visibility, string> = {
    admin: env.DISCORD_TASK_CHANNEL_ADMIN_ID,
    officer: env.DISCORD_TASK_CHANNEL_OFFICER_ID,
    member: env.DISCORD_TASK_CHANNEL_MEMBER_ID,
  };
  return (visibility) => byVisibility[visibility];
}

/**
 * 毎時0分に起動する Cron ハンドラ(wrangler.toml の triggers.crons)。
 *
 * 必要なシートをまとめて1回のAPI呼び出しで読み(CLAUDE.md §8)、
 * リマインド配信 → Googleカレンダー同期の順に実行する。片方が失敗してももう片方は
 * 実行する(カレンダー側の設定不備でリマインドが止まらないように)。
 */
export default {
  async scheduled(_controller: ScheduledController, env: Env, ctx: ExecutionContext): Promise<void> {
    ctx.waitUntil(run(env));
  },
} satisfies ExportedHandler<Env>;

export async function run(env: Env): Promise<void> {
  const serviceAccount = parseServiceAccountJson(env.GOOGLE_SERVICE_ACCOUNT_JSON);
  const calendarEnabled = Boolean(env.GOOGLE_CALENDAR_ID);
  const accessToken = await getAccessToken(
    serviceAccount,
    calendarEnabled ? [SHEETS_SCOPE, CALENDAR_SCOPE] : [SHEETS_SCOPE],
  );

  const sheetNames = [TASKS_SHEET, TASK_ASSIGNEES_SHEET, REMINDER_LOG_SHEET];
  if (calendarEnabled) sheetNames.push(ACTIVITIES_SHEET);
  const [taskRows = [], assigneeRows = [], reminderLogRows = [], activityRows = []] = await batchGetValues(
    accessToken,
    env.SPREADSHEET_ID,
    sheetNames,
  );

  let failed = false;
  try {
    await runReminders(env, accessToken, taskRows, assigneeRows, reminderLogRows);
  } catch (error) {
    failed = true;
    console.error(`reminders: aborted: ${error instanceof Error ? error.message : String(error)}`);
  }

  if (!calendarEnabled) {
    console.log("calendar sync: skipped (GOOGLE_CALENDAR_ID is not set)");
  } else {
    try {
      await runCalendarSync(env, env.GOOGLE_CALENDAR_ID!, accessToken, taskRows, activityRows);
    } catch (error) {
      failed = true;
      console.error(`calendar sync: aborted: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  // 握りつぶさず Cron の実行自体を失敗として記録する(Workers のダッシュボードで確認できる)。
  if (failed) throw new Error("scheduled run finished with errors (see logs above)");
}

/**
 * 1. 期限を過ぎていてまだ送っていないリマインドを洗い出す(reminders.ts、冪等)
 * 2. 1件ずつ送信する(DMが失敗してもチャンネル投稿は続ける)
 * 3. 成功した分だけ reminder_log にまとめて追記する(1回のAPI呼び出し)
 */
async function runReminders(
  env: Env,
  accessToken: string,
  taskRows: string[][],
  assigneeRows: string[][],
  reminderLogRows: string[][],
): Promise<void> {
  const tasks = parseTaskRows(rowsToRecords(taskRows));
  const assignees = parseAssigneeRows(rowsToRecords(assigneeRows));
  const reminderLog = parseReminderLogRows(rowsToRecords(reminderLogRows));

  const now = new Date();
  const jobs = computeReminderJobs({ tasks, assignees, reminderLog, now });
  console.log(`reminders: ${jobs.length} job(s) due`);
  if (jobs.length === 0) return;

  const deps: ReminderDeps = {
    postChannelMessage: (channelId, content) => postChannelMessage(env.DISCORD_BOT_TOKEN, channelId, content),
    sendDirectMessage: (memberId, content) => sendDirectMessage(env.DISCORD_BOT_TOKEN, memberId, content),
    channelIdFor: channelIdFor(env),
  };

  const { sent, failures } = await dispatchReminders(jobs, deps, now);

  for (const failure of failures) {
    // 失敗は握りつぶさずログに残し、reminder_log には書かない(次回実行で再試行される)。
    console.error(
      `reminder failed: task=${failure.job.task.task_id} offset=${failure.job.offsetKey} channel=${failure.job.channel} member=${failure.job.memberId}: ${failure.error}`,
    );
  }

  if (sent.length > 0) {
    await appendRows(
      accessToken,
      env.SPREADSHEET_ID,
      REMINDER_LOG_SHEET,
      sent.map((row) =>
        recordToRow(
          {
            task_id: row.task_id,
            offset_key: row.offset_key,
            channel: row.channel,
            member_id: row.member_id,
            sent_at: row.sent_at,
          },
          REMINDER_LOG_HEADER,
        ),
      ),
    );
  }
  console.log(`reminders: sent=${sent.length} failed=${failures.length}`);
}

/**
 * Googleカレンダーへの一方向同期(calendarSync.ts)。
 *
 * 1. カレンダー上の既存イベントを1回で取得する
 * 2. activities / tasks から目標状態を作り、差分だけ insert/update/delete する
 * 3. google_event_id 列が未記入・不一致の行にまとめて書き戻す(1回のAPI呼び出し)
 */
async function runCalendarSync(
  env: Env,
  calendarId: string,
  accessToken: string,
  taskRows: string[][],
  activityRows: string[][],
): Promise<void> {
  const targets = collectSyncTargets({
    activities: locateRows(rowsToRecords(activityRows), parseActivityRow),
    tasks: locateRows(rowsToRecords(taskRows), parseTaskRow),
  });

  const existing = await listEvents(accessToken, calendarId);
  const operations = planCalendarSync(targets, existing);
  const { succeeded, failures, deferred } = await executeCalendarSync(
    operations,
    {
      insertEvent: (event) => insertEvent(accessToken, calendarId, event),
      updateEvent: (event) => updateEvent(accessToken, calendarId, event),
      deleteEvent: (eventId) => deleteEvent(accessToken, calendarId, eventId),
    },
    MAX_CALENDAR_WRITES_PER_RUN,
  );

  for (const failure of failures) {
    const op = failure.operation;
    const label = op.kind === "delete" ? op.eventId : `${op.target.source}=${op.target.sourceId}`;
    // 失敗は reminder と同じくログに残し、次回の差分計算で自然に再試行される。
    console.error(`calendar sync failed: ${op.kind} ${label}: ${failure.error}`);
  }

  // 列が無い(移行スクリプト未実行)シートは書き戻しをスキップする。同期自体は
  // 決定的な id で動くため、書き戻せなくても重複登録は起きない。
  const columnIndexBySheet: Record<SyncSource, { sheetName: string; columnIndex: number }> = {
    activity: { sheetName: ACTIVITIES_SHEET, columnIndex: activityRows[0]?.indexOf(GOOGLE_EVENT_ID_COLUMN) ?? -1 },
    task: { sheetName: TASKS_SHEET, columnIndex: taskRows[0]?.indexOf(GOOGLE_EVENT_ID_COLUMN) ?? -1 },
  };
  const cellUpdates: CellUpdate[] = [];
  for (const writeback of computeEventIdWritebacks(targets, existing, succeeded)) {
    const { sheetName, columnIndex } = columnIndexBySheet[writeback.source];
    if (columnIndex < 0) continue;
    cellUpdates.push({ sheetName, rowNumber: writeback.rowNumber, columnIndex, value: writeback.eventId });
  }
  for (const [source, { sheetName, columnIndex }] of Object.entries(columnIndexBySheet)) {
    if (columnIndex < 0) {
      console.warn(`calendar sync: ${sheetName} has no ${GOOGLE_EVENT_ID_COLUMN} column; skipped writeback (${source})`);
    }
  }
  await batchUpdateCells(accessToken, env.SPREADSHEET_ID, cellUpdates);

  console.log(
    `calendar sync: ops=${operations.length} succeeded=${succeeded.length} failed=${failures.length} deferred=${deferred} writebacks=${cellUpdates.length}`,
  );
}
