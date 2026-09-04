import { useState, type FormEvent } from "react";
import { useCreateItem, useUpdateItem } from "../api/hooks";
import { CIRCLE_OWNER_ID } from "../api/types";
import type { Category, CurrentUser, Item, Storage } from "../api/types";
import { Button } from "../components/Button";
import { useI18n } from "../i18n/useI18n";
import styles from "./ItemForm.module.css";
import { canSetOwnerCircle } from "./permissions";

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

interface ItemFormProps {
  mode: "create" | "edit";
  item?: Item;
  currentUser: CurrentUser;
  onDone: () => void;
  /** 編集モードでのみ渡す。渡された場合、フォーム下部に削除ボタンを表示する。 */
  onRequestDelete?: () => void;
}

/**
 * 登録・編集で共通のフォーム。item_id は入力項目に含めない(アプリが採番するため、
 * 人間が入力する余地を作らない: CLAUDE.md §4)。owner_id は編集時には変更できない。
 */
export function ItemForm({ mode, item, currentUser, onDone, onRequestDelete }: ItemFormProps) {
  const { t } = useI18n();
  const createItem = useCreateItem();
  const updateItem = useUpdateItem();

  const [name, setName] = useState(item?.name ?? "");
  const [maker, setMaker] = useState(item?.maker ?? "");
  const [category, setCategory] = useState<Category>(item?.category ?? "dripper");
  const [storage, setStorage] = useState<Storage>(item?.storage ?? "owner");
  const [note, setNote] = useState(item?.note ?? "");
  const [ownAsCircle, setOwnAsCircle] = useState(item?.owner_id === CIRCLE_OWNER_ID);

  const canChooseCircle = mode === "create" && canSetOwnerCircle(currentUser);
  const pending = createItem.isPending || updateItem.isPending;
  const error = mode === "create" ? createItem.error : updateItem.error;

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (mode === "create") {
      createItem.mutate(
        { name, maker, category, storage, note, owner_id: ownAsCircle ? CIRCLE_OWNER_ID : undefined },
        { onSuccess: onDone },
      );
    } else if (item) {
      updateItem.mutate(
        { itemId: item.item_id, payload: { name, maker, category, storage, note } },
        { onSuccess: onDone },
      );
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <div className={styles.fields}>
        <label>
          {t("items.formName")}
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
            minLength={1}
          />
        </label>
        <label>
          {t("items.formMaker")}
          <input value={maker} onChange={(event) => setMaker(event.target.value)} />
        </label>
        <label>
          {t("items.formCategory")}
          <select value={category} onChange={(event) => setCategory(event.target.value as Category)}>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {t(`categories.${c}`)}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t("items.formStorage")}
          <select value={storage} onChange={(event) => setStorage(event.target.value as Storage)}>
            {STORAGES.map((s) => (
              <option key={s} value={s}>
                {t(`storage.${s}`)}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t("items.formNote")}
          <input value={note} onChange={(event) => setNote(event.target.value)} />
        </label>
        {storage === "other" && <p className={styles.hint}>{t("items.storageOtherHint")}</p>}
        {canChooseCircle && (
          <label className={styles.circleOption}>
            <input
              type="checkbox"
              checked={ownAsCircle}
              onChange={(event) => setOwnAsCircle(event.target.checked)}
            />
            {t("items.ownerCircle")}
          </label>
        )}
      </div>

      <div className={styles.footer}>
        <Button type="button" variant="secondary" onClick={onDone}>
          {t("items.cancelButton")}
        </Button>
        <Button type="submit" variant="cta" disabled={pending}>
          {t("items.saveButton")}
        </Button>
      </div>
      {error && (
        <p role="alert" className={styles.error}>
          {t(`errors.${error.code}`)}
        </p>
      )}

      {mode === "edit" && onRequestDelete && (
        <div className={styles.deleteRow}>
          <Button type="button" variant="text" onClick={onRequestDelete}>
            {t("items.deleteButton")}
          </Button>
        </div>
      )}
    </form>
  );
}
