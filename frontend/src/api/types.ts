// バックエンドの Pydantic モデルに対応する型(手書き)。フィールド名は API の JSON と
// 同じ snake_case のまま揃え、変換レイヤーを挟まない。

export type Role = "admin" | "officer" | "member";
export type Category =
  | "dripper"
  | "grinder"
  | "scale"
  | "kettle"
  | "pot"
  | "scoop"
  | "thermometer"
  | "server"
  | "other";
export type Storage = "clubroom" | "owner" | "other";
export type AttendanceStatus = "attending" | "absent" | "undecided";
export type AssignmentAction = "add" | "remove";

// items.owner_id / assignments.assignee_id で「個人ではなくサークル所有」を表す特別値
export const CIRCLE_OWNER_ID = "CIRCLE";

export interface User {
  discord_user_id: string;
  name: string;
  role: Role;
  is_active: boolean;
  locale: string;
  registered_at: string | null;
  grade: string;
}

export interface Item {
  item_id: string;
  owner_id: string;
  name: string;
  maker: string;
  category: Category;
  storage: Storage;
  note: string;
  is_active: boolean;
}

// routers/items_schemas.py の ItemCreateRequest に対応
export interface ItemCreateRequest {
  name: string;
  maker: string;
  category: Category;
  storage: Storage;
  note: string;
  owner_id?: string;
}

// routers/items_schemas.py の ItemUpdateRequest に対応
export interface ItemUpdateRequest {
  name?: string;
  maker?: string;
  category?: Category;
  storage?: Storage;
  note?: string;
}

export interface Activity {
  activity_id: string;
  starts_at: string;
  duration_min: number;
  location: string;
  title: string;
  description: string;
  target: string;
  owner_id: string;
  tasks: string;
  note: string;
  announce_message_id: string | null;
  is_active: boolean;
}

// routers/activities_schemas.py の ActivityCreateRequest に対応
export interface ActivityCreateRequest {
  starts_at: string;
  duration_min: number;
  location: string;
  title: string;
  description: string;
  target: string;
  owner_id: string;
  tasks: string;
  note: string;
}

// routers/activities_schemas.py の ActivityUpdateRequest に対応
export interface ActivityUpdateRequest {
  starts_at?: string;
  duration_min?: number;
  location?: string;
  title?: string;
  description?: string;
  target?: string;
  owner_id?: string;
  tasks?: string;
  note?: string;
}

// sheets/schemas/budget_items.py の BudgetItem に対応。予算は「豆 1000円」のような
// 自由記述ラベル+金額を複数持てるよう、単一の budget_jpy ではなくこの一覧で表す。
export interface BudgetItem {
  budget_item_id: string;
  activity_id: string;
  label: string;
  amount_jpy: number;
  is_active: boolean;
}

// routers/budget_items_schemas.py の BudgetItemCreateRequest に対応
export interface BudgetItemCreateRequest {
  activity_id: string;
  label: string;
  amount_jpy: number;
}

export interface Attendance {
  activity_id: string;
  discord_user_id: string;
  status: AttendanceStatus;
  updated_at: string;
}

// routers/attendance_schemas.py の AttendanceUpdateRequest に対応
export interface AttendanceUpdateRequest {
  status: AttendanceStatus;
}

export interface AssignmentLogEntry {
  timestamp: string;
  activity_id: string;
  item_id: string | null;
  custom_name: string | null;
  assignee_id: string | null;
  action: AssignmentAction;
  actor_id: string;
}

// sheets/assignments_state.py の AssignmentSlot(畳み込み後の現在の割り当て)に対応
export interface AssignmentSlot {
  activity_id: string;
  item_id: string | null;
  custom_name: string | null;
  assignee_id: string | null;
  last_action_at: string;
  last_actor_id: string;
}

// routers/assignments_schemas.py の ItemCandidateOut に対応
export interface ItemCandidate {
  item: Item;
  requires_assignee: boolean;
  default_assignee_id: string | null;
}

// routers/assignments_schemas.py の AssignmentAddRequest に対応
export interface AssignmentAddRequest {
  activity_id: string;
  item_id?: string;
  custom_name?: string;
  assignee_id?: string;
}

// routers/assignments_schemas.py の AssignmentRemoveRequest に対応
export interface AssignmentRemoveRequest {
  activity_id: string;
  item_id?: string;
  custom_name?: string;
}

export interface InvalidRowOut {
  row_number: number;
  raw: Record<string, string>;
  reason: string;
}

export interface ListResponse<T> {
  data: T[];
  invalid_rows: InvalidRowOut[];
}

// auth/schemas.py の CurrentUserResponse に対応
export interface CurrentUser {
  discord_user_id: string;
  name: string;
  role: Role;
  is_active: boolean;
  locale: string;
  grade: string;
}

// auth/schemas.py の UpdateProfileRequest に対応
export interface UpdateProfileRequest {
  name: string;
  grade: string;
}

export interface ErrorBody {
  code: string;
  detail: string | null;
}
