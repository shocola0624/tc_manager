import type { CurrentUser, Role, Task } from "../api/types";

// member < officer < admin。閲覧・作成・担当者指定・ステータス変更・編集・削除の
// すべてを「自分のロールが visibility 以上か」という1つのチェックに統一する
// (backend/routers/tasks_permissions.py と対になる実装)。
const ROLE_RANK: Record<Role, number> = { member: 0, officer: 1, admin: 2 };

export function roleRank(role: Role): number {
  return ROLE_RANK[role];
}

export function canAccessVisibility(user: Pick<CurrentUser, "role">, visibility: Role): boolean {
  return roleRank(user.role) >= roleRank(visibility);
}

export function canCreateTaskAt(user: CurrentUser, visibility: Role): boolean {
  return canAccessVisibility(user, visibility);
}

export function canModifyTask(user: CurrentUser, task: Task): boolean {
  return canAccessVisibility(user, task.visibility);
}

/** 担当者候補の絞り込み用。担当者のロールが visibility 以上であること。 */
export function canAssignRole(assigneeRole: Role, visibility: Role): boolean {
  return roleRank(assigneeRole) >= roleRank(visibility);
}
