from datetime import datetime, timedelta, timezone

from sheets.assignments_state import fold_assignment_log
from sheets.schemas import AssignmentAction, AssignmentLogEntry

JST = timezone(timedelta(hours=9))


def _entry(**overrides: object) -> AssignmentLogEntry:
    defaults: dict[str, object] = dict(
        timestamp=datetime(2026, 9, 1, 12, 0, tzinfo=JST),
        activity_id="a1",
        item_id="i1",
        custom_name=None,
        assignee_id=None,
        action=AssignmentAction.ADD,
        actor_id="u1",
    )
    defaults.update(overrides)
    return AssignmentLogEntry(**defaults)


def test_empty_log_has_no_active_slots():
    assert fold_assignment_log([]) == []


def test_add_then_remove_results_in_no_active_slot():
    entries = [
        _entry(timestamp=datetime(2026, 9, 1, 10, 0, tzinfo=JST), action=AssignmentAction.ADD),
        _entry(timestamp=datetime(2026, 9, 1, 11, 0, tzinfo=JST), action=AssignmentAction.REMOVE),
    ]

    assert fold_assignment_log(entries) == []


def test_add_remove_add_results_in_one_active_slot():
    entries = [
        _entry(timestamp=datetime(2026, 9, 1, 10, 0, tzinfo=JST), action=AssignmentAction.ADD),
        _entry(timestamp=datetime(2026, 9, 1, 11, 0, tzinfo=JST), action=AssignmentAction.REMOVE),
        _entry(
            timestamp=datetime(2026, 9, 1, 12, 0, tzinfo=JST),
            action=AssignmentAction.ADD,
            assignee_id="u2",
        ),
    ]

    result = fold_assignment_log(entries)

    assert len(result) == 1
    assert result[0].assignee_id == "u2"


def test_out_of_order_timestamps_are_sorted_before_folding():
    entries = [
        _entry(timestamp=datetime(2026, 9, 1, 12, 0, tzinfo=JST), action=AssignmentAction.ADD, assignee_id="u2"),
        _entry(timestamp=datetime(2026, 9, 1, 10, 0, tzinfo=JST), action=AssignmentAction.ADD, assignee_id="u1"),
        _entry(timestamp=datetime(2026, 9, 1, 11, 0, tzinfo=JST), action=AssignmentAction.REMOVE),
    ]

    result = fold_assignment_log(entries)

    assert len(result) == 1
    assert result[0].assignee_id == "u2"


def test_equal_timestamps_break_ties_by_input_order():
    ts = datetime(2026, 9, 1, 10, 0, tzinfo=JST)

    add_wins = [
        _entry(timestamp=ts, action=AssignmentAction.REMOVE),
        _entry(timestamp=ts, action=AssignmentAction.ADD, assignee_id="u1"),
    ]
    result = fold_assignment_log(add_wins)
    assert len(result) == 1
    assert result[0].assignee_id == "u1"

    remove_wins = [
        _entry(timestamp=ts, action=AssignmentAction.ADD, assignee_id="u1"),
        _entry(timestamp=ts, action=AssignmentAction.REMOVE),
    ]
    assert fold_assignment_log(remove_wins) == []


def test_item_and_custom_name_slots_are_independent_even_with_same_activity():
    entries = [
        _entry(item_id="i1", custom_name=None, action=AssignmentAction.ADD, assignee_id="u1"),
        _entry(item_id=None, custom_name="借り物のドリッパー", action=AssignmentAction.ADD, assignee_id="u2"),
    ]

    result = fold_assignment_log(entries)

    assert {(slot.item_id, slot.custom_name) for slot in result} == {
        ("i1", None),
        (None, "借り物のドリッパー"),
    }


def test_same_item_id_across_different_activities_are_independent_slots():
    entries = [
        _entry(activity_id="a1", action=AssignmentAction.ADD),
        _entry(activity_id="a2", action=AssignmentAction.ADD),
    ]

    result = fold_assignment_log(entries)

    assert {slot.activity_id for slot in result} == {"a1", "a2"}


def test_clubroom_item_without_assignee_can_still_form_an_active_slot():
    entries = [_entry(assignee_id=None, action=AssignmentAction.ADD)]

    result = fold_assignment_log(entries)

    assert len(result) == 1
    assert result[0].assignee_id is None
