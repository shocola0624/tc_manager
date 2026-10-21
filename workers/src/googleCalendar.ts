// Google Calendar API v3 への薄いREST呼び出し(sheets.ts と同じく fetch のみで実装し、
// クライアントライブラリは使わない)。同期の判断ロジックは calendarSync.ts 側に置き、
// ここは HTTP の入出力だけを扱う。

const CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3/calendars";

export class CalendarApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

export interface CalendarEventTime {
  dateTime: string;
  timeZone?: string;
}

/** このアプリが書き込む/読み取るイベントのフィールド(API のサブセット)。 */
export interface CalendarEvent {
  id: string;
  summary?: string;
  description?: string;
  location?: string;
  colorId?: string;
  start?: CalendarEventTime;
  end?: CalendarEventTime;
  status?: string;
  extendedProperties?: { private?: Record<string, string> };
}

async function calendarFetch(accessToken: string, url: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(url, {
    ...init,
    headers: { Authorization: `Bearer ${accessToken}`, "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    throw new CalendarApiError(
      `calendar API request failed: ${response.status} ${await response.text()}`,
      response.status,
    );
  }
  // DELETE は 204 No Content を返す
  if (response.status === 204) return null;
  return response.json();
}

function eventsUrl(calendarId: string): string {
  return `${CALENDAR_API_BASE}/${encodeURIComponent(calendarId)}/events`;
}

/** カレンダー上の(削除済みでない)イベントをページングしながらすべて取得する。
 * 同期先はこのアプリ専用の新規カレンダーを想定しているため件数は多くなく、
 * Cron 1回につき通常1リクエストで済む(maxResults の上限は 2500)。 */
export async function listEvents(accessToken: string, calendarId: string): Promise<CalendarEvent[]> {
  const events: CalendarEvent[] = [];
  let pageToken: string | undefined;
  do {
    const params = new URLSearchParams({ maxResults: "2500", showDeleted: "false" });
    if (pageToken) params.set("pageToken", pageToken);
    const body = (await calendarFetch(accessToken, `${eventsUrl(calendarId)}?${params.toString()}`)) as {
      items?: CalendarEvent[];
      nextPageToken?: string;
    };
    events.push(...(body.items ?? []));
    pageToken = body.nextPageToken;
  } while (pageToken);
  return events;
}

/** id を指定してイベントを作成する。同じ id のイベントが(削除済みとして)既に存在する
 * 場合は 409 になるため、呼び出し元は updateEvent にフォールバックすること。 */
export async function insertEvent(accessToken: string, calendarId: string, event: CalendarEvent): Promise<void> {
  await calendarFetch(accessToken, eventsUrl(calendarId), { method: "POST", body: JSON.stringify(event) });
}

/** イベント全体を置き換える(PUT)。status を "confirmed" で送れば削除済みのイベントも復活する。 */
export async function updateEvent(accessToken: string, calendarId: string, event: CalendarEvent): Promise<void> {
  await calendarFetch(accessToken, `${eventsUrl(calendarId)}/${encodeURIComponent(event.id)}`, {
    method: "PUT",
    body: JSON.stringify(event),
  });
}

/** イベントを削除する。既に削除済み(404/410)なら成功として扱う(冪等)。 */
export async function deleteEvent(accessToken: string, calendarId: string, eventId: string): Promise<void> {
  try {
    await calendarFetch(accessToken, `${eventsUrl(calendarId)}/${encodeURIComponent(eventId)}`, {
      method: "DELETE",
    });
  } catch (error) {
    if (error instanceof CalendarApiError && (error.status === 404 || error.status === 410)) return;
    throw error;
  }
}
