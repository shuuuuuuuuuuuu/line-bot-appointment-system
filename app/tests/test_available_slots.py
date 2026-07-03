from services.available_slots import get_available_slots_logic

MONDAY = "2030-01-07"
FRIDAY = "2030-01-04"


def test_weekday_returns_slots():
    slots = get_available_slots_logic([], [], [], [], MONDAY)
    assert "09:00" in slots
    assert "20:00" in slots
    assert len(slots) == 12


def test_off_day_returns_empty():
    slots = get_available_slots_logic([], [], [], [], FRIDAY)
    assert slots == []


def test_confirmed_slot_is_excluded():
    slots = get_available_slots_logic([], ["10:00"], [], [], MONDAY)
    assert "10:00" not in slots
    assert "09:00" in slots


def test_pending_slot_is_excluded():
    slots = get_available_slots_logic([], [], ["14:00"], [], MONDAY)
    assert "14:00" not in slots


def test_busy_calendar_slot_is_excluded():
    busy = [{"start": "2030-01-07T11:00:00+08:00", "end": "2030-01-07T12:00:00+08:00"}]
    slots = get_available_slots_logic(busy, [], [], [], MONDAY)
    assert "11:00" not in slots
