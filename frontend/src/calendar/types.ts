// イベントソースの共通インターフェース。活動・タスクそれぞれが変換関数
// (eventSources.ts の activityToEvent / taskToEvent)を実装し、カレンダーは
// この形に揃ったイベントを合成して表示するだけにする。後から新しい種類
// (例: 会議・予約)を足す場合も、この型に変換する関数を1つ足すだけでよく、
// CalendarPage 側の変更は不要にする。
export type EventKind = "activity" | "task" | "task_done";

export interface CalendarEvent {
  source: "activity" | "task";
  source_id: string;
  title: string;
  starts_at: string;
  ends_at?: string;
  kind: EventKind;
}
