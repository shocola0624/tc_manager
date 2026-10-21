import { describe, expect, it } from "vitest";
import { parseActivityRow, parseAssigneeRow, parseReminderLogRow, parseTaskRow } from "./parsing";

describe("parseTaskRow", () => {
  const validRecord = {
    task_id: "t1",
    title: "資料作成",
    description: "",
    due_at: "2026-10-20T18:00:00+09:00",
    status: "todo",
    visibility: "member",
    related_activity_id: "",
    reminder_offsets: "-7d,-1d",
    google_event_id: "",
    is_active: "TRUE",
    created_by: "u1",
    created_at: "2026-01-01T00:00:00+09:00",
    updated_at: "2026-01-01T00:00:00+09:00",
  };

  it("parses a well-formed row", () => {
    expect(parseTaskRow(validRecord)).toEqual({
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
    });
  });

  it("treats an empty is_active cell as TRUE (CLAUDE.md: 空欄はTRUEとして扱う)", () => {
    expect(parseTaskRow({ ...validRecord, is_active: "" })?.is_active).toBe(true);
  });

  it("returns null when a required field is missing", () => {
    expect(parseTaskRow({ ...validRecord, task_id: "" })).toBeNull();
    expect(parseTaskRow({ ...validRecord, title: "" })).toBeNull();
    expect(parseTaskRow({ ...validRecord, due_at: "" })).toBeNull();
  });

  it("returns null for an unknown status or visibility code value", () => {
    expect(parseTaskRow({ ...validRecord, status: "not-a-status" })).toBeNull();
    expect(parseTaskRow({ ...validRecord, visibility: "not-a-role" })).toBeNull();
  });

  it("returns null for an unparseable due_at instead of throwing", () => {
    expect(parseTaskRow({ ...validRecord, due_at: "not-a-date" })).toBeNull();
  });
});

describe("parseAssigneeRow", () => {
  it("parses a member assignee", () => {
    expect(parseAssigneeRow({ task_id: "t1", member_id: "u1", label: "" })).toEqual({
      task_id: "t1",
      member_id: "u1",
      label: null,
    });
  });

  it("parses a department label assignee", () => {
    expect(parseAssigneeRow({ task_id: "t1", member_id: "", label: "広報部" })).toEqual({
      task_id: "t1",
      member_id: null,
      label: "広報部",
    });
  });

  it("returns null when both or neither member_id/label are set", () => {
    expect(parseAssigneeRow({ task_id: "t1", member_id: "u1", label: "広報部" })).toBeNull();
    expect(parseAssigneeRow({ task_id: "t1", member_id: "", label: "" })).toBeNull();
  });
});

describe("parseReminderLogRow", () => {
  it("parses a valid row", () => {
    expect(
      parseReminderLogRow({
        task_id: "t1",
        offset_key: "-7d",
        channel: "guild",
        member_id: "",
        sent_at: "2026-10-13T00:00:00+09:00",
      }),
    ).toEqual({ task_id: "t1", offset_key: "-7d", channel: "guild", member_id: "", sent_at: "2026-10-13T00:00:00+09:00" });
  });

  it("returns null for an unknown channel value", () => {
    expect(
      parseReminderLogRow({ task_id: "t1", offset_key: "-7d", channel: "email", member_id: "", sent_at: "" }),
    ).toBeNull();
  });
});

describe("parseActivityRow", () => {
  const validRecord = {
    activity_id: "activity_abc",
    starts_at: "2026-11-01T14:00:00+09:00",
    duration_min: "90",
    location: "部室",
    title: "練習会",
    description: "",
    target: "",
    owner_id: "u1",
    google_event_id: "",
    is_active: "",
  };

  it("parses a well-formed row", () => {
    expect(parseActivityRow(validRecord)).toMatchObject({
      activity_id: "activity_abc",
      duration_min: 90,
      google_event_id: null,
      is_active: true,
    });
  });

  it("returns null for a non-numeric duration (hand-edited cell)", () => {
    expect(parseActivityRow({ ...validRecord, duration_min: "1時間半" })).toBeNull();
  });

  it("returns null for an unparsable starts_at", () => {
    expect(parseActivityRow({ ...validRecord, starts_at: "来週" })).toBeNull();
  });
});
