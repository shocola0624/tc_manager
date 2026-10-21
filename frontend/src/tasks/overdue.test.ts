import { describe, expect, it } from "vitest";
import { isTaskOverdue } from "./overdue";

const NOW = new Date("2026-10-20T12:00:00+09:00");

describe("isTaskOverdue", () => {
  it("is true when due_at is in the past and status is not done", () => {
    expect(isTaskOverdue({ due_at: "2026-10-19T12:00:00+09:00", status: "todo" }, NOW)).toBe(true);
    expect(isTaskOverdue({ due_at: "2026-10-19T12:00:00+09:00", status: "doing" }, NOW)).toBe(true);
  });

  it("is false when due_at is in the future", () => {
    expect(isTaskOverdue({ due_at: "2026-10-21T12:00:00+09:00", status: "todo" }, NOW)).toBe(false);
  });

  it("is false for done tasks even if due_at is in the past", () => {
    expect(isTaskOverdue({ due_at: "2026-10-19T12:00:00+09:00", status: "done" }, NOW)).toBe(false);
  });
});
