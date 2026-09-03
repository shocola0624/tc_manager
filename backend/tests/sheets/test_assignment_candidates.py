from sheets.assignment_candidates import ItemCandidate, compute_item_candidates
from sheets.schemas import CIRCLE_OWNER_ID, AttendanceStatus, Item


def _item(**overrides) -> Item:
    defaults: dict[str, object] = dict(
        item_id="i1",
        owner_id="owner1",
        name="V60",
        maker="Hario",
        category="dripper",
        storage="clubroom",
        note="",
        is_active=True,
    )
    defaults.update(overrides)
    return Item(**defaults)


def test_clubroom_item_is_always_a_candidate_without_assignee():
    item = _item(storage="clubroom")

    [result] = compute_item_candidates([item], {}, extended_mode=False)

    assert result == ItemCandidate(
        item=item, is_candidate=True, requires_assignee=False, default_assignee_id=None
    )


def test_clubroom_item_is_candidate_even_in_extended_mode():
    item = _item(storage="clubroom")

    [result] = compute_item_candidates([item], {}, extended_mode=True)

    assert result.is_candidate is True
    assert result.requires_assignee is False


def test_other_item_is_always_a_candidate_and_requires_assignee():
    item = _item(storage="other")

    [result] = compute_item_candidates([item], {}, extended_mode=False)

    assert result.is_candidate is True
    assert result.requires_assignee is True
    assert result.default_assignee_id is None


def test_owner_item_is_candidate_with_default_assignee_when_owner_attending():
    item = _item(storage="owner", owner_id="owner1")
    attendance = {"owner1": AttendanceStatus.ATTENDING}

    [result] = compute_item_candidates([item], attendance, extended_mode=False)

    assert result.is_candidate is True
    assert result.requires_assignee is False
    assert result.default_assignee_id == "owner1"


def test_owner_item_is_excluded_by_default_when_owner_not_attending():
    item = _item(storage="owner", owner_id="owner1")
    attendance = {"owner1": AttendanceStatus.ABSENT}

    [result] = compute_item_candidates([item], attendance, extended_mode=False)

    assert result.is_candidate is False
    assert result.requires_assignee is True
    assert result.default_assignee_id is None


def test_owner_item_with_no_attendance_row_is_treated_as_not_attending():
    item = _item(storage="owner", owner_id="owner1")

    [result] = compute_item_candidates([item], {}, extended_mode=False)

    assert result.is_candidate is False


def test_owner_item_with_undecided_status_is_treated_as_not_attending():
    item = _item(storage="owner", owner_id="owner1")
    attendance = {"owner1": AttendanceStatus.UNDECIDED}

    [result] = compute_item_candidates([item], attendance, extended_mode=False)

    assert result.is_candidate is False


def test_owner_item_becomes_candidate_in_extended_mode_when_owner_not_attending():
    item = _item(storage="owner", owner_id="owner1")
    attendance = {"owner1": AttendanceStatus.ABSENT}

    [result] = compute_item_candidates([item], attendance, extended_mode=True)

    assert result.is_candidate is True
    assert result.requires_assignee is True
    assert result.default_assignee_id is None


def test_owner_item_with_circle_owner_is_treated_like_other():
    """storage=owner だが owner_id=CIRCLE という、シート直接編集で起こりうる不正な組み合わせ。
    個人の出欠という概念がないため常に候補・要担当割り当てとする。"""
    item = _item(storage="owner", owner_id=CIRCLE_OWNER_ID)

    result_default = compute_item_candidates([item], {}, extended_mode=False)[0]
    result_extended = compute_item_candidates([item], {}, extended_mode=True)[0]

    for result in (result_default, result_extended):
        assert result.is_candidate is True
        assert result.requires_assignee is True
        assert result.default_assignee_id is None


def test_computes_independently_for_multiple_items():
    clubroom_item = _item(item_id="i1", storage="clubroom")
    other_item = _item(item_id="i2", storage="other")
    owner_item = _item(item_id="i3", storage="owner", owner_id="owner1")
    attendance = {"owner1": AttendanceStatus.ATTENDING}

    results = compute_item_candidates(
        [clubroom_item, other_item, owner_item], attendance, extended_mode=False
    )

    by_id = {c.item.item_id: c for c in results}
    assert by_id["i1"].requires_assignee is False
    assert by_id["i2"].requires_assignee is True
    assert by_id["i3"].default_assignee_id == "owner1"
