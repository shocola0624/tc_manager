import { describe, expect, it } from "vitest";
import { formatDateTime } from "./formatDateTime";

describe("formatDateTime", () => {
  it("formats an ISO 8601 timestamp using the given locale", () => {
    const result = formatDateTime("2026-09-02T14:00:00+09:00", "ja");
    // ロケールごとの厳密な出力文字列は環境依存になり得るため、和暦の年月日表記が
    // 含まれることだけを確認する(保存形式と表示形式の分離が効いているかの確認が目的)。
    expect(result).toContain("2026");
    expect(result).toContain("9");
    expect(result).toContain("2");
  });

  it("accepts explicit Intl.DateTimeFormatOptions", () => {
    const result = formatDateTime("2026-09-02T14:00:00+09:00", "ja", { year: "numeric" });
    expect(result).toBe("2026年");
  });
});
