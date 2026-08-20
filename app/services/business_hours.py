"""Resolve effective business hours for a given date."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, List, Optional
import json

from sqlalchemy.orm import Session

from db import models


@dataclass(frozen=True)
class TimeSlot:
    open_hour: int
    close_hour: int


@dataclass(frozen=True)
class ResolvedDayHours:
    is_open: bool
    open_hour: Optional[int] = None
    close_hour: Optional[int] = None
    time_slots: Optional[List[TimeSlot]] = None
    source: str = "weekly"  # weekly | override
    note: Optional[str] = None


def _slot_pair_from_item(item) -> Optional[tuple[int, int]]:
    if item is None:
        return None
    if isinstance(item, dict):
        o, c = item.get("open_hour"), item.get("close_hour")
    elif hasattr(item, "model_dump"):
        data = item.model_dump()
        o, c = data.get("open_hour"), data.get("close_hour")
    else:
        o = getattr(item, "open_hour", None)
        c = getattr(item, "close_hour", None)
    if isinstance(o, int) and isinstance(c, int) and 0 <= o < c <= 24:
        return int(o), int(c)
    return None


def _normalize_time_slots(raw, fallback_open: Optional[int], fallback_close: Optional[int]) -> List[TimeSlot]:
    slots: List[TimeSlot] = []
    try:
        parsed = json.loads(raw or "[]") if isinstance(raw, str) else raw
        if isinstance(parsed, list):
            for item in parsed:
                pair = _slot_pair_from_item(item)
                if pair is not None:
                    o, c = pair
                    slots.append(TimeSlot(open_hour=o, close_hour=c))
    except Exception:
        pass

    if not slots and fallback_open is not None and fallback_close is not None and fallback_open < fallback_close:
        slots = [TimeSlot(open_hour=fallback_open, close_hour=fallback_close)]
    return slots


def _weekly_map(db: Session) -> Dict[int, models.BusinessWeeklyHours]:
    rows = (
        db.query(models.BusinessWeeklyHours)
        .order_by(models.BusinessWeeklyHours.weekday.asc())
        .all()
    )
    return {row.weekday: row for row in rows}


def _override_map(db: Session) -> Dict[date, models.BusinessDateOverride]:
    rows = (
        db.query(models.BusinessDateOverride)
        .order_by(models.BusinessDateOverride.target_date.asc())
        .all()
    )
    return {row.target_date: row for row in rows}


def resolve_business_hours_for_date(
    db: Session,
    target: date,
    *,
    weekly_by_weekday: Optional[Dict[int, models.BusinessWeeklyHours]] = None,
    overrides_by_date: Optional[Dict[date, models.BusinessDateOverride]] = None,
) -> ResolvedDayHours:
    overrides = overrides_by_date if overrides_by_date is not None else _override_map(db)
    override = overrides.get(target)
    if override is not None:
        if not override.is_open:
            return ResolvedDayHours(
                is_open=False,
                source="override",
                note=override.note,
            )
        slots = _normalize_time_slots(override.time_slots, override.open_hour, override.close_hour)
        return ResolvedDayHours(
            is_open=True,
            open_hour=slots[0].open_hour if slots else override.open_hour,
            close_hour=slots[-1].close_hour if slots else override.close_hour,
            time_slots=slots,
            source="override",
            note=override.note,
        )

    weekly = weekly_by_weekday if weekly_by_weekday is not None else _weekly_map(db)
    template = weekly.get(target.weekday())
    if template is None or not template.is_open:
        return ResolvedDayHours(is_open=False, source="weekly")

    slots = _normalize_time_slots(template.time_slots, template.open_hour, template.close_hour)
    return ResolvedDayHours(
        is_open=True,
        open_hour=slots[0].open_hour if slots else template.open_hour,
        close_hour=slots[-1].close_hour if slots else template.close_hour,
        time_slots=slots,
        source="weekly",
    )


def resolve_business_hours_for_date_str(db: Session, target_date_str: str) -> ResolvedDayHours:
    target = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    return resolve_business_hours_for_date(db, target)


def is_time_within_resolved_hours(
    resolved: ResolvedDayHours,
    time_str: str,
    *,
    slot_interval_minutes: int,
) -> bool:
    if not resolved.is_open:
        return False

    slot_start = datetime.strptime(time_str, "%H:%M")
    slot_end_minutes = slot_start.hour * 60 + slot_start.minute + max(slot_interval_minutes, 15)
    slot_start_minutes = slot_start.hour * 60 + slot_start.minute

    slots = resolved.time_slots or []
    if slots:
        return any(
            slot_start_minutes >= item.open_hour * 60 and slot_end_minutes <= item.close_hour * 60
            for item in slots
        )

    if resolved.open_hour is None or resolved.close_hour is None:
        return False

    open_minutes = resolved.open_hour * 60
    close_minutes = resolved.close_hour * 60
    return slot_start_minutes >= open_minutes and slot_end_minutes <= close_minutes


def derive_legacy_fields(weekly_rows: List[models.BusinessWeeklyHours]) -> tuple[int, int, List[int]]:
    open_days = [row for row in weekly_rows if row.is_open]
    if not open_days:
        return 9, 21, list(range(7))

    open_hour = min(row.open_hour for row in open_days)
    close_hour = max(row.close_hour for row in open_days)
    off_weekdays = sorted(
        row.weekday for row in weekly_rows if not row.is_open
    )
    return open_hour, close_hour, off_weekdays
