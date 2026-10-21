import { describe, expect, it } from "vitest";
import { parseOffsets, serializeOffsets } from "./reminderOffsets";

describe("parseOffsets", () => {
  it("parses a comma-separated offset string", () => {
    expect(parseOffsets("-7d,-1d,-2h")).toEqual([
      { amount: 7, unit: "d" },
      { amount: 1, unit: "d" },
      { amount: 2, unit: "h" },
    ]);
  });

  it("returns an empty array for an empty string", () => {
    expect(parseOffsets("")).toEqual([]);
    expect(parseOffsets("   ")).toEqual([]);
  });

  it("skips segments that do not match the expected shape", () => {
    expect(parseOffsets("-7d,garbage,-2h")).toEqual([
      { amount: 7, unit: "d" },
      { amount: 2, unit: "h" },
    ]);
  });
});

describe("serializeOffsets", () => {
  it("serializes rows back into the canonical format", () => {
    expect(
      serializeOffsets([
        { amount: 7, unit: "d" },
        { amount: 2, unit: "h" },
      ]),
    ).toBe("-7d,-2h");
  });

  it("drops rows with a non-positive or non-finite amount", () => {
    expect(serializeOffsets([{ amount: 0, unit: "d" }, { amount: -1, unit: "h" }])).toBe("");
  });

  it("round-trips through parseOffsets", () => {
    const original = "-7d,-1d,-30m";
    expect(serializeOffsets(parseOffsets(original))).toBe(original);
  });
});
