from datetime import datetime

from services.available_slots import get_available_slots_logic

MONDAY = "2030-01-07"
FRIDAY = "2030-01-04"


def test_weekday_returns_slots():
    slots = get_available_slots_logic([], [], [], [], MONDAY, is_open=True)
    assert "09:00" in slots
    assert "20:00" in slots
    assert len(slots) == 12


def test_closed_day_returns_empty():
    slots = get_available_slots_logic([], [], [], [], FRIDAY, is_open=False)
    assert slots == []


def test_custom_hours_and_interval():
    slots = get_available_slots_logic(
        [],
        [],
        [],
        [],
        MONDAY,
        is_open=True,
        open_hour=10,
        close_hour=12,
        slot_interval_minutes=30,
    )
    assert slots == ["10:00", "10:30", "11:00", "11:30"]


def test_confirmed_slot_is_excluded():
    confirmed = [{
        "start": "2030-01-07T10:00:00+08:00",
        "end": "2030-01-07T11:00:00+08:00",
    }]
    slots = get_available_slots_logic([], confirmed, [], [], MONDAY, is_open=True)
    assert "10:00" not in slots
    assert "09:00" in slots


def test_pending_slot_is_excluded():
    slots = get_available_slots_logic([], [], ["14:00"], [], MONDAY, is_open=True)
    assert "14:00" not in slots


def test_busy_calendar_slot_is_excluded():
    busy = [{"start": "2030-01-07T11:00:00+08:00", "end": "2030-01-07T12:00:00+08:00"}]
    slots = get_available_slots_logic(busy, [], [], [], MONDAY, is_open=True)
    assert "11:00" not in slots


def test_reiki_90min_plus_buffer_blocks_following_hours():
    confirmed = [{
        "start": "2030-01-07T13:00:00+08:00",
        "end": "2030-01-07T14:30:00+08:00",
    }]
    slots = get_available_slots_logic([], confirmed, [], [], MONDAY, is_open=True)
    assert "13:00" not in slots
    assert "14:00" not in slots
    assert "15:00" not in slots
    assert "16:00" in slots


def test_singing_bowl_70min_plus_buffer_blocks_following_hours():
    confirmed = [{
        "start": "2030-01-07T13:00:00+08:00",
        "end": "2030-01-07T14:10:00+08:00",
    }]
    slots = get_available_slots_logic([], confirmed, [], [], MONDAY, is_open=True)
    assert "13:00" not in slots
    assert "14:00" not in slots
    assert "15:00" not in slots
    assert "16:00" in slots
