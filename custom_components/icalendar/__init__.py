"""iCalendar integration setup and entry lifecycle."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.typing import ConfigType

from .const import CONF_CALENDAR_ENTITY_ID, CONF_SECRET, DOMAIN
from .http import ICalendarView
from .models import ICalendarRuntimeData
from .weekplan import AulaWeekplanHistory


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the iCalendar component."""
    hass.data.setdefault(DOMAIN, {})
    if not hass.data[DOMAIN].get("view_registered"):
        hass.http.register_view(ICalendarView(hass))
        hass.data[DOMAIN]["view_registered"] = True
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up iCalendar from a config entry."""
    entity_id = entry.data[CONF_CALENDAR_ENTITY_ID]
    weekplan = None
    if entity_id.startswith("sensor."):
        weekplan = AulaWeekplanHistory(hass, entry.entry_id, entity_id)
        await weekplan.async_start()
    elif hass.states.get(entity_id) is None:
        raise ConfigEntryNotReady(f"Feed source not ready: {entity_id}")

    entry.runtime_data = ICalendarRuntimeData(
        calendar_entity_id=entity_id,
        secret=entry.data[CONF_SECRET],
        weekplan=weekplan,
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an iCalendar config entry."""
    if entry.runtime_data.weekplan is not None:
        await entry.runtime_data.weekplan.async_stop()
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove the archive when the feed is deleted."""
    await AulaWeekplanHistory.storage(hass, entry.entry_id).async_remove()
