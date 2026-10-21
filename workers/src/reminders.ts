import type { AssigneeRow, ReminderChannel, ReminderLogRow, TaskRow, Visibility } from "./types";

export interface OffsetSpec {
  /** reminder_log.offset_key にそのまま使う生の区間文字列(例 "-7d")。 */
  key: string;
  /** 期限からどれだけ前かをミリ秒で表したもの。 */
  ms: number;
}

type OffsetUnit = "d" | "h" | "m";

const OFFSET_SEGMENT = /^-(\d+)([dhm])$/;
const UNIT_MS: Record<OffsetUnit, number> = { d: 86_400_000, h: 3_600_000, m: 60_000 };
const UNIT_LABEL_JA: Record<OffsetUnit, string> = { d: "日前", h: "時間前", m: "分前" };

/** 正規表現の一致結果から amount/unit を取り出す。[dhm] に一致した時点で
 * unit は OffsetUnit のいずれかであることが保証されている。 */
function parseOffsetMatch(match: RegExpExecArray): { amount: number; unit: OffsetUnit } {
  return { amount: Number(match[1]), unit: match[2] as OffsetUnit };
}

/** "-7d,-1d,-2h" のようなカンマ区切り文字列をオフセットの配列に変換する。
 * 壊れた区間(人間がセルを直接編集して壊した等)は無視する(CLAUDE.md §8)。 */
export function parseReminderOffsets(value: string): OffsetSpec[] {
  if (!value.trim()) return [];
  const specs: OffsetSpec[] = [];
  for (const segment of value.split(",")) {
    const trimmed = segment.trim();
    const match = OFFSET_SEGMENT.exec(trimmed);
    if (!match) continue;
    const { amount, unit } = parseOffsetMatch(match);
    specs.push({ key: trimmed, ms: amount * UNIT_MS[unit] });
  }
  return specs;
}

/** "-7d" -> "7日前" のような表示用ラベルに変換する。 */
export function describeOffset(key: string): string {
  const match = OFFSET_SEGMENT.exec(key);
  if (!match) return key;
  const { amount, unit } = parseOffsetMatch(match);
  return `${amount}${UNIT_LABEL_JA[unit]}`;
}

export interface ReminderJob {
  task: TaskRow;
  offsetKey: string;
  channel: ReminderChannel;
  /** channel が "guild" のときは空文字。 */
  memberId: string;
}

function reminderLogKey(taskId: string, offsetKey: string, channel: ReminderChannel, memberId: string): string {
  return `${taskId}|${offsetKey}|${channel}|${memberId}`;
}

/**
 * 「期限を過ぎていて、まだ送っていない」リマインドをすべて洗い出す(純粋関数)。
 *
 * 冪等性: reminder_log の (task_id, offset_key, channel, member_id) をキーに、
 * 既に記録済みのものは除外する。
 *
 * 実行の遅延に強い設計: 「ちょうど今のオフセットだけ」ではなく
 * 「期限 + オフセット <= now のものすべて」を対象にするため、Worker が1回落ちても
 * 次の実行で取りこぼしなく拾える。
 */
export function computeReminderJobs(input: {
  tasks: TaskRow[];
  assignees: AssigneeRow[];
  reminderLog: ReminderLogRow[];
  now: Date;
}): ReminderJob[] {
  const { tasks, assignees, reminderLog, now } = input;
  const nowMs = now.getTime();

  const alreadySent = new Set(
    reminderLog.map((row) => reminderLogKey(row.task_id, row.offset_key, row.channel, row.member_id)),
  );

  const assigneesByTask = new Map<string, AssigneeRow[]>();
  for (const assignee of assignees) {
    const list = assigneesByTask.get(assignee.task_id) ?? [];
    list.push(assignee);
    assigneesByTask.set(assignee.task_id, list);
  }

  const jobs: ReminderJob[] = [];
  for (const task of tasks) {
    if (!task.is_active || task.status === "done") continue;
    const dueMs = new Date(task.due_at).getTime();
    if (Number.isNaN(dueMs)) continue; // 壊れた due_at はスキップ(CLAUDE.md §8)

    for (const offset of parseReminderOffsets(task.reminder_offsets)) {
      const triggerMs = dueMs - offset.ms;
      if (triggerMs > nowMs) continue; // まだ先

      const guildKey = reminderLogKey(task.task_id, offset.key, "guild", "");
      if (!alreadySent.has(guildKey)) {
        jobs.push({ task, offsetKey: offset.key, channel: "guild", memberId: "" });
      }

      // 担当者ごとのDM。部門名などの自由記述(member_id が無い)はDM対象外。
      for (const assignee of assigneesByTask.get(task.task_id) ?? []) {
        if (!assignee.member_id) continue;
        const dmKey = reminderLogKey(task.task_id, offset.key, "dm", assignee.member_id);
        if (!alreadySent.has(dmKey)) {
          jobs.push({ task, offsetKey: offset.key, channel: "dm", memberId: assignee.member_id });
        }
      }
    }
  }
  return jobs;
}

function formatDueAtJa(iso: string): string {
  const formatter = new Intl.DateTimeFormat("ja-JP", {
    timeZone: "Asia/Tokyo",
    month: "numeric",
    day: "numeric",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
  return formatter.format(new Date(iso));
}

export function buildReminderMessage(task: TaskRow, offsetKey: string): string {
  const lines = [
    `⏰ **${task.title}** の期限が近づいています(${describeOffset(offsetKey)})`,
    `期限: ${formatDueAtJa(task.due_at)}`,
  ];
  if (task.description) lines.push(task.description);
  return lines.join("\n");
}

export interface ReminderDeps {
  postChannelMessage: (channelId: string, content: string) => Promise<void>;
  sendDirectMessage: (memberId: string, content: string) => Promise<void>;
  channelIdFor: (visibility: Visibility) => string;
}

export interface DispatchFailure {
  job: ReminderJob;
  error: string;
}

export interface DispatchResult {
  sent: ReminderLogRow[];
  failures: DispatchFailure[];
}

/**
 * ジョブを1件ずつ送信する。1件の失敗(DM拒否等)が他の送信を止めないよう、
 * 各ジョブを個別に try/catch する(部分失敗の扱い、ユーザー要件)。
 * reminder_log へ追記するのは成功した分だけ(呼び出し元が1回のAPI呼び出しで
 * まとめて追記する想定、CLAUDE.md §8)。
 */
export async function dispatchReminders(
  jobs: ReminderJob[],
  deps: ReminderDeps,
  now: Date,
): Promise<DispatchResult> {
  const sent: ReminderLogRow[] = [];
  const failures: DispatchFailure[] = [];

  for (const job of jobs) {
    const message = buildReminderMessage(job.task, job.offsetKey);
    try {
      if (job.channel === "guild") {
        await deps.postChannelMessage(deps.channelIdFor(job.task.visibility), message);
      } else {
        await deps.sendDirectMessage(job.memberId, message);
      }
      sent.push({
        task_id: job.task.task_id,
        offset_key: job.offsetKey,
        channel: job.channel,
        member_id: job.memberId,
        sent_at: now.toISOString(),
      });
    } catch (error) {
      failures.push({ job, error: error instanceof Error ? error.message : String(error) });
    }
  }

  return { sent, failures };
}
