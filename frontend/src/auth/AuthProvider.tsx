import { createContext, useContext, useMemo, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { ApiError } from "../api/client";
import { authApi } from "../api/endpoints";
import type { CurrentUser } from "../api/types";

export type AuthStatus =
  | "loading"
  | "unauthenticated"
  | "pending"
  | "inactive"
  | "authenticated"
  | "error";

interface AuthContextValue {
  status: AuthStatus;
  user: CurrentUser | null;
  errorCode: string | null;
  refetch: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

/**
 * GET /auth/me の結果(または ApiError.code)を認証状態に正規化する。
 * 未ログイン/登録未完了/無効ユーザーの判定は auth/dependencies.py が返す
 * error.code(not_authenticated / registration_incomplete / inactive_user)による。
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const query = useQuery({
    queryKey: ["me"],
    queryFn: authApi.me,
    retry: false,
  });

  const value = useMemo<AuthContextValue>(() => {
    const refetch = () => {
      void query.refetch();
    };

    if (query.isPending) {
      return { status: "loading", user: null, errorCode: null, refetch };
    }
    if (query.isSuccess) {
      return { status: "authenticated", user: query.data, errorCode: null, refetch };
    }

    const code = query.error instanceof ApiError ? query.error.code : null;
    switch (code) {
      case "not_authenticated":
        return { status: "unauthenticated", user: null, errorCode: code, refetch };
      case "registration_incomplete":
        return { status: "pending", user: null, errorCode: code, refetch };
      case "inactive_user":
        return { status: "inactive", user: null, errorCode: code, refetch };
      default:
        return { status: "error", user: null, errorCode: code, refetch };
    }
    // query.refetch は TanStack Query が安定した参照を返すため依存配列に含めない
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.isPending, query.isSuccess, query.data, query.error]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
