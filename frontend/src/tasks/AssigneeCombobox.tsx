import { useMemo, useRef, useState } from "react";
import type { TaskAssignee, User } from "../api/types";
import { useI18n } from "../i18n/useI18n";
import styles from "./AssigneeCombobox.module.css";

interface Suggestion {
  key: string;
  display: string;
  assignee: TaskAssignee;
  isLabel: boolean;
}

interface AssigneeComboboxProps {
  value: TaskAssignee[];
  onChange: (value: TaskAssignee[]) => void;
  /** 選択可能な個人候補(すでに visibility で絞り込み済み)。 */
  candidateUsers: User[];
  /** 過去に使われた部門名などのラベル候補(サジェスト用)。 */
  knownLabels: string[];
  nameById: Map<string, string>;
}

/**
 * 担当者を「登録済みメンバーから選ぶ」か「部門名などを自由記述する」かを1つの入力欄で
 * 両立させるコンボボックス。既存メンバーと過去に使われたラベルをサジェストしつつ、
 * 候補にない文字列もそのまま部門ラベルとして追加できる(CLAUDE.md §5のアドホック入力と
 * 同じ考え方)。
 */
export function AssigneeCombobox({
  value,
  onChange,
  candidateUsers,
  knownLabels,
  nameById,
}: AssigneeComboboxProps) {
  const { t } = useI18n();
  const [inputValue, setInputValue] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const trimmed = inputValue.trim();

  const suggestions = useMemo<Suggestion[]>(() => {
    const query = trimmed.toLowerCase();
    const userSuggestions: Suggestion[] = candidateUsers
      .filter((candidate) => !value.some((a) => a.member_id === candidate.discord_user_id))
      .filter((candidate) => query === "" || candidate.name.toLowerCase().includes(query))
      .map((candidate) => ({
        key: `member:${candidate.discord_user_id}`,
        display: candidate.name,
        assignee: { member_id: candidate.discord_user_id, label: null },
        isLabel: false,
      }));

    const labelSuggestions: Suggestion[] = knownLabels
      .filter((label) => !value.some((a) => a.label === label))
      .filter((label) => query === "" || label.toLowerCase().includes(query))
      .map((label) => ({
        key: `label:${label}`,
        display: label,
        assignee: { member_id: null, label },
        isLabel: true,
      }));

    return [...userSuggestions, ...labelSuggestions].slice(0, 20);
  }, [candidateUsers, knownLabels, value, trimmed]);

  const canAddAsNewLabel =
    trimmed.length > 0 &&
    !suggestions.some((s) => s.display.toLowerCase() === trimmed.toLowerCase()) &&
    !value.some((a) => (a.label ?? "").toLowerCase() === trimmed.toLowerCase());

  function commit(assignee: TaskAssignee) {
    onChange([...value, assignee]);
    setInputValue("");
    inputRef.current?.focus();
  }

  function removeAt(index: number) {
    onChange(value.filter((_, i) => i !== index));
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      if (suggestions.length > 0) {
        commit(suggestions[0].assignee);
      } else if (canAddAsNewLabel) {
        commit({ member_id: null, label: trimmed });
      }
    } else if (event.key === "Backspace" && inputValue === "" && value.length > 0) {
      removeAt(value.length - 1);
    }
  }

  function displayFor(assignee: TaskAssignee): string {
    if (assignee.member_id) return nameById.get(assignee.member_id) ?? assignee.member_id;
    return assignee.label ?? "";
  }

  return (
    <div className={styles.combobox}>
      <div className={styles.inputRow}>
        {value.map((assignee, index) => (
          <span key={`${assignee.member_id ?? assignee.label}-${index}`} className={styles.chip}>
            {displayFor(assignee)}
            <button
              type="button"
              className={styles.chipRemove}
              onClick={() => removeAt(index)}
              aria-label={t("tasks.removeAssigneeButton")}
            >
              ×
            </button>
          </span>
        ))}
        <input
          ref={inputRef}
          type="text"
          className={styles.input}
          value={inputValue}
          placeholder={t("tasks.assigneeSearchPlaceholder")}
          onChange={(event) => setInputValue(event.target.value)}
          onFocus={() => setIsOpen(true)}
          onBlur={() => setTimeout(() => setIsOpen(false), 150)}
          onKeyDown={handleKeyDown}
        />
      </div>
      {isOpen && (suggestions.length > 0 || canAddAsNewLabel) && (
        <ul className={styles.suggestionList}>
          {suggestions.map((suggestion) => (
            <li key={suggestion.key}>
              <button
                type="button"
                className={styles.suggestionButton}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => commit(suggestion.assignee)}
              >
                {suggestion.display}
                {suggestion.isLabel && <span className={styles.suggestionTag}>{t("tasks.departmentTag")}</span>}
              </button>
            </li>
          ))}
          {canAddAsNewLabel && (
            <li>
              <button
                type="button"
                className={styles.suggestionButton}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => commit({ member_id: null, label: trimmed })}
              >
                {t("tasks.addDepartmentOption", { name: trimmed })}
              </button>
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
