// Sheets API v4 への薄いREST呼び出し。backend/sheets/client.py と同じ考え方
// (列順に依存しない・1行ずつではなくまとめて読み書きする、CLAUDE.md §8)を
// Workers(Web標準 fetch のみ)で再実装する。googleapiclient のような
// クライアントライブラリは使わない。

const SHEETS_API_BASE = "https://sheets.googleapis.com/v4/spreadsheets";

function quoteSheetName(sheetName: string): string {
  return `'${sheetName.replace(/'/g, "''")}'`;
}

async function sheetsFetch(accessToken: string, url: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(url, {
    ...init,
    headers: { Authorization: `Bearer ${accessToken}`, "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    throw new Error(`sheets API request failed: ${response.status} ${await response.text()}`);
  }
  return response.json();
}

/** 複数シートを1回のAPI呼び出しでまとめて読む(Cron 1回につきシートごとに
 * バラバラに呼ばない、CLAUDE.md §8)。シートが空なら values は含まれない。 */
export async function batchGetValues(
  accessToken: string,
  spreadsheetId: string,
  sheetNames: string[],
): Promise<string[][][]> {
  const params = new URLSearchParams();
  for (const name of sheetNames) params.append("ranges", quoteSheetName(name));
  const body = (await sheetsFetch(
    accessToken,
    `${SHEETS_API_BASE}/${spreadsheetId}/values:batchGet?${params.toString()}`,
  )) as { valueRanges?: { values?: string[][] }[] };
  return (body.valueRanges ?? []).map((range) => range.values ?? []);
}

/** 複数行を1回のAPI呼び出しで追記する(reminder_log への書き込みをこの関数で
 * まとめ、送信件数ぶん1行ずつ呼ばないようにする)。rows が空なら何もしない。 */
export async function appendRows(
  accessToken: string,
  spreadsheetId: string,
  sheetName: string,
  rows: string[][],
): Promise<void> {
  if (rows.length === 0) return;
  await sheetsFetch(
    accessToken,
    `${SHEETS_API_BASE}/${spreadsheetId}/values/${encodeURIComponent(quoteSheetName(sheetName))}:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS`,
    { method: "POST", body: JSON.stringify({ values: rows }) },
  );
}

/** ヘッダ行(1行目)を使って列名→値のレコードに変換する。列順に依存しない
 * (CLAUDE.md §8)。ヘッダに無い列は無視し、行末の欠けたセルは空文字として扱う。 */
export function rowsToRecords(rows: string[][]): Record<string, string>[] {
  if (rows.length === 0) return [];
  const header = rows[0]!;
  return rows.slice(1).map((row) => {
    const record: Record<string, string> = {};
    header.forEach((name, index) => {
      if (!name) return;
      record[name] = row[index] ?? "";
    });
    return record;
  });
}

/** レコードをヘッダ順の行(文字列配列)に変換する。レコードに無い列は空文字。 */
export function recordToRow(record: Record<string, string>, header: string[]): string[] {
  return header.map((name) => record[name] ?? "");
}

/** 0始まりの列インデックスを A1 表記の列名に変換する(0 -> "A", 26 -> "AA")。 */
export function columnLetter(index: number): string {
  let letters = "";
  let n = index + 1;
  while (n > 0) {
    const remainder = (n - 1) % 26;
    letters = String.fromCharCode(65 + remainder) + letters;
    n = Math.floor((n - 1) / 26);
  }
  return letters;
}

export interface CellUpdate {
  sheetName: string;
  /** 1始まりの行番号(ヘッダ行が1)。 */
  rowNumber: number;
  /** 0始まりの列インデックス。ヘッダ行から求めること(列順に依存しない、CLAUDE.md §8)。 */
  columnIndex: number;
  value: string;
}

/** 複数セルを1回のAPI呼び出しで書き換える。updates が空なら何もしない。 */
export async function batchUpdateCells(
  accessToken: string,
  spreadsheetId: string,
  updates: CellUpdate[],
): Promise<void> {
  if (updates.length === 0) return;
  await sheetsFetch(accessToken, `${SHEETS_API_BASE}/${spreadsheetId}/values:batchUpdate`, {
    method: "POST",
    body: JSON.stringify({
      valueInputOption: "RAW",
      data: updates.map((update) => ({
        range: `${quoteSheetName(update.sheetName)}!${columnLetter(update.columnIndex)}${update.rowNumber}`,
        values: [[update.value]],
      })),
    }),
  });
}
