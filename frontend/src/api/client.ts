export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly detail: string | null;

  constructor(status: number, code: string, detail: string | null) {
    super(detail ? `${code}: ${detail}` : code);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

/**
 * errors.py の install_exception_handlers が返す {"error": {"code", "detail"}} 形式を
 * 正規化する。すでに JSON.parse 済みの値を受け取る純粋関数(fetch へは依存しない)。
 */
export function parseErrorEnvelope(body: unknown): { code: string; detail: string | null } {
  if (
    body !== null &&
    typeof body === "object" &&
    "error" in body &&
    (body as { error: unknown }).error !== null &&
    typeof (body as { error: unknown }).error === "object"
  ) {
    const err = (body as { error: Record<string, unknown> }).error;
    return {
      code: typeof err.code === "string" ? err.code : "unknown_error",
      detail: typeof err.detail === "string" ? err.detail : null,
    };
  }
  return { code: "unknown_error", detail: null };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    // session cookie(HttpOnly)を送るために必須。バックエンドの CORS 設定
    // (allow_credentials=True + 単一オリジン許可)と対になっている。
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });

  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      // ボディなし(空レスポンス等)はそのまま unknown_error 扱いにする
    }
    const { code, detail } = parseErrorEnvelope(body);
    throw new ApiError(response.status, code, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const apiClient = {
  get: <T>(path: string): Promise<T> => request<T>(path),
  post: <T>(path: string, body?: unknown): Promise<T> =>
    request<T>(path, {
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  patch: <T>(path: string, body?: unknown): Promise<T> =>
    request<T>(path, {
      method: "PATCH",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  put: <T>(path: string, body?: unknown): Promise<T> =>
    request<T>(path, {
      method: "PUT",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  delete: <T>(path: string): Promise<T> => request<T>(path, { method: "DELETE" }),
};
