import { describe, expect, it } from "vitest";
import { columnLetter, recordToRow, rowsToRecords } from "./sheets";

describe("rowsToRecords", () => {
  it("maps rows by header name, not position", () => {
    const rows = [
      ["task_id", "title", "status"],
      ["t1", "資料作成", "todo"],
      ["t2", "会場予約", "done"],
    ];
    expect(rowsToRecords(rows)).toEqual([
      { task_id: "t1", title: "資料作成", status: "todo" },
      { task_id: "t2", title: "会場予約", status: "done" },
    ]);
  });

  it("pads missing trailing cells with empty strings", () => {
    const rows = [
      ["task_id", "title", "status"],
      ["t1", "資料作成"],
    ];
    expect(rowsToRecords(rows)).toEqual([{ task_id: "t1", title: "資料作成", status: "" }]);
  });

  it("returns an empty array for a header-only or empty sheet", () => {
    expect(rowsToRecords([["task_id", "title"]])).toEqual([]);
    expect(rowsToRecords([])).toEqual([]);
  });

  it("ignores empty header cells", () => {
    const rows = [
      ["task_id", "", "status"],
      ["t1", "extra", "todo"],
    ];
    expect(rowsToRecords(rows)).toEqual([{ task_id: "t1", status: "todo" }]);
  });
});

describe("recordToRow", () => {
  it("orders values according to the given header, filling missing fields with empty strings", () => {
    const row = recordToRow({ task_id: "t1", status: "todo" }, ["task_id", "title", "status"]);
    expect(row).toEqual(["t1", "", "todo"]);
  });
});

describe("columnLetter", () => {
  it("converts zero-based indexes to A1 column names", () => {
    expect(columnLetter(0)).toBe("A");
    expect(columnLetter(25)).toBe("Z");
    expect(columnLetter(26)).toBe("AA");
    expect(columnLetter(27)).toBe("AB");
  });
});
