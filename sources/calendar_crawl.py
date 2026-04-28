"""Calendar snowball crawl (calendar/get-items + event/get endpoints).

Crawl organizer calendars to discover non-featured events.
For each unique calendar/organizer found in previously fetched events,
fetch ALL their future events. Then fetch full details for any event
not already in the known set.

Uses ThreadPoolExecutor for parallel fetching.
"""

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from lib.api import api_get, PAGE_SIZE
from lib.utils import OUTPUT_DIR

# Parallel workers for API calls
MAX_WORKERS = 10


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

    return all_entries


def _fetch_event_detail(event_api_id: str) -> tuple[str, dict | None]:
    """Fetch full details for a single event. Returns (id, detail)."""
    try:
        data = api_get("/event/get", {"event_api_id": event_api_id})
        return (event_api_id, data)
    except Exception:
        return (event_api_id, None)


def fetch(place_id: str, bounds: dict | None = None, city: str = "",
          known_entries: list[dict] | None = None) -> list[dict]:
    """Crawl organizer calendars to discover non-featured events.

    Uses parallel fetching for both calendar crawls and event details.
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

    print(f"  Snowball: crawling {len(calendar_ids)} calendars (parallel)...")

    # ── Phase 1: Crawl all calendars in parallel ──
    new_event_ids = set()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_fetch_calendar_events, cid): cid for cid in calendar_ids}
        for future in as_completed(futures):
            try:
                cal_events = future.result()
                for entry in cal_events:
                    ev = entry.get("event", {})
                    eid = ev.get("api_id", "")
                    if eid and eid not in known_ids and eid not in new_event_ids:
                        new_event_ids.add(eid)
            except Exception:
                pass

    print(f"  Snowball: found {len(new_event_ids)} candidates, fetching details...")

    # ── Phase 2: Fetch event details in parallel ──
    new_entries = []
    checked = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_fetch_event_detail, eid): eid for eid in new_event_ids}
        for future in as_completed(futures):
            checked += 1
            try:
                eid, detail = future.result()
            except Exception:
                continue

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
                geo = event.get("geo_address_info") or {}
                if event.get("location_type") == "online":
                    in_bounds = False

            if in_bounds:
                entry = {
                    "api_id": eid,
                    "event": event,
                    "calendar": detail.get("calendar", {}),
                    "categories": detail.get("categories", []),
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

            if checked % 50 == 0:
                print(f"  Snowball: {checked}/{len(new_event_ids)} checked, {len(new_entries)} in-city")

    print(f"  Snowball: {len(new_entries)} new in-city events discovered")
    return new_entries
