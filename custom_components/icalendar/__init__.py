"""iCalendar integration setup and entry lifecycle."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.typing import ConfigType

from .const import CONF_CALENDAR_ENTITY_ID, CONF_SECRET, DOMAIN
from .http import ICalendarView
from .ical import is_supported_source
from .models import ICalendarRuntimeData


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
    state = hass.states.get(entity_id)
    if state is None or not is_supported_source(entity_id, state.attributes):
        raise ConfigEntryNotReady(f"Feed source not ready: {entity_id}")

    entry.runtime_data = ICalendarRuntimeData(
        calendar_entity_id=entity_id,
        secret=entry.data[CONF_SECRET],
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an iCalendar config entry."""
    return True
