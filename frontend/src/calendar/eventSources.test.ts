import { describe, expect, it } from "vitest";
import type { Activity, Task } from "../api/types";
import { activityToEvent, taskToEvent } from "./eventSources";

function activity(overrides: Partial<Activity> = {}): Activity {
  return {
    activity_id: "a1",
    starts_at: "2026-10-11T07:30:00+09:00",
    duration_min: 60,
    location: "",
    title: "工大祭",
    description: "",
    target: "",
    owner_id: "u1",
    tasks: "",
    note: "",
    announce_message_id: null,
    is_active: true,
    ...overrides,
  };
}

function task(overrides: Partial<Task> = {}): Task {
  return {
    task_id: "t1",
    title: "資料作成",
    description: "",
    due_at: "2026-10-20T18:00:00+09:00",
    status: "todo",
    visibility: "member",
    related_activity_id: null,
    reminder_offsets: "",
    google_event_id: null,
    is_active: true,
    created_by: "u1",
    created_at: "2026-01-01T00:00:00+09:00",
    updated_at: "2026-01-01T00:00:00+09:00",
    assignees: [],
    ...overrides,
  };
}

describe("activityToEvent", () => {
  it("maps fields and computes ends_at from duration_min", () => {
    const event = activityToEvent(activity({ duration_min: 90 }));
    expect(event.source).toBe("activity");
    expect(event.source_id).toBe("a1");
    expect(event.kind).toBe("activity");
    expect(event.starts_at).toBe("2026-10-11T07:30:00+09:00");
    expect(event.ends_at).toBeDefined();
  });
});

describe("taskToEvent", () => {
  it("uses due_at as starts_at and has no ends_at", () => {
    const event = taskToEvent(task());
    expect(event.source).toBe("task");
    expect(event.starts_at).toBe("2026-10-20T18:00:00+09:00");
    expect(event.ends_at).toBeUndefined();
  });

  it("marks done tasks with a distinct kind for muted display", () => {
    expect(taskToEvent(task({ status: "todo" })).kind).toBe("task");
    expect(taskToEvent(task({ status: "doing" })).kind).toBe("task");
    expect(taskToEvent(task({ status: "done" })).kind).toBe("task_done");
  });
});
