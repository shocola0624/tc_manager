import { useMemo, useState, type FormEvent } from "react";
import { Navigate, useParams } from "react-router-dom";
import {
  useAddAssignment,
  useAssignmentCandidates,
  useAttendance,
  useCurrentAssignments,
  useItems,
} from "../api/hooks";
import type { Category, ItemCandidate } from "../api/types";
import { Button } from "../components/Button";
import { DetailHeader } from "../components/DetailHeader";
import type { Translate } from "../i18n/t";
import { useI18n } from "../i18n/useI18n";
import { useUserDirectory } from "../users/useUserDirectory";
import styles from "./ItemSelectionPage.module.css";

const CATEGORIES: Category[] = [
  "dripper",
  "grinder",
  "scale",
  "kettle",
  "pot",
  "scoop",
  "thermometer",
  "server",
  "other",
];

/** 拡張モードでのみ表示する候補(storage=owner かつ所有者が出席しない)かどうか。
 * バックエンドは常に extended_mode=true で候補を返す(sheets/assignment_candidates.py)ため、
 * この2条件だけで「通常リスト」と「非表示ゾーン」をクライアント側で分けられる。 */
function isExtendedOnly(candidate: ItemCandidate): boolean {
  return candidate.item.storage === "owner" && candidate.requires_assignee;
}

/** 器具の選択画面(screen-reference.dc.html 画面3)。複数の器具をチェックボックスで選び、
 * まとめて活動に追加できる。担当者が必要な候補(other・拡張モードのowner)は行内で選んでから
 * 追加操作を行う。 */
export function ItemSelectionPage() {
  const { activityId } = useParams<{ activityId: string }>();
  const { t } = useI18n();
  const { nameById } = useUserDirectory();

  const candidatesQuery = useAssignmentCandidates(activityId ?? "", true);
  const attendanceQuery = useAttendance();
  const currentQuery = useCurrentAssignments();
  const itemsQuery = useItems();
  const addAssignment = useAddAssignment();

  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<Category | "all">("all");
  const [extendedOn, setExtendedOn] = useState(false);
  const [showAdHocForm, setShowAdHocForm] = useState(false);
  const [adHocName, setAdHocName] = useState("");
  const [adHocAssigneeId, setAdHocAssigneeId] = useState("");
  const [checkedItemIds, setCheckedItemIds] = useState<Set<string>>(new Set());
  const [assigneeByItemId, setAssigneeByItemId] = useState<Record<string, string>>({});
  const [isAddingSelection, setIsAddingSelection] = useState(false);

  const attendingUserIds = useMemo(
    () =>
      (attendanceQuery.data?.data ?? [])
        .filter((row) => row.activity_id === activityId && row.status === "attending")
        .map((row) => row.discord_user_id),
    [attendanceQuery.data, activityId],
  );

  // 既に活動へ追加済みのスロット(候補一覧からの除外・カテゴリ別集計の両方に使う)。
  const addedSlots = useMemo(
    () => (currentQuery.data ?? []).filter((slot) => slot.activity_id === activityId),
    [currentQuery.data, activityId],
  );

  const alreadyAddedItemIds = useMemo(
    () => new Set(addedSlots.map((slot) => slot.item_id).filter((id): id is string => id !== null)),
    [addedSlots],
  );

  // カテゴリー別の追加済み器具数。候補一覧は追加済みのものを除外してしまうため、
  // 品目→カテゴリの解決には(候補ではなく)全器具を持つ useItems() を使う。
  // アドホック入力(custom_name のみ)はカテゴリを持たないため集計から除く。
  const addedCountsByCategory = useMemo(() => {
    const itemsById = new Map((itemsQuery.data?.data ?? []).map((item) => [item.item_id, item]));
    const counts = new Map<Category, number>();
    for (const slot of addedSlots) {
      if (!slot.item_id) continue;
      const item = itemsById.get(slot.item_id);
      if (!item) continue;
      counts.set(item.category, (counts.get(item.category) ?? 0) + 1);
    }
    return counts;
  }, [addedSlots, itemsQuery.data]);

  const allCandidates = useMemo(
    () => (candidatesQuery.data ?? []).filter((c) => !alreadyAddedItemIds.has(c.item.item_id)),
    [candidatesQuery.data, alreadyAddedItemIds],
  );

  const candidatesById = useMemo(
    () => new Map(allCandidates.map((c) => [c.item.item_id, c])),
    [allCandidates],
  );

  const matchesFilters = (candidate: ItemCandidate) => {
    if (category !== "all" && candidate.item.category !== category) return false;
    const query = search.trim().toLowerCase();
    if (query && !`${candidate.item.name} ${candidate.item.maker}`.toLowerCase().includes(query)) {
      return false;
    }
    return true;
  };

  const normalCandidates = allCandidates.filter((c) => !isExtendedOnly(c) && matchesFilters(c));
  const extendedCandidates = allCandidates.filter((c) => isExtendedOnly(c) && matchesFilters(c));

  const hasIncompleteSelection = [...checkedItemIds].some((id) => {
    const candidate = candidatesById.get(id);
    return candidate?.requires_assignee && !assigneeByItemId[id];
  });

  if (!activityId) {
    return <Navigate to="/activities" replace />;
  }
  // 以降の閉包(handleAdd 等)から見ても string 型で確定させるため束縛し直す
  // (TypeScript はネストした関数越しにこの上の narrowing を伝播しないため)。
  const currentActivityId: string = activityId;

  function toggleChecked(itemId: string) {
    setCheckedItemIds((prev) => {
      const next = new Set(prev);
      if (next.has(itemId)) {
        next.delete(itemId);
      } else {
        next.add(itemId);
      }
      return next;
    });
  }

  function setAssigneeForItem(itemId: string, assigneeId: string) {
    setAssigneeByItemId((prev) => ({ ...prev, [itemId]: assigneeId }));
  }

  async function handleAddSelected() {
    const targets = [...checkedItemIds]
      .map((id) => candidatesById.get(id))
      .filter((c): c is ItemCandidate => c !== undefined);
    if (targets.length === 0) return;

    setIsAddingSelection(true);
    try {
      await Promise.all(
        targets.map((candidate) =>
          addAssignment.mutateAsync({
            activity_id: currentActivityId,
            item_id: candidate.item.item_id,
            assignee_id: candidate.requires_assignee ? assigneeByItemId[candidate.item.item_id] : undefined,
          }),
        ),
      );
      setCheckedItemIds(new Set());
      setAssigneeByItemId({});
    } finally {
      setIsAddingSelection(false);
    }
  }

  function handleAddAdHoc(event: FormEvent) {
    event.preventDefault();
    addAssignment.mutate(
      {
        activity_id: currentActivityId,
        custom_name: adHocName,
        assignee_id: adHocAssigneeId || undefined,
      },
      {
        onSuccess: () => {
          setAdHocName("");
          setAdHocAssigneeId("");
          setShowAdHocForm(false);
        },
      },
    );
  }

  return (
    <>
      <DetailHeader label={t("assignments.selectTitle")} fallbackTo={`/activities/${activityId}`} />
      <main>
        <div className={styles.stack}>
          {addedCountsByCategory.size > 0 && (
            <div className={styles.selectionSummary}>
              <span className={styles.selectionCountsLabel}>{t("assignments.addedCategoryCounts")}</span>
              <div className={styles.selectionCounts}>
                {[...addedCountsByCategory.entries()].map(([cat, count]) => (
                  <span key={cat} className={styles.selectionBadge}>
                    {t(`categories.${cat}`)} {count}
                  </span>
                ))}
              </div>
            </div>
          )}

          {checkedItemIds.size > 0 && (
            <div className={styles.selectionSummary}>
              <span className={styles.selectionCountsLabel}>
                {t("assignments.selectedCount", { count: checkedItemIds.size })}
              </span>
              <Button
                variant="primary"
                disabled={isAddingSelection || hasIncompleteSelection}
                onClick={handleAddSelected}
              >
                {t("assignments.addSelectedButton", { count: checkedItemIds.size })}
              </Button>
            </div>
          )}

          <input
            className={styles.search}
            type="search"
            placeholder={t("assignments.searchPlaceholder")}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />

          <div className={styles.chips}>
            <button
              type="button"
              className={`${styles.chip} ${category === "all" ? styles.chipActive : ""}`}
              onClick={() => setCategory("all")}
            >
              {t("items.filterAll")}
            </button>
            {CATEGORIES.map((c) => (
              <button
                key={c}
                type="button"
                className={`${styles.chip} ${category === c ? styles.chipActive : ""}`}
                onClick={() => setCategory(c)}
              >
                {t(`categories.${c}`)}
              </button>
            ))}
          </div>

          <div className={styles.legend}>
            <span className={styles.legendItem}>
              <span className={styles.legendDot} style={{ background: "var(--positive)" }} />
              {t("assignments.legendClubroom")}
            </span>
            <span className={styles.legendItem}>
              <span className={styles.legendDot} style={{ background: "var(--accent)" }} />
              {t("assignments.legendOwner")}
            </span>
            <span className={styles.legendItem}>
              <span className={styles.legendDot} style={{ background: "var(--warn)" }} />
              {t("assignments.legendOther")}
            </span>
          </div>

          {candidatesQuery.isPending ? (
            <p>{t("common.loading")}</p>
          ) : normalCandidates.length === 0 ? (
            <p className={styles.empty}>{t("assignments.noCandidates")}</p>
          ) : (
            <div className={styles.candidateList}>
              {normalCandidates.map((candidate) => (
                <CandidateRow
                  key={candidate.item.item_id}
                  candidate={candidate}
                  attendingUserIds={attendingUserIds}
                  nameById={nameById}
                  checked={checkedItemIds.has(candidate.item.item_id)}
                  assigneeId={assigneeByItemId[candidate.item.item_id] ?? ""}
                  onToggle={toggleChecked}
                  onAssigneeChange={setAssigneeForItem}
                  t={t}
                />
              ))}
            </div>
          )}

          <div className={styles.toggleRow}>
            <span>{t("assignments.extendedModeToggle")}</span>
            <button
              type="button"
              role="switch"
              aria-checked={extendedOn}
              className={`${styles.switch} ${extendedOn ? styles.switchOn : ""}`}
              onClick={() => setExtendedOn((value) => !value)}
            >
              <span className={styles.switchKnob} />
            </button>
          </div>

          {extendedOn && (
            <div className={styles.extendedZone}>
              <p className={styles.extendedZoneLabel}>{t("assignments.extendedZoneLabel")}</p>
              {extendedCandidates.length === 0 ? (
                <p className={styles.empty}>{t("assignments.noCandidates")}</p>
              ) : (
                <div className={styles.candidateList}>
                  {extendedCandidates.map((candidate) => (
                    <div key={candidate.item.item_id} className={styles.extendedZoneRow}>
                      <CandidateRow
                        candidate={candidate}
                        attendingUserIds={attendingUserIds}
                        nameById={nameById}
                        checked={checkedItemIds.has(candidate.item.item_id)}
                        assigneeId={assigneeByItemId[candidate.item.item_id] ?? ""}
                        onToggle={toggleChecked}
                        onAssigneeChange={setAssigneeForItem}
                        t={t}
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {showAdHocForm ? (
            <form className={styles.adHocForm} onSubmit={handleAddAdHoc}>
              <label>
                {t("assignments.adHocNameLabel")}
                <input value={adHocName} onChange={(event) => setAdHocName(event.target.value)} required minLength={1} />
              </label>
              <label>
                {t("assignments.adHocAssigneeLabel")}
                <select value={adHocAssigneeId} onChange={(event) => setAdHocAssigneeId(event.target.value)}>
                  <option value="">{t("assignments.assigneeUnassigned")}</option>
                  {attendingUserIds.map((id) => (
                    <option key={id} value={id}>
                      {nameById.get(id) ?? id}
                    </option>
                  ))}
                </select>
              </label>
              <Button type="submit" variant="primary" disabled={addAssignment.isPending}>
                {t("assignments.addButton")}
              </Button>
            </form>
          ) : (
            <Button variant="secondary" onClick={() => setShowAdHocForm(true)}>
              {t("assignments.addAdHocButton")}
            </Button>
          )}
        </div>
      </main>
    </>
  );
}

function CandidateRow({
  candidate,
  attendingUserIds,
  nameById,
  checked,
  assigneeId,
  onToggle,
  onAssigneeChange,
  t,
}: {
  candidate: ItemCandidate;
  attendingUserIds: string[];
  nameById: Map<string, string>;
  checked: boolean;
  assigneeId: string;
  onToggle: (itemId: string) => void;
  onAssigneeChange: (itemId: string, assigneeId: string) => void;
  t: Translate;
}) {
  const barClass =
    candidate.item.storage === "clubroom"
      ? styles.barClubroom
      : candidate.item.storage === "owner"
        ? styles.barOwner
        : styles.barOther;

  const note =
    candidate.item.storage === "clubroom"
      ? t("assignments.hintClubroom")
      : candidate.item.storage === "owner"
        ? t("assignments.hintOwner", {
            name: nameById.get(candidate.item.owner_id) ?? candidate.item.owner_id,
          })
        : t("assignments.hintOther", { location: candidate.item.note });

  return (
    <div className={`${styles.candidateRow} ${barClass}`}>
      <input
        type="checkbox"
        className={styles.candidateCheckbox}
        checked={checked}
        onChange={() => onToggle(candidate.item.item_id)}
        aria-label={candidate.item.name}
      />
      <div className={styles.candidateInfo}>
        <span className={styles.candidateName}>
          {candidate.item.maker} / {candidate.item.name}
        </span>
        <span className={styles.candidateNote}>{note}</span>
      </div>
      {candidate.requires_assignee && (
        <select
          className={styles.assigneeSelect}
          value={assigneeId}
          onChange={(event) => onAssigneeChange(candidate.item.item_id, event.target.value)}
        >
          <option value="">{t("assignments.selectAssignee")}</option>
          {attendingUserIds.map((id) => (
            <option key={id} value={id}>
              {nameById.get(id) ?? id}
            </option>
          ))}
        </select>
      )}
    </div>
  );
}
