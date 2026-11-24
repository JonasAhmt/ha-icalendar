"""Persist Aula week-plan snapshots as the source rolls forward."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.const import DOMAIN as RECORDER_DOMAIN
from homeassistant.components.recorder.history import state_changes_during_period
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DEFAULT_HISTORY_WEEKS, DOMAIN
from .ical import aula_weekplan_events, is_supported_source


class AulaWeekplanHistory:
    """Keep one archived event per date for a configured Aula sensor."""

    def __init__(self, hass: HomeAssistant, entry_id: str, entity_id: str) -> None:
        self.hass = hass
        self.entity_id = entity_id
        self._store = self.storage(hass, entry_id)
        self._events: dict[str, dict[str, str]] = {}
        self._unsubscribe = None

    @staticmethod
    def storage(hass: HomeAssistant, entry_id: str) -> Store[dict[str, Any]]:
        """Create the store for one feed."""
        return Store(hass, 1, f"{DOMAIN}.weekplan.{entry_id}", private=True, atomic_writes=True)

    async def async_start(self) -> None:
        """Restore the archive, then track source updates independently of feed requests."""
        stored = await self._store.async_load()
        if stored and stored["entity_id"] == self.entity_id:
            self._events = stored["events"]
        elif RECORDER_DOMAIN in self.hass.config.components:
            recorder = get_instance(self.hass)
            self._events = await recorder.async_add_executor_job(self._recorded_events)

        if state := self.hass.states.get(self.entity_id):
            self._events = _merge_snapshot(self._events, state)
        self._unsubscribe = async_track_state_change_event(
            self.hass, self.entity_id, self._async_source_changed
        )
        self._store.async_delay_save(self._storage_data)

    @callback
    def _async_source_changed(self, event: Event[EventStateChangedData]) -> None:
        """Merge an available source snapshot into the archive."""
        if (state := event.data["new_state"]) is None:
            return
        updated = _merge_snapshot(self._events, state)
        if updated != self._events:
            self._events = updated
            self._store.async_delay_save(self._storage_data)

    def _storage_data(self) -> dict[str, Any]:
        return {"entity_id": self.entity_id, "events": self._events}

    async def async_stop(self) -> None:
        """Finish saving before a config entry reload can read the store again."""
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        await self._store.async_save(self._storage_data())

    @callback
    def events(self) -> list[dict[str, str]]:
        """Read the current feed window in date order."""
        today = dt_util.now().date()
        cutoff = (today - timedelta(weeks=DEFAULT_HISTORY_WEEKS)).isoformat()
        return [event for day, event in sorted(self._events.items()) if day >= cutoff]

    def _recorded_events(self) -> dict[str, dict[str, str]]:
        """Seed a new archive with any snapshots still available in Recorder."""
        start = dt_util.utcnow() - timedelta(weeks=DEFAULT_HISTORY_WEEKS)
        states = state_changes_during_period(
            self.hass, start, entity_id=self.entity_id, include_start_time_state=False
        ).get(self.entity_id, [])
        events: dict[str, dict[str, str]] = {}
        for state in states:
            events = _merge_snapshot(events, state)
        return events


def _merge_snapshot(
    history: dict[str, dict[str, str]], state: State
) -> dict[str, dict[str, str]]:
    """Keep past days and replace today's and future days from Aula."""
    if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN) or not is_supported_source(
        state.entity_id, state.attributes
    ):
        return history

    snapshot_date = dt_util.as_local(state.last_updated).date()
    cutoff = (snapshot_date - timedelta(weeks=DEFAULT_HISTORY_WEEKS)).isoformat()
    today = snapshot_date.isoformat()
    events = {day: event for day, event in history.items() if cutoff <= day < today}
    events.update(
        (event["start"], event)
        for event in aula_weekplan_events(state.attributes, snapshot_date)
    )
    return events
