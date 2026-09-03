import { describe, expect, it } from "vitest";
import { ApiError, parseErrorEnvelope } from "./client";

describe("parseErrorEnvelope", () => {
  it("extracts code and detail from a well-formed error envelope", () => {
    expect(parseErrorEnvelope({ error: { code: "not_authenticated", detail: "no session" } })).toEqual(
      { code: "not_authenticated", detail: "no session" },
    );
  });

  it("defaults detail to null when absent", () => {
    expect(parseErrorEnvelope({ error: { code: "not_found" } })).toEqual({
      code: "not_found",
      detail: null,
    });
  });

  it("falls back to unknown_error for a body with no error field", () => {
    expect(parseErrorEnvelope({ detail: "legacy shape" })).toEqual({
      code: "unknown_error",
      detail: null,
    });
  });

  it("falls back to unknown_error for null or non-object bodies", () => {
    expect(parseErrorEnvelope(null)).toEqual({ code: "unknown_error", detail: null });
    expect(parseErrorEnvelope("plain text")).toEqual({ code: "unknown_error", detail: null });
  });
});

describe("ApiError", () => {
  it("carries status, code and detail", () => {
    const error = new ApiError(403, "insufficient_role", "nope");
    expect(error.status).toBe(403);
    expect(error.code).toBe("insufficient_role");
    expect(error.detail).toBe("nope");
    expect(error.message).toBe("insufficient_role: nope");
  });

  it("omits the detail suffix in the message when detail is null", () => {
    const error = new ApiError(401, "not_authenticated", null);
    expect(error.message).toBe("not_authenticated");
  });
});
