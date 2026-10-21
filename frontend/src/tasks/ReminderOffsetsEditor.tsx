import { useRef, useState } from "react";
import { Button } from "../components/Button";
import { useI18n } from "../i18n/useI18n";
import { type OffsetRow, type OffsetUnit, parseOffsets, serializeOffsets } from "./reminderOffsets";
import styles from "./ReminderOffsetsEditor.module.css";

interface Row extends OffsetRow {
  id: number;
}

interface ReminderOffsetsEditorProps {
  value: string;
  onChange: (value: string) => void;
}

/**
 * reminder_offsets(例 "-7d,-1d,-2h")をカンマ区切りの自由入力ではなく、
 * 「○日前/○時間前/○分前」の行を追加・削除する形で編集させる(壊れにくい設計)。
 * 行は内部で id を持ち、文字列との往復による再マウント・フォーカス喪失を避ける
 * (入力のたびに value から再パースし直さない。シートを直接編集する運用との整合は
 * 「幹部がセルを直接編集してもアプリ側が壊れない」という読み取り側のバリデーションで担保する)。
 */
export function ReminderOffsetsEditor({ value, onChange }: ReminderOffsetsEditorProps) {
  const { t } = useI18n();
  const nextId = useRef(0);
  const [rows, setRows] = useState<Row[]>(() =>
    parseOffsets(value).map((row) => ({ ...row, id: nextId.current++ })),
  );

  function emit(next: Row[]) {
    setRows(next);
    onChange(serializeOffsets(next));
  }

  function handleAdd() {
    emit([...rows, { id: nextId.current++, amount: 1, unit: "d" }]);
  }

  function handleRemove(id: number) {
    emit(rows.filter((row) => row.id !== id));
  }

  function handleAmountChange(id: number, amount: number) {
    emit(rows.map((row) => (row.id === id ? { ...row, amount } : row)));
  }

  function handleUnitChange(id: number, unit: OffsetUnit) {
    emit(rows.map((row) => (row.id === id ? { ...row, unit } : row)));
  }

  return (
    <div className={styles.editor}>
      {rows.length === 0 && <p className={styles.empty}>{t("tasks.reminderOffsetsEmpty")}</p>}
      {rows.map((row) => (
        <div key={row.id} className={styles.row}>
          <input
            type="number"
            min={1}
            step={1}
            value={row.amount}
            onChange={(event) => handleAmountChange(row.id, Number(event.target.value))}
            className={styles.amountInput}
          />
          <select
            value={row.unit}
            onChange={(event) => handleUnitChange(row.id, event.target.value as OffsetUnit)}
            className={styles.unitSelect}
          >
            <option value="d">{t("tasks.offsetUnitDay")}</option>
            <option value="h">{t("tasks.offsetUnitHour")}</option>
            <option value="m">{t("tasks.offsetUnitMinute")}</option>
          </select>
          <Button type="button" variant="text" onClick={() => handleRemove(row.id)}>
            {t("tasks.removeOffsetButton")}
          </Button>
        </div>
      ))}
      <Button type="button" variant="secondary" onClick={handleAdd}>
        {t("tasks.addOffsetButton")}
      </Button>
    </div>
  );
}
