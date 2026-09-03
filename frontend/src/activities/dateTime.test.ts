import { describe, expect, it } from "vitest";
import {
  combineDateAndTimeToJstIso,
  computeEndTimeIso,
  isUpcoming,
  splitJstIso,
} from "./dateTime";

describe("combineDateAndTimeToJstIso", () => {
  it("combines date and time into a JST-offset ISO string", () => {
    expect(combineDateAndTimeToJstIso("2026-09-10", "14:00")).toBe(
      "2026-09-10T14:00:00+09:00",
    );
  });
});

describe("splitJstIso", () => {
  it("is the inverse of combineDateAndTimeToJstIso", () => {
    const iso = combineDateAndTimeToJstIso("2026-09-10", "14:00");
    expect(splitJstIso(iso)).toEqual({ date: "2026-09-10", time: "14:00" });
  });

  it("returns empty strings for a malformed input", () => {
    expect(splitJstIso("not-a-date")).toEqual({ date: "", time: "" });
  });
});

describe("computeEndTimeIso", () => {
  it("adds duration_min to starts_at without mutating the stored value", () => {
    const end = computeEndTimeIso("2026-09-10T14:00:00+09:00", 90);
    // 14:00 JST + 90min = 15:30 JST = 06:30 UTC
    expect(end).toBe("2026-09-10T06:30:00.000Z");
  });
});

describe("isUpcoming", () => {
  it("is true when the activity has not ended yet", () => {
    const now = new Date("2026-09-10T05:00:00+09:00"); // 開始前
    expect(isUpcoming("2026-09-10T14:00:00+09:00", 60, now)).toBe(true);
  });

  it("is true while the activity is still ongoing", () => {
    const now = new Date("2026-09-10T14:30:00+09:00"); // 開催中
    expect(isUpcoming("2026-09-10T14:00:00+09:00", 60, now)).toBe(true);
  });

  it("is false once the activity has ended", () => {
    const now = new Date("2026-09-10T15:30:00+09:00"); // 終了後
    expect(isUpcoming("2026-09-10T14:00:00+09:00", 60, now)).toBe(false);
  });
});
