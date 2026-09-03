import { useMemo, useState, type FormEvent } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import {
  useActivities,
  useAddAssignment,
  useAnnounceActivity,
  useAttendance,
  useBudgetItems,
  useConfirmActivity,
  useCreateBudgetItem,
  useCurrentAssignments,
  useDeleteActivity,
  useDeleteBudgetItem,
  useItems,
  useRemoveAssignment,
  useSetAttendance,
} from "../api/hooks";
import type { AssignmentSlot, AttendanceStatus, Item } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
import { Button } from "../components/Button";
import { DetailHeader } from "../components/DetailHeader";
import { Modal } from "../components/Modal";
import { useI18n } from "../i18n/useI18n";
import { useUserDirectory } from "../users/useUserDirectory";
import { ActivityForm } from "./ActivityForm";
import styles from "./ActivityDetailPage.module.css";
import { computeEndTimeIso } from "./dateTime";
import { canManageActivities } from "./permissions";

/** 活動詳細画面。「準備が整っているかどうか」が主役(screen-reference.dc.html 画面2)。 */
export function ActivityDetailPage() {
  const { activityId } = useParams<{ activityId: string }>();
  const navigate = useNavigate();
  const { t, formatDateTime } = useI18n();
  const { user } = useAuth();

  const activitiesQuery = useActivities();
  const attendanceQuery = useAttendance();
  const assignmentsQuery = useCurrentAssignments();
  const itemsQuery = useItems();
  const budgetItemsQuery = useBudgetItems();
  const { nameById, activeUsers, isPending: usersPending } = useUserDirectory();

  const setAttendance = useSetAttendance();
  const addAssignment = useAddAssignment();
  const removeAssignment = useRemoveAssignment();
  const announceActivity = useAnnounceActivity();
  const confirmActivity = useConfirmActivity();
  const deleteActivity = useDeleteActivity();
  const createBudgetItem = useCreateBudgetItem();
  const deleteBudgetItem = useDeleteBudgetItem();

  const [isChangingAnswer, setIsChangingAnswer] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [budgetLabel, setBudgetLabel] = useState("");
  const [budgetAmount, setBudgetAmount] = useState(0);

  const activity = useMemo(
    () => (activitiesQuery.data?.data ?? []).find((a) => a.activity_id === activityId),
    [activitiesQuery.data, activityId],
  );

  const itemsById = useMemo(() => {
    const map = new Map<string, Item>();
    for (const item of itemsQuery.data?.data ?? []) {
      map.set(item.item_id, item);
    }
    return map;
  }, [itemsQuery.data]);

  const attendanceRows = useMemo(
    () => (attendanceQuery.data?.data ?? []).filter((row) => row.activity_id === activityId),
    [attendanceQuery.data, activityId],
  );

  const currentSlots = useMemo(
    () => (assignmentsQuery.data ?? []).filter((slot) => slot.activity_id === activityId),
    [assignmentsQuery.data, activityId],
  );

  const budgetItemsForActivity = useMemo(
    () =>
      (budgetItemsQuery.data?.data ?? []).filter(
        (item) => item.activity_id === activityId && item.is_active,
      ),
    [budgetItemsQuery.data, activityId],
  );
  const budgetTotal = budgetItemsForActivity.reduce((sum, item) => sum + item.amount_jpy, 0);

  const isPending =
    activitiesQuery.isPending ||
    attendanceQuery.isPending ||
    assignmentsQuery.isPending ||
    itemsQuery.isPending ||
    budgetItemsQuery.isPending ||
    usersPending ||
    !user;

  if (isPending) {
    return <p>{t("common.loading")}</p>;
  }

  if (!activity) {
    return <Navigate to="/activities" replace />;
  }

  const attendingCount = attendanceRows.filter((r) => r.status === "attending").length;
  const absentCount = attendanceRows.filter((r) => r.status === "absent").length;
  const undecidedCount = Math.max(0, activeUsers.length - attendingCount - absentCount);

  const myAttendance = attendanceRows.find((row) => row.discord_user_id === user.discord_user_id);
  const myStatus = myAttendance?.status ?? "undecided";
  const showRsvpButtons = isChangingAnswer || myStatus === "undecided";

  const unassignedSlots = currentSlots.filter((slot) => needsAssigneeWarning(slot, itemsById));
  const assignedSlots = currentSlots.filter((slot) => !needsAssigneeWarning(slot, itemsById));

  // カテゴリー別の追加済み器具数(ItemSelectionPage と同じ集計)。アドホック入力(custom_name のみ)
  // はカテゴリを持たないため集計から除く。
  const addedCountsByCategory = new Map<string, number>();
  for (const slot of currentSlots) {
    if (!slot.item_id) continue;
    const item = itemsById.get(slot.item_id);
    if (!item) continue;
    addedCountsByCategory.set(item.category, (addedCountsByCategory.get(item.category) ?? 0) + 1);
  }

  const attendeeNames = attendanceRows
    .filter((row) => row.status === "attending")
    .map((row) => nameById.get(row.discord_user_id) ?? row.discord_user_id);

  const canManage = canManageActivities(user);

  function handleSetAttendance(status: AttendanceStatus) {
    if (!activity) return;
    setAttendance.mutate(
      { activityId: activity.activity_id, status },
      { onSuccess: () => setIsChangingAnswer(false) },
    );
  }

  function handleClaim(slot: AssignmentSlot) {
    if (!activity || !user) return;
    addAssignment.mutate({
      activity_id: activity.activity_id,
      item_id: slot.item_id ?? undefined,
      custom_name: slot.item_id ? undefined : (slot.custom_name ?? undefined),
      assignee_id: user.discord_user_id,
    });
  }

  function handleRemove(slot: AssignmentSlot) {
    if (!activity) return;
    removeAssignment.mutate({
      activity_id: activity.activity_id,
      item_id: slot.item_id ?? undefined,
      custom_name: slot.item_id ? undefined : (slot.custom_name ?? undefined),
    });
  }

  function handleAddBudgetItem(event: FormEvent) {
    event.preventDefault();
    if (!activity) return;
    createBudgetItem.mutate(
      { activity_id: activity.activity_id, label: budgetLabel, amount_jpy: budgetAmount },
      {
        onSuccess: () => {
          setBudgetLabel("");
          setBudgetAmount(0);
        },
      },
    );
  }

  return (
    <>
      <DetailHeader label={t("activities.detailLabel")} fallbackTo="/activities" />
      <main>
        <div className={styles.stack}>
          <div className={styles.headerBlock}>
            <div className={styles.dateTime}>
              {formatDateTime(activity.starts_at, { month: "numeric", day: "numeric", weekday: "short" })}{" "}
              {formatDateTime(activity.starts_at, { hour: "2-digit", minute: "2-digit", hourCycle: "h23" })}
              {"–"}
              {formatDateTime(computeEndTimeIso(activity.starts_at, activity.duration_min), {
                hour: "2-digit",
                minute: "2-digit",
                hourCycle: "h23",
              })}
            </div>
            <h1 className={styles.title}>{activity.title}</h1>
            {activity.location && <div className={styles.location}>{activity.location}</div>}
          </div>

          <div className={styles.tallyRow}>
            <div className={styles.tallyGroup}>
              <span className={styles.tallyItem}>
                {t("activities.tallyAttending")}
                <b className={styles.tallyAttending}>{attendingCount}</b>
              </span>
              <span className={styles.tallyItem}>
                {t("activities.tallyAbsent")}
                <b>{absentCount}</b>
              </span>
              <span className={styles.tallyItem}>
                {t("activities.tallyUndecided")}
                <b>{undecidedCount}</b>
              </span>
            </div>
            <div className={styles.statusBadge}>
              <span
                className={`${styles.dot} ${
                  showRsvpButtons
                    ? styles.dotWarn
                    : myStatus === "attending"
                      ? styles.dotPositive
                      : styles.dotMuted
                }`}
                aria-hidden="true"
              />
              <span className={styles.statusText}>
                {showRsvpButtons
                  ? t("home.unanswered")
                  : t(myStatus === "attending" ? "home.attendingAnswered" : "home.absentAnswered")}
              </span>
            </div>
          </div>

          {showRsvpButtons ? (
            <div className={styles.rsvpActions}>
              <Button
                variant="primary"
                disabled={setAttendance.isPending}
                onClick={() => handleSetAttendance("attending")}
              >
                {t("home.rsvpAttend")}
              </Button>
              <Button
                variant="secondary"
                disabled={setAttendance.isPending}
                onClick={() => handleSetAttendance("absent")}
              >
                {t("home.rsvpAbsent")}
              </Button>
            </div>
          ) : (
            <div className={styles.rsvpActions}>
              <Button variant="secondary" onClick={() => setIsChangingAnswer(true)}>
                {t("home.changeAnswer")}
              </Button>
            </div>
          )}

          <div className={styles.card}>
            <div className={styles.readinessHeaderRow}>
              <span className={styles.readinessTitle}>{t("assignments.readinessTitle")}</span>
              {unassignedSlots.length > 0 && (
                <span className={styles.unassignedCount}>
                  {t("assignments.unassignedCount", { count: unassignedSlots.length })}
                </span>
              )}
            </div>

            {addedCountsByCategory.size > 0 && (
              <div className={styles.categoryCounts}>
                {[...addedCountsByCategory.entries()].map(([cat, count]) => (
                  <span key={cat} className={styles.categoryCountBadge}>
                    {t(`categories.${cat}`)} {count}
                  </span>
                ))}
              </div>
            )}

            {assignedSlots.map((slot) => {
              const item = slot.item_id ? itemsById.get(slot.item_id) : undefined;
              const name = item ? item.name : (slot.custom_name ?? "");
              const note =
                slot.assignee_id !== null
                  ? t("assignments.assignedToLabel", {
                      name: nameById.get(slot.assignee_id) ?? slot.assignee_id,
                    })
                  : t("assignments.clubroomNote");
              return (
                <div
                  key={slot.item_id ?? `custom:${slot.custom_name ?? ""}`}
                  className={`${styles.itemRow} ${slot.assignee_id !== null ? styles.itemRowAssigned : ""}`}
                >
                  <div className={styles.itemInfo}>
                    <span className={styles.itemName}>{name}</span>
                    {item && (
                      <span className={styles.itemMeta}>
                        {item.maker} · {t(`categories.${item.category}`)}
                      </span>
                    )}
                    <span className={styles.itemNote}>{note}</span>
                  </div>
                  <Button
                    variant="text"
                    disabled={removeAssignment.isPending}
                    onClick={() => handleRemove(slot)}
                  >
                    {t("assignments.removeButton")}
                  </Button>
                </div>
              );
            })}

            {unassignedSlots.length > 0 && (
              <>
                <div className={styles.unassignedDivider}>{t("assignments.unassignedSectionLabel")}</div>
                {unassignedSlots.map((slot) => {
                  const item = slot.item_id ? itemsById.get(slot.item_id) : undefined;
                  const name = item ? item.name : (slot.custom_name ?? "");
                  return (
                    <div
                      key={slot.item_id ?? `custom:${slot.custom_name ?? ""}`}
                      className={styles.unassignedRow}
                    >
                      <div className={styles.itemInfo}>
                        <span className={styles.itemName}>{name}</span>
                        {item && (
                          <span className={styles.itemMeta}>
                            {item.maker} · {t(`categories.${item.category}`)}
                          </span>
                        )}
                        <span className={styles.unassignedNote}>{t("assignments.unassignedSectionLabel")}</span>
                      </div>
                      <Button variant="warn" disabled={addAssignment.isPending} onClick={() => handleClaim(slot)}>
                        {t("assignments.claimButton")}
                      </Button>
                    </div>
                  );
                })}
              </>
            )}

            <div className={styles.addItemButtonRow}>
              <Button variant="cta" onClick={() => navigate(`/activities/${activity.activity_id}/select-item`)}>
                {t("assignments.addItemButton")}
              </Button>
            </div>
          </div>

          <div className={styles.section}>
            <div className={styles.sectionHeaderRow}>
              <span className={styles.sectionTitle}>{t("budgetItems.title")}</span>
              <span className={styles.budgetTotal}>
                {t("budgetItems.total", { amount: budgetTotal.toLocaleString("ja-JP") })}
              </span>
            </div>

            {budgetItemsForActivity.length === 0 ? (
              <p className={styles.itemNote}>{t("budgetItems.empty")}</p>
            ) : (
              budgetItemsForActivity.map((budgetItem) => (
                <div key={budgetItem.budget_item_id} className={styles.budgetRow}>
                  <span className={styles.itemName}>{budgetItem.label}</span>
                  <div className={styles.budgetRowRight}>
                    <span className={styles.budgetAmount}>
                      {t("budgetItems.amount", { amount: budgetItem.amount_jpy.toLocaleString("ja-JP") })}
                    </span>
                    {canManage && (
                      <Button
                        variant="text"
                        disabled={deleteBudgetItem.isPending}
                        onClick={() => deleteBudgetItem.mutate(budgetItem.budget_item_id)}
                      >
                        {t("assignments.removeButton")}
                      </Button>
                    )}
                  </div>
                </div>
              ))
            )}

            {canManage && (
              <form className={styles.budgetForm} onSubmit={handleAddBudgetItem}>
                <input
                  value={budgetLabel}
                  onChange={(event) => setBudgetLabel(event.target.value)}
                  placeholder={t("budgetItems.labelPlaceholder")}
                  required
                  minLength={1}
                />
                <input
                  type="number"
                  value={budgetAmount}
                  onChange={(event) => setBudgetAmount(Number(event.target.value))}
                  placeholder={t("budgetItems.amountPlaceholder")}
                  required
                />
                <Button type="submit" variant="secondary" disabled={createBudgetItem.isPending}>
                  {t("budgetItems.addButton")}
                </Button>
              </form>
            )}
          </div>

          <details className={styles.details}>
            <summary className={styles.detailsSummary}>
              {t("activities.attendeesToggle", { count: attendeeNames.length })}
            </summary>
            <p className={styles.attendeesList}>{attendeeNames.join("、") || "—"}</p>
          </details>

          <details className={styles.details}>
            <summary className={styles.detailsSummary}>{t("activities.detailsToggle")}</summary>
            <div className={styles.fieldList}>
              {activity.description && (
                <div>
                  <span className={styles.fieldLabel}>{t("activities.detailDescriptionLabel")}</span>
                  <p className={styles.fieldValue}>{activity.description}</p>
                </div>
              )}
              {activity.target && (
                <div>
                  <span className={styles.fieldLabel}>{t("activities.detailTargetLabel")}</span>
                  <p className={styles.fieldValue}>{activity.target}</p>
                </div>
              )}
              <div>
                <span className={styles.fieldLabel}>{t("activities.ownerLabel")}</span>
                <p className={styles.fieldValue}>{nameById.get(activity.owner_id) ?? activity.owner_id}</p>
              </div>
              {activity.tasks && (
                <div>
                  <span className={styles.fieldLabel}>{t("activities.detailTasksLabel")}</span>
                  <p className={styles.fieldValue}>{activity.tasks}</p>
                </div>
              )}
              {activity.note && (
                <div>
                  <span className={styles.fieldLabel}>{t("activities.detailNoteLabel")}</span>
                  <p className={styles.fieldValue}>{activity.note}</p>
                </div>
              )}
            </div>
          </details>

          {canManage && (
            <details className={styles.details}>
              <summary className={styles.detailsSummary}>{t("activities.manageSectionLabel")}</summary>
              <div className={styles.manageSection}>
                <Button variant="secondary" onClick={() => setIsEditing(true)}>
                  {t("activities.editButton")}
                </Button>
                <Button
                  variant="secondary"
                  disabled={announceActivity.isPending}
                  onClick={() => announceActivity.mutate(activity.activity_id)}
                >
                  {activity.announce_message_id
                    ? t("activities.reannounceButton")
                    : t("activities.announceButton")}
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => {
                    if (window.confirm(t("activities.deleteConfirm"))) {
                      deleteActivity.mutate(activity.activity_id, {
                        onSuccess: () => navigate("/activities", { replace: true }),
                      });
                    }
                  }}
                >
                  {t("activities.deleteButton")}
                </Button>
              </div>
            </details>
          )}

          {canManage && isEditing && (
            <Modal title={t("activities.editModalTitle")} onClose={() => setIsEditing(false)}>
              <ActivityForm
                mode="edit"
                activity={activity}
                currentUserId={user.discord_user_id}
                activeUsers={activeUsers}
                onDone={() => setIsEditing(false)}
              />
            </Modal>
          )}

          {canManage && (
            <Button
              variant="primary"
              disabled={confirmActivity.isPending}
              onClick={() => {
                if (window.confirm(t("activities.confirmActivityConfirm"))) {
                  confirmActivity.mutate(activity.activity_id);
                }
              }}
            >
              {t("activities.confirmButton")}
            </Button>
          )}
        </div>
      </main>
    </>
  );
}

/** storage=clubroom は元々担当不要。それ以外で assignee_id が空なのは「担当未定」の警告対象
 * (アドホック入力は未割り当てを許容するため起こりうる。CLAUDE.md §5)。 */
function needsAssigneeWarning(slot: AssignmentSlot, itemsById: Map<string, Item>): boolean {
  if (slot.assignee_id !== null) return false;
  const item = slot.item_id ? itemsById.get(slot.item_id) : undefined;
  return item === undefined || item.storage !== "clubroom";
}
