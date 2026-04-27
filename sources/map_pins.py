"""Fetch events from map pins (get-map-pins endpoint)."""

import time

from lib.api import api_get, REQUEST_DELAY


def _fetch_event_detail(event_api_id: str) -> dict | None:
    """Fetch full details for a single event."""
    try:
        data = api_get("/event/get", {"event_api_id": event_api_id})
        return data
    except Exception:
        return None


def fetch(place_id: str, bounds: dict | None = None, city: str = "") -> list[dict]:
    """Fetch events visible on the map within a bounding box.

    Returns a list of event entries. Requires bounds to be set.
    """
    if not bounds:
        return []

    params = {
        "discover_place_api_id": place_id,
        "north": bounds["north"],
        "south": bounds["south"],
        "east": bounds["east"],
        "west": bounds["west"],
    }
    data = api_get("/discover/get-map-pins", params)
    pins = data.get("entries", [])

    # Fetch full details for each pin to get complete event data
    entries = []
    for pin in pins:
        detail = _fetch_event_detail(pin["api_id"])
        if detail:
            entry = {
                "api_id": pin["api_id"],
                "event": detail.get("event", {}),
                "calendar": detail.get("calendar", {}),
                "hosts": detail.get("hosts", []),
                "guest_count": detail.get("guest_count"),
                "start_at": detail.get("event", {}).get("start_at"),
                "waitlist_active": False,
                "source": "map",
            }
            entries.append(entry)
        time.sleep(REQUEST_DELAY)

    return entries
