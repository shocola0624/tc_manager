import { useState } from "react";
import { useI18n } from "../i18n/useI18n";
import type { InvalidRowOut } from "../api/types";

interface InvalidRowsWarningProps {
  invalidRows: InvalidRowOut[];
}

/**
 * ListResponse.invalid_rows をそのまま受け取り警告表示する共通コンポーネント。
 * reason はバックエンドの検証エラーをそのまま格納した非翻訳の技術的文字列であり、
 * 主にシートを修正する管理者向けの手がかりとして表示する(t() では変換しない)。
 */
export function InvalidRowsWarning({ invalidRows }: InvalidRowsWarningProps) {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState(false);

  if (invalidRows.length === 0) {
    return null;
  }

  return (
    <div role="alert" className="invalid-rows-warning">
      <button type="button" onClick={() => setExpanded((value) => !value)}>
        {t("invalidRows.title", { count: invalidRows.length })}
      </button>
      {expanded && (
        <ul>
          {invalidRows.map((row) => (
            <li key={row.row_number}>
              <strong>{t("invalidRows.rowLabel", { row: row.row_number })}</strong>
              {" — "}
              <span>{t("invalidRows.reasonLabel")}: </span>
              <code>{row.reason}</code>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
