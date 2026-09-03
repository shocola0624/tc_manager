import { useMemo, useState } from "react";
import { useDeleteItem, useItems } from "../api/hooks";
import { CIRCLE_OWNER_ID } from "../api/types";
import type { Category, Item, Storage } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
import { Button } from "../components/Button";
import { DetailHeader } from "../components/DetailHeader";
import { InvalidRowsWarning } from "../components/InvalidRowsWarning";
import { Modal } from "../components/Modal";
import { useI18n } from "../i18n/useI18n";
import { useUserDirectory } from "../users/useUserDirectory";
import { ItemForm } from "./ItemForm";
import styles from "./ItemsPage.module.css";
import { canEditItem } from "./permissions";

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
const STORAGES: Storage[] = ["clubroom", "owner", "other"];

type ModalState = { mode: "create" } | { mode: "edit"; item: Item } | null;

/** 持ち物一覧(screen-reference.dc(1).html の t6/t7)。自分/他人/部室で保有者を色分けし、
 * 登録・編集はモーダルで行う。カテゴリーは常時表示のチップで絞り込む。 */
export function ItemsPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const itemsQuery = useItems();
  const { nameById, isPending: usersPending } = useUserDirectory();
  const deleteItem = useDeleteItem();

  const [categoryFilter, setCategoryFilter] = useState<Category | "all">("all");
  const [storageFilter, setStorageFilter] = useState<Storage | "all">("all");
  const [ownerFilter, setOwnerFilter] = useState<string>("all");
  const [modal, setModal] = useState<ModalState>(null);

  const ownerDisplayName = (ownerId: string): string =>
    ownerId === CIRCLE_OWNER_ID ? t("items.ownerCircle") : (nameById.get(ownerId) ?? ownerId);

  // 削除(is_active=FALSE)された持ち物は一覧からは常に除く。カテゴリー/所有者/保管場所の
  // 絞り込みはキャッシュ済みデータに対してクライアント側で行う(CLAUDE.md §3)。
  const activeItems = useMemo(
    () => (itemsQuery.data?.data ?? []).filter((item) => item.is_active),
    [itemsQuery.data],
  );

  const ownerOptions = useMemo(
    () => Array.from(new Set(activeItems.map((item) => item.owner_id))),
    [activeItems],
  );

  const visibleItems = useMemo(
    () =>
      activeItems.filter((item) => {
        if (categoryFilter !== "all" && item.category !== categoryFilter) return false;
        if (storageFilter !== "all" && item.storage !== storageFilter) return false;
        if (ownerFilter !== "all" && item.owner_id !== ownerFilter) return false;
        return true;
      }),
    [activeItems, categoryFilter, storageFilter, ownerFilter],
  );

  if (itemsQuery.isPending || usersPending || !user) {
    return <p>{t("common.loading")}</p>;
  }

  // 保有者による色分け(自分/他人/部室)。保管場所ではなく「誰の持ち物か」で分ける
  // (screen-reference.dc(1).html t6/t7 の凡例)。
  function ownerKind(item: Item): "clubroom" | "mine" | "other" {
    if (item.owner_id === CIRCLE_OWNER_ID) return "clubroom";
    if (item.owner_id === user!.discord_user_id) return "mine";
    return "other";
  }

  function ownedByLabel(item: Item): string {
    const kind = ownerKind(item);
    if (kind === "clubroom") return t("items.ownedByClubroom");
    if (kind === "mine") return t("items.ownedByMe");
    return t("items.ownedByOther", { name: ownerDisplayName(item.owner_id) });
  }

  function ownerColumnLabel(item: Item): string {
    const kind = ownerKind(item);
    if (kind === "clubroom") return t("items.legendClubroom");
    if (kind === "mine") return t("items.legendMine");
    return ownerDisplayName(item.owner_id);
  }

  function closeModal() {
    setModal(null);
  }

  function handleDeleteFromModal(item: Item) {
    if (window.confirm(t("items.deleteConfirm"))) {
      deleteItem.mutate(item.item_id, { onSuccess: closeModal });
    }
  }

  return (
    <>
      <DetailHeader label={t("items.title")} fallbackTo="/" />
      <main>
        {itemsQuery.data && <InvalidRowsWarning invalidRows={itemsQuery.data.invalid_rows} />}

        <div className={styles.toolbar}>
          <div className={styles.chips} role="group" aria-label={t("items.filterCategory")}>
            <button
              type="button"
              className={`${styles.chip} ${categoryFilter === "all" ? styles.chipActive : ""}`}
              onClick={() => setCategoryFilter("all")}
            >
              {t("items.filterAll")}
            </button>
            {CATEGORIES.map((c) => (
              <button
                key={c}
                type="button"
                className={`${styles.chip} ${categoryFilter === c ? styles.chipActive : ""}`}
                onClick={() => setCategoryFilter(c)}
              >
                {t(`categories.${c}`)}
              </button>
            ))}
          </div>
          <Button
            variant="cta"
            className={styles.addDesktop}
            onClick={() => setModal({ mode: "create" })}
          >
            {t("items.addButton")}
          </Button>
        </div>

        <div className={styles.legendRow}>
          <div className={styles.legend}>
            <span className={styles.legendItem}>
              <span className={`${styles.swatch} ${styles.swatchMine}`} />
              {t("items.legendMine")}
            </span>
            <span className={styles.legendItem}>
              <span className={`${styles.swatch} ${styles.swatchOther}`} />
              {t("items.legendOthers")}
            </span>
            <span className={styles.legendItem}>
              <span className={`${styles.swatch} ${styles.swatchClubroom}`} />
              {t("items.legendClubroom")}
            </span>
          </div>
          <div className={styles.secondaryFilters}>
            <label>
              <span className={styles.srOnly}>{t("items.filterStorage")}</span>
              <select
                value={storageFilter}
                onChange={(event) => setStorageFilter(event.target.value as Storage | "all")}
              >
                <option value="all">{t("items.filterStorage")}</option>
                {STORAGES.map((s) => (
                  <option key={s} value={s}>
                    {t(`storage.${s}`)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className={styles.srOnly}>{t("items.filterOwner")}</span>
              <select value={ownerFilter} onChange={(event) => setOwnerFilter(event.target.value)}>
                <option value="all">{t("items.filterOwner")}</option>
                {ownerOptions.map((ownerId) => (
                  <option key={ownerId} value={ownerId}>
                    {ownerDisplayName(ownerId)}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>

        {visibleItems.length === 0 ? (
          <p className={styles.empty}>{t("items.emptyList")}</p>
        ) : (
          <>
            <div className={styles.tableHeader}>
              <span />
              <span>{t("items.tableName")}</span>
              <span>{t("items.tableCategory")}</span>
              <span>{t("items.tableOwner")}</span>
              <span />
            </div>
            <ul className={styles.list}>
              {visibleItems.map((item) => {
                const kind = ownerKind(item);
                return (
                  <li key={item.item_id} className={styles.row}>
                    <div
                      className={`${styles.bar} ${
                        kind === "clubroom"
                          ? styles.barClubroom
                          : kind === "mine"
                            ? styles.barMine
                            : styles.barOther
                      }`}
                    />
                    <div className={styles.main}>
                      <div className={styles.name}>
                        {item.name}
                        {item.maker && <>（{item.maker}）</>}
                      </div>
                      <div className={styles.metaCombined}>
                        {t(`categories.${item.category}`)} · {ownedByLabel(item)}
                        {item.note && <> · {item.note}</>}
                      </div>
                    </div>
                    <div className={styles.categoryCol}>{t(`categories.${item.category}`)}</div>
                    <div className={styles.ownerCol}>{ownerColumnLabel(item)}</div>
                    {canEditItem(item, user) ? (
                      <button
                        type="button"
                        className={styles.editLink}
                        onClick={() => setModal({ mode: "edit", item })}
                      >
                        {t("items.editButton")}
                      </button>
                    ) : (
                      <span />
                    )}
                  </li>
                );
              })}
            </ul>
          </>
        )}

        <Button
          variant="cta"
          className={styles.addMobile}
          onClick={() => setModal({ mode: "create" })}
        >
          {t("items.addButton")}
        </Button>
      </main>

      {modal && (
        <Modal
          title={modal.mode === "create" ? t("items.modalAddTitle") : t("items.modalEditTitle")}
          onClose={closeModal}
        >
          {modal.mode === "create" ? (
            <ItemForm mode="create" currentUser={user} onDone={closeModal} />
          ) : (
            <ItemForm
              mode="edit"
              item={modal.item}
              currentUser={user}
              onDone={closeModal}
              onRequestDelete={() => handleDeleteFromModal(modal.item)}
            />
          )}
        </Modal>
      )}
    </>
  );
}
