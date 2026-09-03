import { useMemo } from "react";
import { useUsers } from "../api/hooks";
import type { User } from "../api/types";

/**
 * discord_user_id -> name の解決に使う共通フック。items の所有者表示・activities の
 * 責任者表示など、複数機能で「結合ビュー」を作る際に使う(CLAUDE.md §1)。
 */
export function useUserDirectory() {
  const usersQuery = useUsers();

  const nameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const user of usersQuery.data?.data ?? []) {
      map.set(user.discord_user_id, user.name);
    }
    return map;
  }, [usersQuery.data]);

  const activeUsers: User[] = useMemo(
    () => (usersQuery.data?.data ?? []).filter((user) => user.is_active),
    [usersQuery.data],
  );

  return {
    nameById,
    activeUsers,
    isPending: usersQuery.isPending,
  };
}
