import { useMemo, useState } from "react";
import { useDeleteTask, useTasks, useUpdateTask } from "../api/hooks";
import type { Task, TaskStatus } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
import { Button } from "../components/Button";
import { DetailHeader } from "../components/DetailHeader";
import { InvalidRowsWarning } from "../components/InvalidRowsWarning";
import { Modal } from "../components/Modal";
import { useI18n } from "../i18n/useI18n";
import { useUserDirectory } from "../users/useUserDirectory";
import { isTaskOverdue } from "./overdue";
import { TaskForm } from "./TaskForm";
import styles from "./TasksPage.module.css";

type Tab = "open" | "done";

const STATUS_OPTIONS: TaskStatus[] = ["todo", "doing", "done"];

type ModalState = { mode: "create" } | { mode: "edit"; task: Task } | null;

/** タスク一覧。visibility に応じて見える範囲はサーバー側で既に絞られているため
 * (GET /api/tasks)、ここに表示されているタスクは全員が編集・ステータス変更できる。 */
export function TasksPage() {
  const { t, formatDateTime } = useI18n();
  const { user } = useAuth();
  const tasksQuery = useTasks();
  const { nameById, activeUsers, isPending: usersPending } = useUserDirectory();
  const updateTask = useUpdateTask();
  const deleteTask = useDeleteTask();

  const [tab, setTab] = useState<Tab>("open");
  const [modal, setModal] = useState<ModalState>(null);

  const activeTasks = useMemo(
    () => (tasksQuery.data?.data ?? []).filter((task) => task.is_active),
    [tasksQuery.data],
  );

  const visibleTasks = useMemo(
    () =>
      activeTasks
        .filter((task) => (tab === "open" ? task.status !== "done" : task.status === "done"))
        .sort((a, b) => a.due_at.localeCompare(b.due_at)),
    [activeTasks, tab],
  );

  if (tasksQuery.isPending || usersPending || !user) {
    return <p>{t("common.loading")}</p>;
  }

  function closeModal() {
    setModal(null);
  }

  function handleDeleteFromModal(task: Task) {
    if (window.confirm(t("tasks.deleteConfirm"))) {
      deleteTask.mutate(task.task_id, { onSuccess: closeModal });
    }
  }

  return (
    <>
      <DetailHeader label={t("tasks.title")} fallbackTo="/" />
      <main>
        {tasksQuery.data && <InvalidRowsWarning invalidRows={tasksQuery.data.invalid_rows} />}

        <nav className={styles.tabs}>
          <button
            type="button"
            className={`${styles.tab} ${tab === "open" ? styles.tabActive : ""}`}
            onClick={() => setTab("open")}
          >
            {t("tasks.tabOpen")}
          </button>
          <button
            type="button"
            className={`${styles.tab} ${tab === "done" ? styles.tabActive : ""}`}
            onClick={() => setTab("done")}
          >
            {t("tasks.tabDone")}
          </button>
        </nav>

        <div className={styles.createSection}>
          <Button variant="cta" onClick={() => setModal({ mode: "create" })}>
            {t("tasks.addButton")}
          </Button>
        </div>

        {visibleTasks.length === 0 ? (
          <p className={styles.empty}>{t("tasks.emptyList")}</p>
        ) : (
          <ul className={styles.list}>
            {visibleTasks.map((task) => {
              const assigneeNames = task.assignees.map((assignee) =>
                assignee.member_id ? (nameById.get(assignee.member_id) ?? assignee.member_id) : assignee.label,
              );
              const overdue = isTaskOverdue(task);
              return (
                <li
                  key={task.task_id}
                  className={`${styles.row} ${overdue ? styles.row_overdue : styles[`row_${task.status}`]}`}
                >
                  <div className={styles.rowHeader}>
                    <div className={styles.rowHeaderLeft}>
                      <div className={`${styles.dateTime} ${overdue ? styles.dateTimeOverdue : ""}`}>
                        {formatDateTime(task.due_at, { month: "numeric", day: "numeric", weekday: "short" })}{" "}
                        {formatDateTime(task.due_at, { hour: "2-digit", minute: "2-digit", hourCycle: "h23" })}
                      </div>
                      <span className={styles.visibilityBadge}>{t(`roles.${task.visibility}`)}</span>
                    </div>
                    <button
                      type="button"
                      className={styles.editButton}
                      onClick={() => setModal({ mode: "edit", task })}
                    >
                      {t("tasks.editButton")}
                    </button>
                  </div>
                  <div className={styles.title}>{task.title}</div>
                  {task.description && <div className={styles.description}>{task.description}</div>}
                  <div className={styles.assignees}>
                    {t("tasks.formAssignees")}: {assigneeNames.length > 0 ? assigneeNames.join("、") : t("tasks.assigneesEmpty")}
                  </div>
                  <div className={styles.statusRow}>
                    {/* 現在のステータスの位置を固定し、押すたびにボタンの並びが変わらないようにする
                        (STATUS_OPTIONS の順序を常に維持し、現在値だけ見た目をバッジに変える)。 */}
                    {STATUS_OPTIONS.map((status) =>
                      status === task.status ? (
                        <span key={status} className={`${styles.statusBadge} ${styles[`statusBadge_${status}`]}`}>
                          {t(`tasks.status.${status}`)}
                        </span>
                      ) : (
                        <button
                          key={status}
                          type="button"
                          className={`${styles.statusButton} ${styles[`statusButton_${status}`]}`}
                          disabled={updateTask.isPending}
                          onClick={() => updateTask.mutate({ taskId: task.task_id, payload: { status } })}
                        >
                          {t(`tasks.statusAction.${status}`)}
                        </button>
                      ),
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </main>

      {modal && (
        <Modal
          title={modal.mode === "create" ? t("tasks.modalAddTitle") : t("tasks.modalEditTitle")}
          onClose={closeModal}
        >
          {modal.mode === "create" ? (
            <TaskForm mode="create" currentUser={user} activeUsers={activeUsers} onDone={closeModal} />
          ) : (
            <TaskForm
              mode="edit"
              task={modal.task}
              currentUser={user}
              activeUsers={activeUsers}
              onDone={closeModal}
              onRequestDelete={() => handleDeleteFromModal(modal.task)}
            />
          )}
        </Modal>
      )}
    </>
  );
}
