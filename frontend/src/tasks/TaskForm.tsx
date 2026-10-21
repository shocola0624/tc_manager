import { useEffect, useMemo, useState, type FormEvent } from "react";
import { combineDateAndTimeToJstIso, splitJstIso } from "../activities/dateTime";
import { useActivities, useCreateTask, useTasks, useUpdateTask } from "../api/hooks";
import type { CurrentUser, Role, Task, TaskAssignee, User } from "../api/types";
import { AssigneeCombobox } from "./AssigneeCombobox";
import { Button } from "../components/Button";
import { useI18n } from "../i18n/useI18n";
import { canAssignRole, roleRank } from "./permissions";
import { ReminderOffsetsEditor } from "./ReminderOffsetsEditor";
import styles from "./TaskForm.module.css";

const VISIBILITY_OPTIONS: Role[] = ["member", "officer", "admin"];

interface TaskFormProps {
  mode: "create" | "edit";
  task?: Task;
  currentUser: CurrentUser;
  activeUsers: User[];
  onDone: () => void;
  /** 編集モードでのみ渡す。渡された場合、フォーム下部に削除ボタンを表示する。 */
  onRequestDelete?: () => void;
}

interface TaskDraft {
  title: string;
  description: string;
  date: string;
  time: string;
  visibility: Role;
  relatedActivityId: string;
  reminderOffsets: string;
  assignees: TaskAssignee[];
}

/** 新規作成中の下書きをブラウザに保存し、モーダルを誤って閉じても再度開けば続きから
 * 書けるようにする(CLAUDE.md §3: キャッシュはブラウザ側、activities の下書きと同じ方式)。
 * 編集フォームは対象にしない。 */
function draftStorageKey(currentUserId: string): string {
  return `tc-manager:task-draft:${currentUserId}`;
}

function loadDraft(currentUserId: string): TaskDraft | null {
  try {
    const raw = window.localStorage.getItem(draftStorageKey(currentUserId));
    return raw ? (JSON.parse(raw) as TaskDraft) : null;
  } catch {
    return null;
  }
}

function saveDraft(currentUserId: string, draft: TaskDraft): void {
  try {
    window.localStorage.setItem(draftStorageKey(currentUserId), JSON.stringify(draft));
  } catch {
    // プライベートブラウジング等で使えない場合、下書き保存はあきらめる(補助機能のため)。
  }
}

function clearDraft(currentUserId: string): void {
  try {
    window.localStorage.removeItem(draftStorageKey(currentUserId));
  } catch {
    // 上記と同様
  }
}

/** 自分のロール以下の visibility しか選べない(ユーザー要件: 下の階層は上の階層の
 * タスクを作成できない)。 */
function visibilityOptionsFor(user: CurrentUser): Role[] {
  return VISIBILITY_OPTIONS.filter((role) => roleRank(role) <= roleRank(user.role));
}

/** 作成・編集共通のフォーム。task_id はアプリが採番するため入力項目に含めない。 */
export function TaskForm({ mode, task, currentUser, activeUsers, onDone, onRequestDelete }: TaskFormProps) {
  const { t, formatDateTime } = useI18n();
  const createTask = useCreateTask();
  const updateTask = useUpdateTask();
  const activitiesQuery = useActivities();
  const tasksQuery = useTasks();

  const initialSplit = task ? splitJstIso(task.due_at) : { date: "", time: "" };
  const [draft] = useState<TaskDraft | null>(() =>
    mode === "create" ? loadDraft(currentUser.discord_user_id) : null,
  );

  const [title, setTitle] = useState(task?.title ?? draft?.title ?? "");
  const [description, setDescription] = useState(task?.description ?? draft?.description ?? "");
  const [date, setDate] = useState(draft?.date ?? initialSplit.date);
  const [time, setTime] = useState(draft?.time ?? initialSplit.time);
  const [visibility, setVisibility] = useState<Role>(task?.visibility ?? draft?.visibility ?? "member");
  const [relatedActivityId, setRelatedActivityId] = useState(
    task?.related_activity_id ?? draft?.relatedActivityId ?? "",
  );
  const [reminderOffsets, setReminderOffsets] = useState(task?.reminder_offsets ?? draft?.reminderOffsets ?? "");
  const [assignees, setAssignees] = useState<TaskAssignee[]>(task?.assignees ?? draft?.assignees ?? []);

  useEffect(() => {
    if (mode !== "create") return;
    saveDraft(currentUser.discord_user_id, {
      title,
      description,
      date,
      time,
      visibility,
      relatedActivityId,
      reminderOffsets,
      assignees,
    });
  }, [mode, currentUser.discord_user_id, title, description, date, time, visibility, relatedActivityId, reminderOffsets, assignees]);

  const visibilityOptions = visibilityOptionsFor(currentUser);
  const nameById = useMemo(
    () => new Map(activeUsers.map((activeUser) => [activeUser.discord_user_id, activeUser.name])),
    [activeUsers],
  );

  const assignableUsers = useMemo(
    () => activeUsers.filter((candidate) => canAssignRole(candidate.role, visibility)),
    [activeUsers, visibility],
  );

  // 過去に使われた部門名などのラベルをサジェスト候補にする(タスク横断で集計)。
  const knownLabels = useMemo(() => {
    const labels = new Set<string>();
    for (const existingTask of tasksQuery.data?.data ?? []) {
      for (const assignee of existingTask.assignees) {
        if (assignee.label) labels.add(assignee.label);
      }
    }
    return Array.from(labels).sort();
  }, [tasksQuery.data]);

  const pending = createTask.isPending || updateTask.isPending;
  const error = mode === "create" ? createTask.error : updateTask.error;

  function handleVisibilityChange(next: Role) {
    setVisibility(next);
    // 可視性を上げると担当者候補から外れる人がいるため、選択を候補内に絞り直す
    // (壊れにくい設計: サーバー側のバリデーションに頼らず、入力の時点で矛盾を作らせない)。
    // 部門名などの自由記述(label)はロールを持たないため対象外。
    setAssignees((current) =>
      current.filter((assignee) => {
        if (assignee.member_id === null) return true;
        const candidate = activeUsers.find((activeUser) => activeUser.discord_user_id === assignee.member_id);
        return candidate !== undefined && canAssignRole(candidate.role, next);
      }),
    );
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const payload = {
      title,
      description,
      due_at: combineDateAndTimeToJstIso(date, time),
      visibility,
      related_activity_id: relatedActivityId || null,
      reminder_offsets: reminderOffsets,
      assignees,
    };

    if (mode === "create") {
      createTask.mutate(payload, {
        onSuccess: () => {
          clearDraft(currentUser.discord_user_id);
          onDone();
        },
      });
    } else if (task) {
      updateTask.mutate({ taskId: task.task_id, payload }, { onSuccess: onDone });
    }
  }

  const activeActivities = (activitiesQuery.data?.data ?? []).filter((activity) => activity.is_active);

  return (
    <form onSubmit={handleSubmit}>
      <div className={styles.fields}>
        <label>
          {t("tasks.formTitle")}
          <input value={title} onChange={(event) => setTitle(event.target.value)} required minLength={1} />
        </label>
        <label>
          {t("tasks.formDescription")}
          <textarea value={description} onChange={(event) => setDescription(event.target.value)} />
        </label>
        <label>
          {t("tasks.formDueDate")}
          <input type="date" value={date} onChange={(event) => setDate(event.target.value)} required />
        </label>
        <label>
          {t("tasks.formDueTime")}
          <input type="time" value={time} onChange={(event) => setTime(event.target.value)} required />
        </label>
        <label>
          {t("tasks.formVisibility")}
          <select value={visibility} onChange={(event) => handleVisibilityChange(event.target.value as Role)}>
            {visibilityOptions.map((role) => (
              <option key={role} value={role}>
                {t(`roles.${role}`)}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t("tasks.formRelatedActivity")}
          <select value={relatedActivityId} onChange={(event) => setRelatedActivityId(event.target.value)}>
            <option value="">{t("tasks.formRelatedActivityNone")}</option>
            {activeActivities.map((activity) => (
              <option key={activity.activity_id} value={activity.activity_id}>
                {activity.title}（{formatDateTime(activity.starts_at, { month: "numeric", day: "numeric" })}）
              </option>
            ))}
          </select>
        </label>

        <div className={styles.assigneeField}>
          <span className={styles.assigneeLabel}>{t("tasks.formAssignees")}</span>
          <AssigneeCombobox
            value={assignees}
            onChange={setAssignees}
            candidateUsers={assignableUsers}
            knownLabels={knownLabels}
            nameById={nameById}
          />
        </div>

        <div className={styles.offsetsField}>
          <span className={styles.assigneeLabel}>{t("tasks.reminderOffsetsLabel")}</span>
          <ReminderOffsetsEditor value={reminderOffsets} onChange={setReminderOffsets} />
        </div>
      </div>

      <div className={styles.footer}>
        <Button type="button" variant="secondary" onClick={onDone}>
          {t("tasks.cancelButton")}
        </Button>
        <Button type="submit" variant="primary" disabled={pending}>
          {t("tasks.saveButton")}
        </Button>
      </div>
      {mode === "edit" && onRequestDelete && (
        <Button type="button" variant="warn" className={styles.deleteButton} onClick={onRequestDelete}>
          {t("tasks.deleteButton")}
        </Button>
      )}
      {error && (
        <p role="alert" className={styles.error}>
          {t(`errors.${error.code}`)}
        </p>
      )}
    </form>
  );
}
