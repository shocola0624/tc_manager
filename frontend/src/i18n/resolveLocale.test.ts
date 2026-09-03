import { describe, expect, it } from "vitest";
import { resolveLocale } from "./resolveLocale";

describe("resolveLocale", () => {
  it("prefers users.locale when it is supported", () => {
    expect(resolveLocale("ja", ["en-US"])).toBe("ja");
  });

  it("falls back to browser languages when users.locale is missing", () => {
    expect(resolveLocale(null, ["fr-FR", "ja-JP"])).toBe("ja");
  });

  it("falls back to browser languages when users.locale is unsupported", () => {
    expect(resolveLocale("en", ["ja-JP"])).toBe("ja");
  });

  it("defaults to ja when nothing matches", () => {
    expect(resolveLocale(undefined, ["fr-FR", "de-DE"])).toBe("ja");
  });

  it("matches on the primary language subtag, ignoring region", () => {
    expect(resolveLocale("ja-JP", [])).toBe("ja");
  });
});
