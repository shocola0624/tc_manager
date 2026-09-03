import { describe, expect, it, vi } from "vitest";
import { createTranslator } from "./t";

describe("createTranslator", () => {
  it("resolves a nested dot-path key from the ja dictionary", () => {
    const t = createTranslator("ja");
    expect(t("auth.loginButton")).toBe("Discordでログイン");
  });

  it("interpolates {param} placeholders", () => {
    const t = createTranslator("ja");
    expect(t("invalidRows.title", { count: 3 })).toBe("3件の不正な行があります");
  });

  it("returns the key itself when the translation is missing", () => {
    const t = createTranslator("ja");
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});

    expect(t("nonexistent.key")).toBe("nonexistent.key");

    warn.mockRestore();
  });

  it("leaves unknown placeholders untouched", () => {
    const t = createTranslator("ja");
    expect(t("invalidRows.rowLabel", {})).toBe("{row}行目");
  });
});
