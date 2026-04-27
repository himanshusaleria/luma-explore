"""Fetch featured events from the Luma discover page (get-paginated-events endpoint)."""

import time

from lib.api import api_get, PAGE_SIZE, REQUEST_DELAY


def fetch(place_id: str, bounds: dict | None = None, city: str = "") -> list[dict]:
    """Fetch featured/curated events from the discover page.

    Returns a list of event entries.
    """
    all_entries = []
    cursor = None

    while True:
        params = {
            "discover_place_api_id": place_id,
            "pagination_limit": PAGE_SIZE,
        }
        if cursor:
            params["pagination_cursor"] = cursor

        data = api_get("/discover/get-paginated-events", params)
        entries = data.get("entries", [])
        all_entries.extend(entries)

        if not data.get("has_more") or not entries:
            break

        cursor = data.get("next_cursor")
        time.sleep(REQUEST_DELAY)

    # Tag source
    for entry in all_entries:
        entry.setdefault("source", "featured")

    return all_entries
