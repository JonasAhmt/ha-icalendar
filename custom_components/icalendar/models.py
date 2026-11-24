"""Data models for iCalendar integration runtime."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .const import (
    CONF_CALENDAR_ENTITY_ID,
    CONF_CALENDAR_ENTITY_IDS,
    CONF_LEGACY_UIDS,
    CONF_SELECTION_MODE,
    MODE_INCLUDE,
)
from .weekplan import AulaWeekplanHistory


def calendar_selection(data: Mapping[str, Any]) -> tuple[str, list[str]]:
    """Read selection, including legacy single-calendar entries."""
    entities = data.get(CONF_CALENDAR_ENTITY_IDS)
    if entities is None:
        entity = data.get(CONF_CALENDAR_ENTITY_ID)
        entities = [entity] if entity else []
    return data.get(CONF_SELECTION_MODE, MODE_INCLUDE), list(dict.fromkeys(entities))


def weekplan_source(mode: str, entity_ids: list[str]) -> str | None:
    """Identify a standalone Aula feed selection."""
    if mode == MODE_INCLUDE and len(entity_ids) == 1 and entity_ids[0].startswith("sensor."):
        return entity_ids[0]
    return None


def uses_legacy_uids(data: Mapping[str, Any]) -> bool:
    """Keep the original event IDs for feeds created before combined feeds."""
    return data.get(CONF_LEGACY_UIDS, CONF_CALENDAR_ENTITY_ID in data)


@dataclass(slots=True)
class ICalendarRuntimeData:
    """Runtime data for one config entry."""

    calendar_entity_ids: list[str]
    selection_mode: str
    secret: str
    geocoding_url: str = ""
    legacy_uids: bool = False
    weekplan: AulaWeekplanHistory | None = None

    cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    store: Any = None
