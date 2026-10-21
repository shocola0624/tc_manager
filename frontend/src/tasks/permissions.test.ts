import { describe, expect, it } from "vitest";
import type { CurrentUser, Role, Task } from "../api/types";
import { canAssignRole, canCreateTaskAt, canModifyTask, roleRank } from "./permissions";

function user(role: Role): CurrentUser {
  return {
    discord_user_id: "u1",
    name: "Alice",
    role,
    is_active: true,
    locale: "ja",
    grade: "",
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

describe("roleRank", () => {
  it("orders member < officer < admin", () => {
    expect(roleRank("member")).toBeLessThan(roleRank("officer"));
    expect(roleRank("officer")).toBeLessThan(roleRank("admin"));
  });
});

describe("canCreateTaskAt", () => {
  it("allows creating at or below own tier", () => {
    expect(canCreateTaskAt(user("officer"), "officer")).toBe(true);
    expect(canCreateTaskAt(user("officer"), "member")).toBe(true);
  });

  it("forbids creating above own tier", () => {
    expect(canCreateTaskAt(user("officer"), "admin")).toBe(false);
    expect(canCreateTaskAt(user("member"), "officer")).toBe(false);
  });
});

describe("canModifyTask", () => {
  it("allows editing a task at or below own tier", () => {
    expect(canModifyTask(user("admin"), task({ visibility: "officer" }))).toBe(true);
  });

  it("forbids editing a task above own tier", () => {
    expect(canModifyTask(user("member"), task({ visibility: "officer" }))).toBe(false);
  });
});

describe("canAssignRole", () => {
  it("allows a role at or above the visibility", () => {
    expect(canAssignRole("officer", "officer")).toBe(true);
    expect(canAssignRole("admin", "officer")).toBe(true);
  });

  it("forbids a role below the visibility", () => {
    expect(canAssignRole("member", "officer")).toBe(false);
  });
});
