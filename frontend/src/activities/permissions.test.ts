import { describe, expect, it } from "vitest";
import type { CurrentUser } from "../api/types";
import { canManageActivities } from "./permissions";

function user(role: CurrentUser["role"]): CurrentUser {
  return {
    discord_user_id: "u1",
    name: "Alice",
    role,
    is_active: true,
    locale: "ja",
    grade: "",
  };
}

describe("canManageActivities", () => {
  it("allows admin and officer", () => {
    expect(canManageActivities(user("admin"))).toBe(true);
    expect(canManageActivities(user("officer"))).toBe(true);
  });

  it("forbids member", () => {
    expect(canManageActivities(user("member"))).toBe(false);
  });
});
