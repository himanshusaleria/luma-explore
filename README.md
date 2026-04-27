# Luma Event Explorer

A tool to discover and aggregate upcoming events from [Luma](https://luma.com) across multiple cities. Luma's discover page only shows featured events — this tool surfaces **all** events visible on the map and city pages, making it easier to find what's happening near you.

> **Disclaimer:** This is an unofficial tool. All events are hosted on Luma. Click any event to view full details and RSVP on luma.com.

## How It Works

Luma's frontend uses an internal API (`api2.luma.com`) to load events. This tool calls the same endpoints the browser uses — no authentication or scraping required.

### Key API Endpoints Discovered

| Endpoint | Purpose |
|----------|---------|
| `GET /url?url={city-slug}` | Resolve a city slug (e.g. `singapore`) to a `discover_place_api_id` |
| `GET /discover/get-paginated-events?discover_place_api_id={id}&pagination_limit=50` | Paginated list of all upcoming events for a city |
| `GET /discover/get-map-pins?discover_place_api_id={id}&north=...&south=...&east=...&west=...` | Events within a map bounding box |
| `GET /discover/get-place-v2?discover_place_api_id={id}` | City metadata (name, description, hero images) |
| `GET /discover/get-calendars?discover_place_api_id={id}` | Featured calendars/organizers for a city |

### Supported Cities (26)

| Region | Cities |
|--------|--------|
| **Asia** | Singapore, Bengaluru, Mumbai, New Delhi, Tokyo, Seoul, Jakarta, Dubai, Tel Aviv |
| **Americas** | San Francisco, New York, Los Angeles, Austin, Seattle, Boston, Chicago, Miami, Toronto, Vancouver |
| **Europe** | London, Berlin, Paris, Amsterdam |
| **Oceania** | Sydney, Melbourne |

## Project Structure

```
luma-explore/
├── scrape_luma.py      # Python scraper — fetches events from Luma API
├── index.html           # Single-page web UI to browse events
├── data/                # Scraped event data (JSON + CSV)
│   ├── singapore_latest.json
│   ├── singapore_latest.csv
│   ├── bengaluru_latest.json
│   └── bengaluru_latest.csv
└── README.md
```

## Quick Start

### 1. Scrape events

```bash
# Scrape all configured cities
python3 scrape_luma.py

# Scrape specific cities
python3 scrape_luma.py singapore bengaluru

# Scrape any city by slug (auto-resolves place ID)
python3 scrape_luma.py tokyo london sf
```

### 2. View events in browser

```bash
python3 -m http.server 8080
# Open http://localhost:8080
```

## Output Format

Each event is saved with the following fields:

| Field | Description |
|-------|-------------|
| `event_id` | Luma event API ID |
| `name` | Event title |
| `url` | Direct link to the event on Luma |
| `start_at` / `end_at` | ISO 8601 timestamps |
| `timezone` | Event timezone |
| `location_type` | `offline` or `online` |
| `city`, `sublocality`, `country` | Location details |
| `latitude`, `longitude` | Geo coordinates |
| `guest_count` | Number of RSVPs |
| `hosts` | Comma-separated host names |
| `calendar_name` | Organizer/calendar name |
| `waitlist_active` | Whether event has a waitlist |

## Ideas & Future Improvements

- [ ] **Automated refresh** — Run the scraper on a cron schedule (every 2 hours) to keep data fresh
- [ ] **More cities** — Add support for any city on Luma by slug name
- [ ] **Event filtering** — Filter by category, date range, online/offline, guest count
- [ ] **Calendar export** — Export events as .ics files for Google Calendar / Apple Calendar
- [ ] **Notifications** — Get alerted when new events matching your interests are posted
- [ ] **Event analytics** — Track which events are trending (fastest growing RSVPs)
- [ ] **Host/organizer profiles** — Aggregate events by host to see who runs the best events in your city
- [ ] **Cross-city view** — See all events across cities in a single timeline
- [ ] **Map view** — Plot events on an interactive map using the coordinate data
- [ ] **API server** — Expose a simple REST API for other tools to consume event data
- [ ] **Slack/Discord bot** — Post daily event roundups to community channels
- [ ] **Duplicate detection** — Flag events that appear in multiple cities or are cross-posted
- [ ] **Historical data** — Track event trends over time (which cities are growing, peak event days, etc.)

## Technical Notes

- The API requires standard browser headers (`Origin: https://luma.com`, `x-luma-client-type: luma-web`) but **no authentication**
- Pagination uses cursor-based pagination (`next_cursor` field)
- Rate limiting appears to be generous — 200+ requests/minute per IP
- The `discover_place_api_id` for each city is stable and doesn't change
- The scraper uses only Python stdlib (`urllib`, `json`, `csv`) — no dependencies required
