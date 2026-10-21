import { describe, expect, it, vi } from "vitest";
import {
  buildActivityEvent,
  buildTaskEvent,
  collectSyncTargets,
  computeEventIdWritebacks,
  eventIdFor,
  executeCalendarSync,
  isSameEvent,
  locateRows,
  planCalendarSync,
  type CalendarSyncDeps,
  type SyncOperation,
} from "./calendarSync";
import { CalendarApiError, type CalendarEvent } from "./googleCalendar";
import type { ActivityRow, TaskRow } from "./types";

function activity(overrides: Partial<ActivityRow> = {}): ActivityRow {
  return {
    activity_id: "activity_abc123",
    starts_at: "2026-11-01T14:00:00+09:00",
    duration_min: 90,
    location: "部室",
    title: "ハンドドリップ練習会",
    description: "浅煎りを淹れ比べる",
    target: "全員",
    google_event_id: null,
    is_active: true,
    ...overrides,
  };
}

function task(overrides: Partial<TaskRow> = {}): TaskRow {
  return {
    task_id: "01JTASK",
    title: "豆の発注",
    description: "",
    due_at: "2026-10-30T18:00:00+09:00",
    status: "todo",
    visibility: "member",
    related_activity_id: null,
    reminder_offsets: "",
    google_event_id: null,
    is_active: true,
    ...overrides,
  };
}

describe("eventIdFor", () => {
  it("uses only base32hex characters allowed by the Calendar API", () => {
    const id = eventIdFor("activity", "activity_abc123");
    expect(id).toMatch(/^[a-v0-9]{5,1024}$/);
  });

  it("is deterministic and distinguishes sources", () => {
    expect(eventIdFor("task", "x")).toBe(eventIdFor("task", "x"));
    expect(eventIdFor("task", "x")).not.toBe(eventIdFor("activity", "x"));
  });
});

describe("buildActivityEvent / buildTaskEvent", () => {
  it("computes the activity end from duration_min", () => {
    const event = buildActivityEvent(activity());
    expect(new Date(event.start!.dateTime).toISOString()).toBe("2026-11-01T05:00:00.000Z");
    expect(new Date(event.end!.dateTime).toISOString()).toBe("2026-11-01T06:30:00.000Z");
    expect(event.description).toContain("対象: 全員");
  });

  it("marks done tasks with a different color and prefix", () => {
    const open = buildTaskEvent(task());
    const done = buildTaskEvent(task({ status: "done" }));
    expect(open.colorId).not.toBe(done.colorId);
    expect(done.summary).toBe("✓ 豆の発注");
    expect(new Date(open.end!.dateTime).getTime()).toBeGreaterThan(new Date(open.start!.dateTime).getTime());
  });
});

describe("collectSyncTargets", () => {
  it("skips inactive rows and non-member tasks", () => {
    const targets = collectSyncTargets({
      activities: [
        { row: activity(), rowNumber: 2 },
        { row: activity({ activity_id: "gone", is_active: false }), rowNumber: 3 },
      ],
      tasks: [
        { row: task(), rowNumber: 2 },
        { row: task({ task_id: "officer-only", visibility: "officer" }), rowNumber: 3 },
        { row: task({ task_id: "admin-only", visibility: "admin" }), rowNumber: 4 },
      ],
    });
    expect(targets.map((t) => t.sourceId)).toEqual(["activity_abc123", "01JTASK"]);
  });
});

describe("locateRows", () => {
  it("keeps the original sheet row numbers when skipping broken rows", () => {
    const located = locateRows([{ v: "a" }, { v: "" }, { v: "c" }], (record) => (record.v ? record.v : null));
    expect(located).toEqual([
      { row: "a", rowNumber: 2 },
      { row: "c", rowNumber: 4 },
    ]);
  });
});

describe("isSameEvent", () => {
  it("compares times by instant, not by string form", () => {
    const desired = buildActivityEvent(activity());
    const actual: CalendarEvent = {
      ...desired,
      start: { dateTime: "2026-11-01T14:00:00+09:00" },
      end: { dateTime: "2026-11-01T15:30:00+09:00" },
    };
    expect(isSameEvent(desired, actual)).toBe(true);
  });

  it("detects a changed title", () => {
    const desired = buildActivityEvent(activity());
    expect(isSameEvent(desired, { ...desired, summary: "別の題名" })).toBe(false);
  });
});

describe("planCalendarSync", () => {
  const targets = collectSyncTargets({
    activities: [{ row: activity(), rowNumber: 2 }],
    tasks: [{ row: task(), rowNumber: 2 }],
  });
  const [activityTarget, taskTarget] = targets;

  it("inserts events that do not exist yet", () => {
    const ops = planCalendarSync(targets, []);
    expect(ops.map((op) => op.kind)).toEqual(["insert", "insert"]);
  });

  it("does nothing when the calendar already matches (no hourly rewrites)", () => {
    const ops = planCalendarSync(targets, [activityTarget!.event, taskTarget!.event]);
    expect(ops).toEqual([]);
  });

  it("updates only events whose content changed", () => {
    const stale = { ...activityTarget!.event, location: "旧部室" };
    const ops = planCalendarSync(targets, [stale, taskTarget!.event]);
    expect(ops).toEqual([{ kind: "update", target: activityTarget }]);
  });

  it("deletes managed events that are no longer wanted, but never human-made events", () => {
    const orphan = buildActivityEvent(activity({ activity_id: "deleted" }));
    const humanMade: CalendarEvent = { id: "manual1", summary: "部員が手で追加した予定" };
    const ops = planCalendarSync(targets, [activityTarget!.event, taskTarget!.event, orphan, humanMade]);
    expect(ops).toEqual([{ kind: "delete", eventId: orphan.id }]);
  });
});

function fakeDeps(overrides: Partial<CalendarSyncDeps> = {}): CalendarSyncDeps {
  return {
    insertEvent: vi.fn(async () => {}),
    updateEvent: vi.fn(async () => {}),
    deleteEvent: vi.fn(async () => {}),
    ...overrides,
  };
}

describe("executeCalendarSync", () => {
  const [target] = collectSyncTargets({ activities: [{ row: activity(), rowNumber: 2 }], tasks: [] });

  it("falls back to update when insert conflicts with a previously deleted event", async () => {
    const deps = fakeDeps({
      insertEvent: vi.fn(async () => {
        throw new CalendarApiError("conflict", 409);
      }),
    });
    const result = await executeCalendarSync([{ kind: "insert", target: target! }], deps, 10);
    expect(deps.updateEvent).toHaveBeenCalledWith(target!.event);
    expect(result.succeeded).toHaveLength(1);
    expect(result.failures).toHaveLength(0);
  });

  it("keeps going after a failure and reports it", async () => {
    const deps = fakeDeps({
      updateEvent: vi.fn(async () => {
        throw new CalendarApiError("boom", 500);
      }),
    });
    const ops: SyncOperation[] = [
      { kind: "update", target: target! },
      { kind: "delete", eventId: "tcdead" },
    ];
    const result = await executeCalendarSync(ops, deps, 10);
    expect(result.failures).toHaveLength(1);
    expect(result.succeeded).toEqual([{ kind: "delete", eventId: "tcdead" }]);
  });

  it("defers operations beyond the per-run write limit", async () => {
    const ops: SyncOperation[] = [1, 2, 3].map((n) => ({ kind: "delete", eventId: `tc${n}` }));
    const deps = fakeDeps();
    const result = await executeCalendarSync(ops, deps, 2);
    expect(deps.deleteEvent).toHaveBeenCalledTimes(2);
    expect(result.deferred).toBe(1);
  });
});

describe("computeEventIdWritebacks", () => {
  it("writes back ids only for events confirmed on the calendar and not yet recorded", () => {
    const targets = collectSyncTargets({
      activities: [
        { row: activity({ activity_id: "a-new" }), rowNumber: 2 },
        { row: activity({ activity_id: "a-failed" }), rowNumber: 3 },
        {
          row: activity({ activity_id: "a-synced", google_event_id: eventIdFor("activity", "a-synced") }),
          rowNumber: 4,
        },
        { row: activity({ activity_id: "a-existing-unrecorded" }), rowNumber: 5 },
      ],
      tasks: [],
    });
    const [newT, , syncedT, existingT] = targets;
    const succeeded: SyncOperation[] = [{ kind: "insert", target: newT! }];
    const writebacks = computeEventIdWritebacks(targets, [syncedT!.event, existingT!.event], succeeded);
    expect(writebacks).toEqual([
      { source: "activity", rowNumber: 2, eventId: newT!.event.id },
      { source: "activity", rowNumber: 5, eventId: existingT!.event.id },
    ]);
  });
});
