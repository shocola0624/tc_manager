import { describe, expect, it } from "vitest";
import { addMonths, dateKey, getMonthGrid, jstDateKeyFromIso } from "./monthGrid";

describe("dateKey", () => {
  it("formats a Date as YYYY-MM-DD with zero padding", () => {
    expect(dateKey(new Date(2026, 0, 5))).toBe("2026-01-05");
    expect(dateKey(new Date(2026, 9, 31))).toBe("2026-10-31");
  });
});

describe("jstDateKeyFromIso", () => {
  it("slices the date portion without any timezone conversion", () => {
    expect(jstDateKeyFromIso("2026-10-11T07:30:00+09:00")).toBe("2026-10-11");
  });
});

describe("getMonthGrid", () => {
  it("returns 42 days starting on a Sunday and ending on a Saturday", () => {
    const days = getMonthGrid({ year: 2026, month: 9 }); // October 2026
    expect(days).toHaveLength(42);
    expect(days[0].getDay()).toBe(0);
    expect(days[41].getDay()).toBe(6);
  });

  it("includes every day of the target month", () => {
    const days = getMonthGrid({ year: 2026, month: 9 });
    const octoberDays = days.filter((d) => d.getMonth() === 9 && d.getFullYear() === 2026);
    expect(octoberDays).toHaveLength(31);
  });
});

describe("addMonths", () => {
  it("moves forward and wraps the year", () => {
    expect(addMonths({ year: 2026, month: 11 }, 1)).toEqual({ year: 2027, month: 0 });
  });

  it("moves backward and wraps the year", () => {
    expect(addMonths({ year: 2026, month: 0 }, -1)).toEqual({ year: 2025, month: 11 });
  });
});
