/** 月表示用のカレンダーグリッド計算。タイムゾーン変換を一切経由しない
 * (Date は「年月日の組」を表すためだけに使い、実時刻としては扱わない)。 */

export interface MonthCursor {
  year: number;
  /** 0始まり(JS の Date と合わせる) */
  month: number;
}

function pad2(value: number): string {
  return String(value).padStart(2, "0");
}

/** Date を "YYYY-MM-DD" に変換する(ローカルの年月日をそのまま使う。
 * toISOString は UTC 変換が入るため使わない)。 */
export function dateKey(date: Date): string {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
}

/** ISO8601 文字列(常に +09:00 で保存されている前提)から JST の日付部分だけを取り出す。
 * new Date(iso) 経由だとブラウザのローカルタイムゾーンで再解釈されてしまうため使わない。 */
export function jstDateKeyFromIso(iso: string): string {
  return iso.slice(0, 10);
}

/** 指定月を含む6週間(42日)分の Date 配列を返す(前後月の日もグリッドを埋めるために含む)。
 * 週の始まりは日曜日。 */
export function getMonthGrid({ year, month }: MonthCursor): Date[] {
  const firstOfMonth = new Date(year, month, 1);
  const startOffset = firstOfMonth.getDay();
  const start = new Date(year, month, 1 - startOffset);

  const days: Date[] = [];
  for (let i = 0; i < 42; i++) {
    days.push(new Date(start.getFullYear(), start.getMonth(), start.getDate() + i));
  }
  return days;
}

export function addMonths(cursor: MonthCursor, delta: number): MonthCursor {
  const base = new Date(cursor.year, cursor.month + delta, 1);
  return { year: base.getFullYear(), month: base.getMonth() };
}
