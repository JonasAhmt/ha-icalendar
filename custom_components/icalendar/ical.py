"""iCalendar formatting and color resolution."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from datetime import date, datetime, timezone
from typing import Any

from homeassistant.components import frontend
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from ical.calendar import Calendar
from ical.calendar_stream import IcsCalendarStream
from ical.event import Event


def build_icalendar(
    hass: HomeAssistant,
    entity_id: str,
    calendar_name: str,
    events: list[dict[str, Any]],
) -> str:
    """Build iCalendar feed output using HA's shared ical library."""
    calendar = Calendar()
    calendar.prodid = "-//Home Assistant//iCal Subscription 2.0//EN"
    calendar.version = "2.0"
    calendar.calscale = "GREGORIAN"
    calendar.method = "PUBLISH"

    for ha_event in events:
        if event := event_from_ha(entity_id, ha_event):
            calendar.events.append(event)

    output = IcsCalendarStream.calendar_to_ics(calendar)
    return inject_calendar_metadata(
        output,
        calendar_name=calendar_name,
        calendar_color=resolve_calendar_color(hass, entity_id),
    )


def inject_calendar_metadata(ics: str, calendar_name: str, calendar_color: str | None) -> str:
    """Inject NAME/X-WR-CALNAME/COLOR in VCALENDAR headers."""
    lines = ics.splitlines()
    injected: list[str] = []
    inserted = False
    for line in lines:
        injected.append(line)
        if not inserted and line == "METHOD:PUBLISH":
            injected.append(f"NAME:{calendar_name}")
            injected.append(f"X-WR-CALNAME:{calendar_name}")
            if calendar_color:
                injected.append(f"COLOR:{calendar_color}")
            inserted = True
    return "\r\n".join(injected) + "\r\n"


def event_from_ha(entity_id: str, event: dict[str, Any]) -> Event | None:
    """Convert Home Assistant event payload to an ical.Event."""
    try:
        start = parse_ha_datetime_or_date(event["start"])
        end = parse_ha_datetime_or_date(event["end"])
    except (KeyError, ValueError, TypeError):
        return None

    if isinstance(start, datetime) and start.tzinfo:
        start = start.astimezone(timezone.utc)
    if isinstance(end, datetime) and end.tzinfo:
        end = end.astimezone(timezone.utc)

    summary = str(event.get("summary") or "")
    description = event.get("description")
    location = event.get("location")
    uid = "\x1f".join(
        (
            entity_id,
            start.isoformat(),
            end.isoformat(),
            summary,
            str(description or ""),
            str(location or ""),
        )
    )

    return Event(
        uid=hashlib.sha256(uid.encode()).hexdigest(),
        summary=summary,
        start=start,
        end=end,
        description=description,
        location=location,
    )


def parse_ha_datetime_or_date(value: str) -> datetime | date:
    """Parse HA event date/datetime string."""
    if "T" in value:
        return datetime.fromisoformat(value)
    return datetime.strptime(value, "%Y-%m-%d").date()


def resolve_calendar_color(hass: HomeAssistant, entity_id: str) -> str | None:
    """Resolve calendar color from HA entity options."""
    resolved: str | None = None
    registry = er.async_get(hass)
    if registry_entry := registry.async_get(entity_id):
        if color := registry_entry.options.get("calendar", {}).get("color"):
            resolved = str(color)
    return normalize_calendar_color(hass, resolved)


def normalize_calendar_color(hass: HomeAssistant, color: str | None) -> str | None:
    """Normalize calendar color token into a concrete ICS-friendly color."""
    if not color:
        return None

    value = color.strip()
    if not value:
        return None

    if is_hex_color(value) or is_css_color_name(value):
        return value

    lowered = value.lower()
    theme_vars = active_theme_vars(hass)
    semantic_map = {
        "primary": "primary-color",
        "accent": "accent-color",
    }
    if (theme_key := semantic_map.get(lowered)) and (theme_value := theme_vars.get(theme_key)):
        theme_color = str(theme_value).strip()
        if is_hex_color(theme_color) or is_css_color_name(theme_color):
            return theme_color

    if lowered == "primary":
        return frontend.DEFAULT_THEME_COLOR

    return None


def active_theme_vars(hass: HomeAssistant) -> Mapping[str, Any]:
    """Return active frontend theme variables if available."""
    themes = hass.data.get(frontend.DATA_THEMES, {})
    if not isinstance(themes, dict):
        return {}

    active_theme = hass.data.get(frontend.DATA_DEFAULT_THEME, frontend.DEFAULT_THEME)
    if not active_theme or active_theme == frontend.DEFAULT_THEME:
        return {}

    variables = themes.get(active_theme, {})
    if isinstance(variables, dict):
        return variables
    return {}


def is_hex_color(value: str) -> bool:
    """Check whether value is a #RGB or #RRGGBB hex color."""
    return bool(re.fullmatch(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?", value))


def is_css_color_name(value: str) -> bool:
    """Basic CSS color keyword sanity check."""
    return bool(re.fullmatch(r"[a-zA-Z][a-zA-Z0-9-]*", value))
