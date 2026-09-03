import { API_BASE, apiClient } from "./client";
import type {
  Activity,
  ActivityCreateRequest,
  ActivityUpdateRequest,
  Attendance,
  AttendanceStatus,
  AttendanceUpdateRequest,
  AssignmentAddRequest,
  AssignmentLogEntry,
  AssignmentRemoveRequest,
  AssignmentSlot,
  BudgetItem,
  BudgetItemCreateRequest,
  CurrentUser,
  Item,
  ItemCandidate,
  ItemCreateRequest,
  ItemUpdateRequest,
  ListResponse,
  User,
} from "./types";

export const authApi = {
  me: () => apiClient.get<CurrentUser>("/auth/me"),
  register: (name: string) => apiClient.post<CurrentUser>("/auth/register", { name }),
  logout: () => apiClient.post<{ ok: boolean }>("/auth/logout"),
  // OAuth はリダイレクトを伴う実ナビゲーションであり fetch では扱わない。
  // <a href={authApi.loginUrl()}> のように使う。
  loginUrl: () => `${API_BASE}/auth/discord/login`,
};

export const usersApi = {
  list: () => apiClient.get<ListResponse<User>>("/api/users"),
};

export const itemsApi = {
  list: () => apiClient.get<ListResponse<Item>>("/api/items"),
  create: (payload: ItemCreateRequest) => apiClient.post<Item>("/api/items", payload),
  update: (itemId: string, payload: ItemUpdateRequest) =>
    apiClient.patch<Item>(`/api/items/${encodeURIComponent(itemId)}`, payload),
  remove: (itemId: string) => apiClient.delete<Item>(`/api/items/${encodeURIComponent(itemId)}`),
};

export const activitiesApi = {
  list: () => apiClient.get<ListResponse<Activity>>("/api/activities"),
  create: (payload: ActivityCreateRequest) =>
    apiClient.post<Activity>("/api/activities", payload),
  update: (activityId: string, payload: ActivityUpdateRequest) =>
    apiClient.patch<Activity>(`/api/activities/${encodeURIComponent(activityId)}`, payload),
  remove: (activityId: string) =>
    apiClient.delete<Activity>(`/api/activities/${encodeURIComponent(activityId)}`),
  announce: (activityId: string) =>
    apiClient.post<Activity>(`/api/activities/${encodeURIComponent(activityId)}/announce`),
  confirm: (activityId: string) =>
    apiClient.post<Activity>(`/api/activities/${encodeURIComponent(activityId)}/confirm`),
};

export const attendanceApi = {
  list: () => apiClient.get<ListResponse<Attendance>>("/api/attendance"),
  setMine: (activityId: string, status: AttendanceStatus) =>
    apiClient.put<Attendance>(`/api/attendance/${encodeURIComponent(activityId)}`, {
      status,
    } satisfies AttendanceUpdateRequest),
};

export const assignmentsApi = {
  list: () => apiClient.get<ListResponse<AssignmentLogEntry>>("/api/assignments"),
  current: () => apiClient.get<AssignmentSlot[]>("/api/assignments/current"),
  candidates: (activityId: string, extended: boolean) =>
    apiClient.get<ItemCandidate[]>(
      `/api/assignments/candidates?${new URLSearchParams({
        activity_id: activityId,
        extended: String(extended),
      }).toString()}`,
    ),
  add: (payload: AssignmentAddRequest) =>
    apiClient.post<AssignmentLogEntry>("/api/assignments", payload),
  remove: (payload: AssignmentRemoveRequest) =>
    apiClient.post<AssignmentLogEntry>("/api/assignments/remove", payload),
};

export const budgetItemsApi = {
  list: () => apiClient.get<ListResponse<BudgetItem>>("/api/budget-items"),
  create: (payload: BudgetItemCreateRequest) =>
    apiClient.post<BudgetItem>("/api/budget-items", payload),
  remove: (budgetItemId: string) =>
    apiClient.delete<BudgetItem>(`/api/budget-items/${encodeURIComponent(budgetItemId)}`),
};
