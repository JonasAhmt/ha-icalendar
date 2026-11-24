"""HTTP view for iCalendar feed exposure."""

from __future__ import annotations

import hmac
from http import HTTPStatus
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONTENT_TYPE_ICAL, DOMAIN, URL_PATH_PREFIX
from .ical import build_icalendar
from .models import ICalendarRuntimeData


class ICalendarView(HomeAssistantView):
    """Serve iCalendar feeds."""

    name = DOMAIN
    url = f"{URL_PATH_PREFIX}/{{entry_id}}/{{secret}}"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request, entry_id: str, secret: str) -> web.Response:
        """Handle iCalendar feed requests."""
        entry = self.hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN:
            return web.Response(body="404: Not Found", status=HTTPStatus.NOT_FOUND)

        runtime_data = getattr(entry, "runtime_data", None)
        if runtime_data is None or not isinstance(runtime_data, ICalendarRuntimeData):
            return web.Response(body="503: Service Unavailable", status=HTTPStatus.SERVICE_UNAVAILABLE)

        if not secret or not runtime_data.secret:
            return web.Response(body="403: Forbidden", status=HTTPStatus.FORBIDDEN)

        if not hmac.compare_digest(str(secret), str(runtime_data.secret)):
            return web.Response(body="401: Unauthorized", status=HTTPStatus.UNAUTHORIZED)

        entity_id = runtime_data.calendar_entity_id
        state = self.hass.states.get(entity_id)
        if runtime_data.weekplan is not None:
            events = runtime_data.weekplan.events()
            if not events and (state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN)):
                return web.Response(body="503: Service Unavailable", status=HTTPStatus.SERVICE_UNAVAILABLE)
            if state:
                source_name = state.name
            elif registry_entry := er.async_get(self.hass).async_get(entity_id):
                source_name = registry_entry.name or registry_entry.original_name or entity_id
            else:
                source_name = entity_id
            calendar_name = f"Ugeplan {source_name}"
        elif state is not None:
            events = await self._fetch_events(entity_id)
            calendar_name = state.name
        else:
            return web.Response(body="404: Not Found", status=HTTPStatus.NOT_FOUND)
        if events is None:
            return web.Response(body="404: Not Found", status=HTTPStatus.NOT_FOUND)

        feed = build_icalendar(self.hass, entity_id, calendar_name, events)
        return web.Response(body=feed, content_type=CONTENT_TYPE_ICAL, charset="utf-8")

    async def _fetch_events(self, entity_id: str) -> list[dict[str, Any]] | None:
        """Fetch events from Home Assistant calendar service."""
        from datetime import datetime, timedelta, timezone

        from .const import DEFAULT_FUTURE_WEEKS, DEFAULT_HISTORY_WEEKS

        start = datetime.now(timezone.utc) - timedelta(weeks=DEFAULT_HISTORY_WEEKS)
        end = datetime.now(timezone.utc) + timedelta(weeks=DEFAULT_FUTURE_WEEKS)

        events_response = await self.hass.services.async_call(
            "calendar",
            "get_events",
            {
                "entity_id": entity_id,
                "start_date_time": start.isoformat(),
                "end_date_time": end.isoformat(),
            },
            blocking=True,
            return_response=True,
        )
        if not events_response or entity_id not in events_response:
            return None
        return events_response[entity_id].get("events", [])
