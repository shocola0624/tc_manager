export type OffsetUnit = "d" | "h" | "m";

export interface OffsetRow {
  amount: number;
  unit: OffsetUnit;
}

const SEGMENT = /^-(\d+)([dhm])$/;

/** "-7d,-1d,-2h" のようなカンマ区切り文字列を行の配列に変換する。壊れた区間は無視する。 */
export function parseOffsets(value: string): OffsetRow[] {
  if (!value.trim()) return [];
  const rows: OffsetRow[] = [];
  for (const segment of value.split(",")) {
    const match = segment.trim().match(SEGMENT);
    if (!match) continue;
    rows.push({ amount: Number(match[1]), unit: match[2] as OffsetUnit });
  }
  return rows;
}

/** 行の配列を "-7d,-1d,-2h" のようなカンマ区切り文字列に変換する。0以下の行は書き出さない。 */
export function serializeOffsets(rows: OffsetRow[]): string {
  return rows
    .filter((row) => Number.isFinite(row.amount) && row.amount > 0)
    .map((row) => `-${Math.trunc(row.amount)}${row.unit}`)
    .join(",");
}
