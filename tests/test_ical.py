"""Regression tests for ICS event identity and time zones."""

import sys
from datetime import date, datetime, timezone
from types import SimpleNamespace

from ical.calendar import Calendar
from ical.calendar_stream import IcsCalendarStream

from custom_components.icalendar.config_flow import _build_feed_urls
from custom_components.icalendar.ical import (
    aula_weekplan_events,
    event_from_ha,
    inject_calendar_metadata,
)


def test_offset_events_use_stable_uids_and_utc() -> None:
    """Keep subscription updates tied to one event across requests."""
    payload = {
        "summary": "Matematik",
        "description": "Room 2",
        "location": "School",
        "start": "2026-09-01T08:00:00+02:00",
        "end": "2026-09-01T08:45:00+02:00",
    }

    event = event_from_ha("calendar.school", payload)
    updated_event = event_from_ha(
        "calendar.school", {**payload, "description": "Room 3", "location": "Gym"}
    )

    assert event is not None
    assert updated_event is not None
    assert event.uid == event_from_ha("calendar.school", payload).uid
    assert event.uid == updated_event.uid
    assert event.dtstart == datetime(2026, 9, 1, 6, 0, tzinfo=timezone.utc)
    assert "DTSTART:20260901T060000Z" in IcsCalendarStream.calendar_to_ics(
        Calendar(events=[event])
    )


def test_all_day_events_keep_dates_and_stable_uids() -> None:
    """Preserve all-day semantics while assigning a deterministic UID."""
    payload = {"summary": "Birthday", "start": "2026-09-01", "end": "2026-09-02"}

    event = event_from_ha("calendar.birthdays", payload)

    assert event is not None
    assert event.dtstart == date(2026, 9, 1)
    assert event.dtend == date(2026, 9, 2)
    assert event.uid == event_from_ha("calendar.birthdays", payload).uid
    ics = inject_calendar_metadata(
        IcsCalendarStream.calendar_to_ics(Calendar(events=[event])), "Birthdays", None
    )
    assert "DTSTART;VALUE=DATE:20260901" in ics
    assert "DTEND;VALUE=DATE:20260902" in ics


def test_aula_weekplans_become_nonempty_all_day_events() -> None:
    """Expose each populated Aula day while skipping placeholder days."""
    events = aula_weekplan_events(
        {
            "ugeplan": (
                "<h3>mandag 31. aug.</h3>-"
                "<h3>tirsdag 1. sep.</h3><b>Matematik &amp; dansk</b><br>"
                r"Læs 1\. kapitel<br><br><b>UUV</b><br>Trivsel<br><br>"
            ),
            "ugeplan_next": (
                "<h3>mandag 7. sep.</h3>-"
                "<h3>onsdag 9. sep.</h3>Idrætsdag"
            ),
        },
        today=date(2026, 9, 1),
    )

    assert events == [
        {
            "summary": "Ugeplan",
            "description": "Matematik & dansk\nLæs 1. kapitel\n\nUUV\nTrivsel",
            "start": "2026-09-01",
            "end": "2026-09-02",
        },
        {
            "summary": "Ugeplan",
            "description": "Idrætsdag",
            "start": "2026-09-09",
            "end": "2026-09-10",
        },
    ]


def test_feed_url_falls_back_to_home_assistant_cloud(monkeypatch) -> None:
    """Offer a subscribable URL when HA's external URL setting is empty."""
    hass = SimpleNamespace(config=SimpleNamespace(internal_url=None, external_url=None))
    monkeypatch.setitem(
        sys.modules,
        "homeassistant.components.cloud",
        SimpleNamespace(
            CloudNotAvailable=RuntimeError,
            async_remote_ui_url=lambda hass: "https://example.ui.nabu.casa",
        ),
    )

    assert _build_feed_urls(hass, "entry", "secret") == (
        "",
        "https://example.ui.nabu.casa/api/ics/entry/secret",
    )
