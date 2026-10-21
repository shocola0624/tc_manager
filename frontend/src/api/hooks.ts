import { useMutation, useQueryClient, useQuery } from "@tanstack/react-query";
import type { ApiError } from "./client";
import {
  activitiesApi,
  assignmentsApi,
  attendanceApi,
  budgetItemsApi,
  itemsApi,
  tasksApi,
  usersApi,
} from "./endpoints";
import type {
  Activity,
  ActivityCreateRequest,
  ActivityUpdateRequest,
  AssignmentAddRequest,
  AssignmentLogEntry,
  AssignmentRemoveRequest,
  Attendance,
  AttendanceStatus,
  BudgetItem,
  BudgetItemCreateRequest,
  Item,
  ItemCreateRequest,
  ItemUpdateRequest,
  Task,
  TaskCreateRequest,
  TaskUpdateRequest,
} from "./types";

// queryClient の defaultOptions(staleTime: Infinity など)に乗るので、
// 個々のフックで再取得系オプションを繰り返す必要はない。

export function useUsers() {
  return useQuery({ queryKey: ["users"], queryFn: usersApi.list });
}

export function useItems() {
  return useQuery({ queryKey: ["items"], queryFn: itemsApi.list });
}

export function useActivities() {
  return useQuery({ queryKey: ["activities"], queryFn: activitiesApi.list });
}

// ホーム画面向けの軽量版(CLAUDE.md §9)。["activities"] を接頭辞に持つため、
// 通常の useActivities() 用の invalidateQueries(["activities"]) でまとめて再検証される
// (useAssignmentCandidates 等と同じ命名規約)。
export function useCurrentWindowActivities() {
  return useQuery({ queryKey: ["activities", "current-window"], queryFn: activitiesApi.currentWindow });
}

export function useAttendance() {
  return useQuery({ queryKey: ["attendance"], queryFn: attendanceApi.list });
}

// useCurrentWindowActivities() と同じ位置づけ(CLAUDE.md §9)。
export function useCurrentWindowAttendance() {
  return useQuery({ queryKey: ["attendance", "current-window"], queryFn: attendanceApi.currentWindow });
}

export function useAssignmentLog() {
  return useQuery({ queryKey: ["assignments"], queryFn: assignmentsApi.list });
}

// 追記専用ログを畳み込んだ現在の割り当て状態(CLAUDE.md §4)。activity_id でのフィルターは
// useAttendance() 同様、呼び出し側でキャッシュ済みデータに対して行う。
export function useCurrentAssignments() {
  return useQuery({ queryKey: ["assignments", "current"], queryFn: assignmentsApi.current });
}

// 候補一覧(CLAUDE.md §5)は出欠状況に依存するため activity_id ごと・拡張モードの
// on/off ごとにキャッシュする。カテゴリー/所有者フィルターは呼び出し側でこの結果に対して行う。
export function useAssignmentCandidates(activityId: string, extended: boolean) {
  return useQuery({
    queryKey: ["assignments", "candidates", activityId, extended],
    queryFn: () => assignmentsApi.candidates(activityId, extended),
  });
}

// 書き込み成功時は該当 queryKey だけを invalidate する規約(CLAUDE.md §3)。

export function useCreateItem() {
  const queryClient = useQueryClient();
  return useMutation<Item, ApiError, ItemCreateRequest>({
    mutationFn: (payload) => itemsApi.create(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["items"] });
    },
  });
}

export function useUpdateItem() {
  const queryClient = useQueryClient();
  return useMutation<Item, ApiError, { itemId: string; payload: ItemUpdateRequest }>({
    mutationFn: ({ itemId, payload }) => itemsApi.update(itemId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["items"] });
    },
  });
}

export function useDeleteItem() {
  const queryClient = useQueryClient();
  return useMutation<Item, ApiError, string>({
    mutationFn: (itemId) => itemsApi.remove(itemId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["items"] });
    },
  });
}

export function useCreateActivity() {
  const queryClient = useQueryClient();
  return useMutation<Activity, ApiError, ActivityCreateRequest>({
    mutationFn: (payload) => activitiesApi.create(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["activities"] });
    },
  });
}

export function useUpdateActivity() {
  const queryClient = useQueryClient();
  return useMutation<Activity, ApiError, { activityId: string; payload: ActivityUpdateRequest }>({
    mutationFn: ({ activityId, payload }) => activitiesApi.update(activityId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["activities"] });
    },
  });
}

export function useDeleteActivity() {
  const queryClient = useQueryClient();
  return useMutation<Activity, ApiError, string>({
    mutationFn: (activityId) => activitiesApi.remove(activityId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["activities"] });
    },
  });
}

export function useAnnounceActivity() {
  const queryClient = useQueryClient();
  return useMutation<Activity, ApiError, string>({
    mutationFn: (activityId) => activitiesApi.announce(activityId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["activities"] });
    },
  });
}

export function useConfirmActivity() {
  const queryClient = useQueryClient();
  return useMutation<Activity, ApiError, string>({
    mutationFn: (activityId) => activitiesApi.confirm(activityId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["activities"] });
    },
  });
}

export function useSetAttendance() {
  const queryClient = useQueryClient();
  return useMutation<Attendance, ApiError, { activityId: string; status: AttendanceStatus }>({
    mutationFn: ({ activityId, status }) => attendanceApi.setMine(activityId, status),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["attendance"] });
    },
  });
}

// ["assignments"] を invalidate すると ["assignments", "current"] / ["assignments", "candidates", ...]
// もプレフィックス一致でまとめて再検証される。

export function useAddAssignment() {
  const queryClient = useQueryClient();
  return useMutation<AssignmentLogEntry, ApiError, AssignmentAddRequest>({
    mutationFn: (payload) => assignmentsApi.add(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["assignments"] });
    },
  });
}

export function useRemoveAssignment() {
  const queryClient = useQueryClient();
  return useMutation<AssignmentLogEntry, ApiError, AssignmentRemoveRequest>({
    mutationFn: (payload) => assignmentsApi.remove(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["assignments"] });
    },
  });
}

export function useBudgetItems() {
  return useQuery({ queryKey: ["budgetItems"], queryFn: budgetItemsApi.list });
}

export function useCreateBudgetItem() {
  const queryClient = useQueryClient();
  return useMutation<BudgetItem, ApiError, BudgetItemCreateRequest>({
    mutationFn: (payload) => budgetItemsApi.create(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["budgetItems"] });
    },
  });
}

export function useDeleteBudgetItem() {
  const queryClient = useQueryClient();
  return useMutation<BudgetItem, ApiError, string>({
    mutationFn: (budgetItemId) => budgetItemsApi.remove(budgetItemId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["budgetItems"] });
    },
  });
}

export function useTasks() {
  return useQuery({ queryKey: ["tasks"], queryFn: tasksApi.list });
}

export function useCreateTask() {
  const queryClient = useQueryClient();
  return useMutation<Task, ApiError, TaskCreateRequest>({
    mutationFn: (payload) => tasksApi.create(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["tasks"] });
    },
  });
}

export function useUpdateTask() {
  const queryClient = useQueryClient();
  return useMutation<Task, ApiError, { taskId: string; payload: TaskUpdateRequest }>({
    mutationFn: ({ taskId, payload }) => tasksApi.update(taskId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["tasks"] });
    },
  });
}

export function useDeleteTask() {
  const queryClient = useQueryClient();
  return useMutation<Task, ApiError, string>({
    mutationFn: (taskId) => tasksApi.remove(taskId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["tasks"] });
    },
  });
}
