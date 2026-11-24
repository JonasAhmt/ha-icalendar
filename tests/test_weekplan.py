"""Regression tests for the Aula week-plan archive."""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, State

from custom_components.icalendar import weekplan


def test_weekplans_survive_rollover_and_reload(tmp_path, monkeypatch) -> None:
    """Backfill old snapshots and retain observed days without a feed request."""
    entity_id = "sensor.aula"

    async def check_history() -> None:
        hass = HomeAssistant(str(tmp_path))
        hass.config.components.add(weekplan.RECORDER_DOMAIN)
        archive = weekplan.AulaWeekplanHistory(hass, "entry", entity_id)
        now = datetime(2026, 9, 14, 9, tzinfo=timezone.utc)
        monkeypatch.setattr(weekplan.dt_util, "now", lambda: now)

        states = [
            State(
                entity_id,
                "ready",
                {"ugeplan": "<h3>fredag 11. sep.</h3>Recorded plan"},
                last_updated=datetime(2026, 9, 11, 9, tzinfo=timezone.utc),
            )
        ]
        run_query = AsyncMock(side_effect=lambda query: query())
        monkeypatch.setattr(
            weekplan, "get_instance", lambda _: SimpleNamespace(async_add_executor_job=run_query)
        )
        monkeypatch.setattr(
            weekplan, "state_changes_during_period", lambda *args, **kwargs: {entity_id: states}
        )
        hass.states.async_set(
            entity_id,
            "ready",
            {
                "ugeplan": "<h3>mandag 14. sep.</h3>Current plan",
                "ugeplan_next": "<h3>tirsdag 22. sep.</h3>Cancelled plan",
            },
            timestamp=now.timestamp(),
        )
        await archive.async_start()

        hass.states.async_set(
            entity_id,
            "ready",
            {"ugeplan": "<h3>mandag 14. sep.</h3>Updated plan"},
            timestamp=now.timestamp(),
        )
        await hass.async_block_till_done()
        assert [event["description"] for event in archive.events()] == [
            "Recorded plan",
            "Updated plan",
        ]
        now = datetime(2026, 9, 21, 9, tzinfo=timezone.utc)
        hass.states.async_set(
            entity_id,
            "ready",
            {"ugeplan": "<h3>mandag 21. sep.</h3>New week"},
            timestamp=now.timestamp(),
        )
        await hass.async_block_till_done()
        await archive.async_stop()

        hass.states.async_set(entity_id, STATE_UNAVAILABLE, timestamp=now.timestamp())
        reloaded = weekplan.AulaWeekplanHistory(hass, "entry", entity_id)
        await reloaded.async_start()
        assert [event["description"] for event in reloaded.events()] == [
            "Recorded plan", "Updated plan", "New week"
        ]
        run_query.assert_awaited_once()
        now = datetime(2026, 10, 13, 9, tzinfo=timezone.utc)
        assert [event["description"] for event in reloaded.events()] == ["New week"]
        await reloaded.async_stop()

    asyncio.run(check_history())
