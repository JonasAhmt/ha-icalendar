"""HTTP view for iCalendar feed exposure."""

from __future__ import annotations

import hmac
from http import HTTPStatus
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import CONTENT_TYPE_ICAL, DOMAIN, URL_PATH_PREFIX
from .ical import aula_weekplan_events, build_icalendar, is_supported_source
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
        if state is None:
            return web.Response(body="404: Not Found", status=HTTPStatus.NOT_FOUND)
        if not is_supported_source(entity_id, state.attributes):
            return web.Response(body="403: Forbidden", status=HTTPStatus.FORBIDDEN)

        if entity_id.startswith("calendar."):
            events = await self._fetch_events(entity_id)
            calendar_name = state.name
        else:
            events = aula_weekplan_events(state.attributes)
            calendar_name = f"Ugeplan {state.name}"
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
