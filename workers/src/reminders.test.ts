import { describe, expect, it, vi } from "vitest";
import {
  buildReminderMessage,
  computeReminderJobs,
  describeOffset,
  dispatchReminders,
  parseReminderOffsets,
  type ReminderDeps,
} from "./reminders";
import type { AssigneeRow, ReminderLogRow, TaskRow } from "./types";

function task(overrides: Partial<TaskRow> = {}): TaskRow {
  return {
    task_id: "t1",
    title: "資料作成",
    description: "",
    due_at: "2026-10-20T18:00:00+09:00",
    status: "todo",
    visibility: "member",
    related_activity_id: null,
    reminder_offsets: "-7d,-1d",
    google_event_id: null,
    is_active: true,
    ...overrides,
  };
}

describe("parseReminderOffsets", () => {
  it("parses valid segments into offset specs", () => {
    expect(parseReminderOffsets("-7d,-1d,-2h,-30m")).toEqual([
      { key: "-7d", ms: 7 * 86_400_000 },
      { key: "-1d", ms: 86_400_000 },
      { key: "-2h", ms: 2 * 3_600_000 },
      { key: "-30m", ms: 30 * 60_000 },
    ]);
  });

  it("returns an empty array for blank input", () => {
    expect(parseReminderOffsets("")).toEqual([]);
    expect(parseReminderOffsets("   ")).toEqual([]);
  });

  it("skips malformed segments instead of throwing (CLAUDE.md §8: don't crash on a human-edited sheet)", () => {
    expect(parseReminderOffsets("-7d,garbage,7d,-1x")).toEqual([{ key: "-7d", ms: 7 * 86_400_000 }]);
  });
});

describe("describeOffset", () => {
  it("formats known units in Japanese", () => {
    expect(describeOffset("-7d")).toBe("7日前");
    expect(describeOffset("-2h")).toBe("2時間前");
    expect(describeOffset("-30m")).toBe("30分前");
  });

  it("falls back to the raw key for anything unrecognized", () => {
    expect(describeOffset("weird")).toBe("weird");
  });
});

describe("computeReminderJobs", () => {
  const now = new Date("2026-10-19T00:00:00+09:00"); // due 2026-10-20T18:00, so -1d (10/19 18:00) not yet due, -7d (10/13) already due

  it("produces a guild job once the offset has passed", () => {
    const jobs = computeReminderJobs({ tasks: [task()], assignees: [], reminderLog: [], now });
    expect(jobs).toEqual([{ task: task(), offsetKey: "-7d", channel: "guild", memberId: "" }]);
  });

  it("does not produce a job for an offset that has not passed yet", () => {
    const jobs = computeReminderJobs({
      tasks: [task({ reminder_offsets: "-1d" })],
      assignees: [],
      reminderLog: [],
      now,
    });
    expect(jobs).toEqual([]);
  });

  it("is idempotent: a job already present in reminder_log is not reproduced", () => {
    const reminderLog: ReminderLogRow[] = [
      { task_id: "t1", offset_key: "-7d", channel: "guild", member_id: "", sent_at: "2026-10-13T00:00:00+09:00" },
    ];
    const jobs = computeReminderJobs({ tasks: [task()], assignees: [], reminderLog, now });
    expect(jobs).toEqual([]);
  });

  it("still fires even when the run is very late (not just 'exactly now')", () => {
    const farFuture = new Date("2026-12-01T00:00:00+09:00");
    const jobs = computeReminderJobs({ tasks: [task()], assignees: [], reminderLog: [], now: farFuture });
    expect(jobs.map((j) => j.offsetKey)).toEqual(["-7d", "-1d"]);
  });

  it("excludes done tasks", () => {
    const jobs = computeReminderJobs({ tasks: [task({ status: "done" })], assignees: [], reminderLog: [], now });
    expect(jobs).toEqual([]);
  });

  it("excludes soft-deleted tasks", () => {
    const jobs = computeReminderJobs({ tasks: [task({ is_active: false })], assignees: [], reminderLog: [], now });
    expect(jobs).toEqual([]);
  });

  it("skips a task with an unparseable due_at instead of crashing", () => {
    const jobs = computeReminderJobs({
      tasks: [task({ due_at: "not-a-date" })],
      assignees: [],
      reminderLog: [],
      now,
    });
    expect(jobs).toEqual([]);
  });

  it("produces a dm job per assignee with a member_id", () => {
    const assignees: AssigneeRow[] = [
      { task_id: "t1", member_id: "u1", label: null },
      { task_id: "t1", member_id: "u2", label: null },
    ];
    const jobs = computeReminderJobs({ tasks: [task()], assignees, reminderLog: [], now });
    const dmJobs = jobs.filter((j) => j.channel === "dm");
    expect(dmJobs.map((j) => j.memberId).sort()).toEqual(["u1", "u2"]);
  });

  it("does not produce a dm job for a department label assignee", () => {
    const assignees: AssigneeRow[] = [{ task_id: "t1", member_id: null, label: "広報部" }];
    const jobs = computeReminderJobs({ tasks: [task()], assignees, reminderLog: [], now });
    expect(jobs.some((j) => j.channel === "dm")).toBe(false);
    expect(jobs.some((j) => j.channel === "guild")).toBe(true);
  });

  it("does not re-send a dm already logged for that member but still sends to a new assignee", () => {
    const assignees: AssigneeRow[] = [
      { task_id: "t1", member_id: "u1", label: null },
      { task_id: "t1", member_id: "u2", label: null },
    ];
    const reminderLog: ReminderLogRow[] = [
      { task_id: "t1", offset_key: "-7d", channel: "dm", member_id: "u1", sent_at: "2026-10-13T00:00:00+09:00" },
      { task_id: "t1", offset_key: "-7d", channel: "guild", member_id: "", sent_at: "2026-10-13T00:00:00+09:00" },
    ];
    const jobs = computeReminderJobs({ tasks: [task()], assignees, reminderLog, now });
    expect(jobs).toEqual([{ task: task(), offsetKey: "-7d", channel: "dm", memberId: "u2" }]);
  });
});

describe("buildReminderMessage", () => {
  it("includes the title, offset label, formatted due date, and description", () => {
    const message = buildReminderMessage(task({ description: "印刷して配布" }), "-1d");
    expect(message).toContain("資料作成");
    expect(message).toContain("1日前");
    expect(message).toContain("印刷して配布");
  });

  it("omits the description line when there is none", () => {
    const message = buildReminderMessage(task({ description: "" }), "-1d");
    expect(message.split("\n")).toHaveLength(2);
  });
});

describe("dispatchReminders", () => {
  const now = new Date("2026-10-19T00:00:00+09:00");

  function makeDeps(overrides: Partial<ReminderDeps> = {}): ReminderDeps {
    return {
      postChannelMessage: vi.fn().mockResolvedValue(undefined),
      sendDirectMessage: vi.fn().mockResolvedValue(undefined),
      channelIdFor: (visibility) => `channel-${visibility}`,
      ...overrides,
    };
  }

  it("sends every job and records a reminder_log row per success", async () => {
    const jobs = [
      { task: task(), offsetKey: "-7d", channel: "guild" as const, memberId: "" },
      { task: task(), offsetKey: "-7d", channel: "dm" as const, memberId: "u1" },
    ];
    const deps = makeDeps();
    const result = await dispatchReminders(jobs, deps, now);

    expect(result.failures).toEqual([]);
    expect(result.sent).toHaveLength(2);
    expect(deps.postChannelMessage).toHaveBeenCalledWith("channel-member", expect.stringContaining("資料作成"));
    expect(deps.sendDirectMessage).toHaveBeenCalledWith("u1", expect.stringContaining("資料作成"));
  });

  it("keeps sending remaining jobs when one DM fails (partial failure handling)", async () => {
    const jobs = [
      { task: task(), offsetKey: "-7d", channel: "dm" as const, memberId: "u1" },
      { task: task(), offsetKey: "-7d", channel: "guild" as const, memberId: "" },
    ];
    const deps = makeDeps({
      sendDirectMessage: vi.fn().mockRejectedValue(new Error("DMs closed")),
    });
    const result = await dispatchReminders(jobs, deps, now);

    expect(result.failures).toHaveLength(1);
    expect(result.failures[0]!.job.memberId).toBe("u1");
    expect(result.sent).toHaveLength(1);
    expect(result.sent[0]!.channel).toBe("guild");
  });

  it("does not add a reminder_log row for a failed send", async () => {
    const jobs = [{ task: task(), offsetKey: "-7d", channel: "guild" as const, memberId: "" }];
    const deps = makeDeps({ postChannelMessage: vi.fn().mockRejectedValue(new Error("channel not found")) });
    const result = await dispatchReminders(jobs, deps, now);

    expect(result.sent).toEqual([]);
    expect(result.failures).toHaveLength(1);
  });

  it("routes the channel post to the channel matching the task's visibility", async () => {
    const deps = makeDeps();
    await dispatchReminders(
      [{ task: task({ visibility: "admin" }), offsetKey: "-7d", channel: "guild" as const, memberId: "" }],
      deps,
      now,
    );
    expect(deps.postChannelMessage).toHaveBeenCalledWith("channel-admin", expect.any(String));
  });
});
