/**
 * date("YYYY-MM-DD")と time("HH:MM")を JST 固定の ISO 8601 文字列に結合する。
 * ブラウザのローカルタイムゾーンに依存させない(常に +09:00 を付与する)。
 */
export function combineDateAndTimeToJstIso(date: string, time: string): string {
  return `${date}T${time}:00+09:00`;
}

/**
 * combineDateAndTimeToJstIso の逆変換。編集フォームの初期値を作るために使う。
 * 常に +09:00 で書き込まれている前提で文字列として素直に分解する
 * (Date を経由するとブラウザのローカルタイムゾーンで再解釈されてしまうため)。
 */
export function splitJstIso(iso: string): { date: string; time: string } {
  const match = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/.exec(iso);
  if (!match) {
    return { date: "", time: "" };
  }
  const [, date, time] = match;
  return { date, time };
}

/**
 * starts_at(ISO 8601)と duration_min から終了時刻を算出する。CLAUDE.md §4 のとおり
 * シートには保存せず、表示のためだけにその場で計算する。
 */
export function computeEndTimeIso(startsAt: string, durationMinutes: number): string {
  const start = new Date(startsAt);
  const end = new Date(start.getTime() + durationMinutes * 60_000);
  return end.toISOString();
}

/**
 * 活動が「今後」タブに入るかどうか。終了時刻が現在時刻を過ぎていなければ今後扱い
 * (開催中の活動は「過去」に落とさない)。
 */
export function isUpcoming(
  startsAt: string,
  durationMinutes: number,
  now: Date = new Date(),
): boolean {
  const end = new Date(computeEndTimeIso(startsAt, durationMinutes));
  return end.getTime() >= now.getTime();
}
