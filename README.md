# iCalendar API integration for Home Assistant
Generates an iCalendar (.ics) link that you can use to view Home Assistant calendars and Aula week plans in another app.

## Installation
### HACS (recommended)
1. [Install HACS](https://hacs.xyz/docs/setup/download), if you did not already.
2. [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=chris-y&repository=ha-icalendar&category=integration)
3. Press the Download button.
4. Restart Home Assistant.

### Manually
Copy all files in the `custom_components/icalendar` folder to your Home Assistant folder `config/custom_components/icalendar`.

## Setup
1. Go to **Settings > Devices & Services > Integrations**.
2. Add **iCalendar API**.
3. Choose a `calendar.*` entity or an Aula sensor with `ugeplan` attributes.

Each config entry maps to exactly one source entity and one secret.

## URL format
The feed URL is now tied to the config entry ID:

- `/api/ics/<entry_id>/<secret>`

In the integration reconfigure/options UI, both local and external URL variants are shown (if configured in Home Assistant). Secret rotation is available from reconfigure.

## Additional configuration
Calendar color is taken from Home Assistant's calendar entity UI settings.
Set it in the calendar entity settings and it will be emitted as `COLOR` in the ICS feed.

## Configuration parameters
- Setup:
  - `calendar_entity_id`: Existing Home Assistant calendar or Aula week-plan sensor to expose.
- Reconfigure:
  - `calendar_entity_id`: Change the selected calendar.
  - `secret`: Optional new secret (minimum 20 chars). Leave blank to keep current secret.
- Options:
  - Read-only feed URL display only.

## Installation parameters
- Home Assistant `internal_url` and/or `external_url` should be configured to display full feed URLs in UI.
- The selected source entity must be loaded and available at setup/reconfigure time.

## Supported functionality
- Provides a secure iCalendar feed endpoint:
  - `GET /api/ics/<config_entry_id>/<secret>`
- Exports calendar events from the selected Home Assistant calendar entity.
- Converts populated days in Aula `ugeplan` and `ugeplan_next` sensor attributes to all-day events.
- Emits calendar-level `COLOR` from Home Assistant calendar UI color settings when available.

## Data update behavior
- Data is fetched on-demand per HTTP request from `calendar.get_events` or the selected Aula sensor.
- Time window returned is 4 weeks of history and 52 weeks in the future.

## Use cases
- Subscribe to Home Assistant calendars from external calendar clients that support ICS URLs.
- Share read-only calendar timelines using per-entry secrets.

## Example
- `https://home.example.com/api/ics/01ABCDEF1234567890/your_long_secret`

## Known limitations
- Feed security is URL-secret based; URLs should be treated as credentials.
- Calendar data is read at request time; response latency depends on calendar backend responsiveness.

## Troubleshooting
- `401 Unauthorized`: URL secret does not match the config entry secret.
- `403 Forbidden`: Invalid path/secret format or unsupported source entity.
- `404 Not Found`: Entry ID or source entity does not exist, or no calendar events were returned.
- If UI does not show full feed URLs, set `internal_url` / `external_url` in Home Assistant network settings.

## Removal instructions
1. Go to **Settings > Devices & Services > Integrations**.
2. Open **iCalendar API**.
3. Delete the config entry.
4. Update/remove ICS subscriptions that used that entry URL.

## Security notes
- Secret checks use constant-time comparison.
- iCalendar output now escapes reserved characters and folds long lines to improve parser safety and compatibility.
