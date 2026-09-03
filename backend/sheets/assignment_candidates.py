from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .schemas.common import CIRCLE_OWNER_ID, AttendanceStatus, Storage
from .schemas.items import Item


@dataclass(frozen=True)
class ItemCandidate:
    """ある活動に対する、ある持ち物の候補判定結果(CLAUDE.md §5)。"""

    item: Item
    is_candidate: bool
    requires_assignee: bool
    default_assignee_id: str | None


def compute_item_candidates(
    items: Sequence[Item],
    attendance_by_user: Mapping[str, AttendanceStatus],
    *,
    extended_mode: bool,
) -> list[ItemCandidate]:
    """候補判定は所有者の種別ではなく storage で決まる(CLAUDE.md §5)。

    - clubroom: 常時候補。持参担当は不要
    - owner: 所有者が attending の場合のみ既定で候補に入り、持参担当は自動的に所有者になる。
      所有者が attending でない場合は extended_mode が True のときだけ候補に入り、
      その場合は受け渡しが発生するため持参担当の割り当てが必須になる
    - other: 常時候補。持参担当の割り当てが必須

    純粋関数であり、シートの読み書きは行わない。呼び出し元が items/attendance を
    あらかじめ取得しておくこと(items は is_active な行だけを渡す想定)。
    """
    candidates: list[ItemCandidate] = []
    for item in items:
        if item.storage == Storage.CLUBROOM:
            candidates.append(
                ItemCandidate(
                    item=item, is_candidate=True, requires_assignee=False, default_assignee_id=None
                )
            )
        elif item.storage == Storage.OTHER:
            candidates.append(
                ItemCandidate(
                    item=item, is_candidate=True, requires_assignee=True, default_assignee_id=None
                )
            )
        else:
            candidates.append(_owner_storage_candidate(item, attendance_by_user, extended_mode))
    return candidates


def _owner_storage_candidate(
    item: Item, attendance_by_user: Mapping[str, AttendanceStatus], extended_mode: bool
) -> ItemCandidate:
    if item.owner_id == CIRCLE_OWNER_ID:
        # storage=owner だが所有者がサークル自体という、本来想定されないデータ(シート直接編集で
        # 起こりうる)。個人の出欠という概念がないため other と同様に扱う。
        return ItemCandidate(item=item, is_candidate=True, requires_assignee=True, default_assignee_id=None)

    owner_attending = attendance_by_user.get(item.owner_id) == AttendanceStatus.ATTENDING
    if owner_attending:
        return ItemCandidate(
            item=item, is_candidate=True, requires_assignee=False, default_assignee_id=item.owner_id
        )
    return ItemCandidate(
        item=item, is_candidate=extended_mode, requires_assignee=True, default_assignee_id=None
    )
