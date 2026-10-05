import { describe, expect, it } from "vitest";
import { CIRCLE_OWNER_ID } from "../api/types";
import type { CurrentUser, Item } from "../api/types";
import { canEditItem, canSetOwnerCircle } from "./permissions";

function item(overrides: Partial<Item> = {}): Item {
  return {
    item_id: "item_1",
    owner_id: "u1",
    name: "V60",
    maker: "Hario",
    category: "dripper",
    storage: "owner",
    note: "",
    is_active: true,
    ...overrides,
  };
}

function user(overrides: Partial<CurrentUser> = {}): CurrentUser {
  return {
    discord_user_id: "u1",
    name: "Alice",
    role: "member",
    is_active: true,
    locale: "ja",
    grade: "",
    ...overrides,
  };
}

describe("canEditItem", () => {
  it("allows the owner to edit their own item", () => {
    expect(canEditItem(item({ owner_id: "u1" }), user({ discord_user_id: "u1" }))).toBe(true);
  });

  it("forbids a member from editing someone else's item", () => {
    expect(canEditItem(item({ owner_id: "u2" }), user({ discord_user_id: "u1" }))).toBe(false);
  });

  it("allows admin to edit someone else's item", () => {
    expect(
      canEditItem(item({ owner_id: "u2" }), user({ discord_user_id: "u1", role: "admin" })),
    ).toBe(true);
  });

  it("forbids officer from editing someone else's item", () => {
    expect(
      canEditItem(item({ owner_id: "u2" }), user({ discord_user_id: "u1", role: "officer" })),
    ).toBe(false);
  });

  it("allows officer to edit a circle-owned item", () => {
    expect(
      canEditItem(
        item({ owner_id: CIRCLE_OWNER_ID }),
        user({ discord_user_id: "u1", role: "officer" }),
      ),
    ).toBe(true);
  });

  it("forbids a member from editing a circle-owned item", () => {
    expect(
      canEditItem(
        item({ owner_id: CIRCLE_OWNER_ID }),
        user({ discord_user_id: "u1", role: "member" }),
      ),
    ).toBe(false);
  });
});

describe("canSetOwnerCircle", () => {
  it("allows admin and officer", () => {
    expect(canSetOwnerCircle(user({ role: "admin" }))).toBe(true);
    expect(canSetOwnerCircle(user({ role: "officer" }))).toBe(true);
  });

  it("forbids member", () => {
    expect(canSetOwnerCircle(user({ role: "member" }))).toBe(false);
  });
});
