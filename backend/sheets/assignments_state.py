from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from .schemas.assignments import AssignmentLogEntry
from .schemas.common import AssignmentAction


@dataclass(frozen=True)
class AssignmentSlot:
    """assignments ログを畳み込んだ後の「現在の割り当て」1件"""

    activity_id: str
    item_id: str | None
    custom_name: str | None
    assignee_id: str | None
    last_action_at: datetime
    last_actor_id: str


def fold_assignment_log(entries: Sequence[AssignmentLogEntry]) -> list[AssignmentSlot]:
    """追記専用ログを畳み込み、現在の割り当て状態を導出する純粋関数。

    - timestamp の昇順に処理する。timestamp が同一の場合は entries の入力順を
      タイブレークとする(list.sort/sorted は安定ソートであることを利用)。
    - 枠の識別キーは (activity_id, item_id または custom_name)。
    - 各枠について最後に記録された action が "add" のものだけを結果に含める。
      "remove" が最後の枠、および一度も add されていない枠は結果から除外される。

    read-modify-write は行わない: 入力は毎回シート全体の追記ログであり、
    出力はそこから導出される値であって、シートへ書き戻すための中間状態ではない。
    """
    latest_by_slot: dict[tuple[str, str], AssignmentLogEntry] = {}

    for entry in sorted(entries, key=lambda e: e.timestamp):
        latest_by_slot[(entry.activity_id, entry.slot_key)] = entry

    slots = [
        AssignmentSlot(
            activity_id=entry.activity_id,
            item_id=entry.item_id,
            custom_name=entry.custom_name,
            assignee_id=entry.assignee_id,
            last_action_at=entry.timestamp,
            last_actor_id=entry.actor_id,
        )
        for entry in latest_by_slot.values()
        if entry.action == AssignmentAction.ADD
    ]
    slots.sort(key=lambda slot: (slot.activity_id, slot.item_id or "", slot.custom_name or ""))
    return slots
