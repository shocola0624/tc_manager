import type { CurrentUser } from "../api/types";

/** routers/activities.py の require_role(ADMIN, OFFICER) と同じ規則(CLAUDE.md §6 権限)。 */
export function canManageActivities(user: CurrentUser): boolean {
  return user.role === "admin" || user.role === "officer";
}
