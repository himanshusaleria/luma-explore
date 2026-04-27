"""Calendar snowball crawl (calendar/get-items + event/get endpoints).

Crawl organizer calendars to discover non-featured events.
For each unique calendar/organizer found in previously fetched events,
fetch ALL their future events. Then fetch full details for any event
not already in the known set.
"""

import json
import os
import time

from lib.api import api_get, PAGE_SIZE, REQUEST_DELAY
from lib.utils import OUTPUT_DIR


def _fetch_calendar_events(calendar_id: str) -> list[dict]:
    """Fetch all future events from a specific organizer calendar."""
    all_entries = []
    cursor = None

    while True:
        params = {
            "calendar_api_id": calendar_id,
            "pagination_limit": PAGE_SIZE,
            "period": "future",
        }
        if cursor:
            params["pagination_cursor"] = cursor

        try:
            data = api_get("/calendar/get-items", params)
        except Exception:
            break

        entries = data.get("entries", [])
        all_entries.extend(entries)

        if not data.get("has_more") or not entries:
            break

        cursor = data.get("next_cursor")
        time.sleep(REQUEST_DELAY)

    return all_entries


def _fetch_event_detail(event_api_id: str) -> dict | None:
    """Fetch full details for a single event."""
    try:
        data = api_get("/event/get", {"event_api_id": event_api_id})
        return data
    except Exception:
        return None


def fetch(place_id: str, bounds: dict | None = None, city: str = "",
          known_entries: list[dict] | None = None) -> list[dict]:
    """Crawl organizer calendars to discover non-featured events.

    Args:
        place_id: The discover place API ID (unused here but kept for consistent interface).
        bounds: Geo bounding box for the city. Required for filtering.
        city: City slug, used to load saved calendar registry.
        known_entries: Already-fetched entries from other sources, used to
                       extract calendar IDs and avoid duplicate event fetches.

    Returns a list of newly discovered event entries.
    """
    if not bounds:
        return []

    known_entries = known_entries or []

    # Extract unique calendar IDs and known event IDs
    known_ids = set()
    calendar_ids = set()

    for entry in known_entries:
        known_ids.add(entry.get("api_id") or entry.get("event", {}).get("api_id", ""))
        cal_id = entry.get("calendar", {}).get("api_id")
        if cal_id:
            calendar_ids.add(cal_id)

    # Also load previously saved calendar registry
    if city:
        cal_path = f"{OUTPUT_DIR}/{city}_calendars.json"
        if os.path.exists(cal_path):
            with open(cal_path) as f:
                saved = json.load(f)
            for cal_id in saved:
                calendar_ids.add(cal_id)

    print(f"  Snowball: crawling {len(calendar_ids)} organizer calendars...")

    # Crawl each calendar
    new_event_ids = set()
    for cal_id in calendar_ids:
        cal_events = _fetch_calendar_events(cal_id)
        for entry in cal_events:
            ev = entry.get("event", {})
            eid = ev.get("api_id", "")
            if eid and eid not in known_ids and eid not in new_event_ids:
                new_event_ids.add(eid)
        time.sleep(REQUEST_DELAY)

    print(f"  Snowball: found {len(new_event_ids)} candidate non-featured events")

    # Fetch full details for new events and filter by city bounds
    new_entries = []
    for i, eid in enumerate(new_event_ids):
        detail = _fetch_event_detail(eid)
        if not detail:
            continue

        # Check if event is in the city's geo bounds
        event = detail.get("event", {})
        coord = event.get("coordinate") or {}
        lat = coord.get("latitude")
        lng = coord.get("longitude")

        in_bounds = False
        if lat is not None and lng is not None:
            in_bounds = (bounds["south"] <= lat <= bounds["north"] and
                         bounds["west"] <= lng <= bounds["east"])
        else:
            # No coordinates — check city name in geo_address_info
            geo = event.get("geo_address_info") or {}
            city_name = (geo.get("city") or "").lower()
            # Skip online-only events with no location
            if event.get("location_type") == "online":
                in_bounds = False

        if in_bounds:
            # Convert to the same format as featured entries
            entry = {
                "api_id": eid,
                "event": event,
                "calendar": detail.get("calendar", {}),
                "hosts": detail.get("hosts", []),
                "guest_count": detail.get("guest_count"),
                "start_at": event.get("start_at"),
                "cover_image": None,
                "ticket_info": detail.get("ticket_info"),
                "featured_guests": [],
                "waitlist_active": False,
                "source": "snowball",
            }
            new_entries.append(entry)

        if (i + 1) % 20 == 0:
            print(f"  Snowball: checked {i+1}/{len(new_event_ids)} events, {len(new_entries)} in-city")
        time.sleep(REQUEST_DELAY)

    print(f"  Snowball: {len(new_entries)} new in-city events discovered")
    return new_entries
