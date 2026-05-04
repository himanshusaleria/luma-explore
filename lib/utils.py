"""Shared utilities for Luma event fetching."""

import csv
import json
import os
from datetime import datetime, timezone

OUTPUT_DIR = "data"

CITIES = {
    "bengaluru": {
        "place_id": "discplace-G0tGUVYwl7T17Sb",
        "bounds": {"north": 13.2, "south": 12.7, "east": 77.9, "west": 77.3},
    },
    "singapore": {
        "place_id": "discplace-mUbtdfNjfWaLQ72",
        "bounds": {"north": 1.5, "south": 1.1, "east": 104.1, "west": 103.6},
    },
    "sf": {
        "place_id": "discplace-BDj7GNbGlsF7Cka",
        "bounds": {"north": 38.0, "south": 37.3, "east": -121.8, "west": -122.6},
    },
    "mumbai": {
        "place_id": "discplace-Q5hkYsjZs1ZDJcU",
        "bounds": {"north": 19.3, "south": 18.85, "east": 72.95, "west": 72.75},
    },
    "new-delhi": {
        "place_id": "discplace-CzipmKodUYN2Dfx",
        "bounds": {"north": 28.9, "south": 28.4, "east": 77.4, "west": 76.8},
    },
    "boston": {
        "place_id": "discplace-VWeZ1zUvnawYHMj",
        "bounds": {"north": 42.5, "south": 42.2, "east": -70.9, "west": -71.3},
    },
    "pune": {
        "place_id": None,  # No discover page — coordinate-only city
        "bounds": {"north": 18.65, "south": 18.40, "east": 74.0, "west": 73.7},
        "scan_from": ["bengaluru", "mumbai", "new-delhi"],  # Scan these cities' calendars too
    },
}


def flatten_event(entry: dict) -> dict:
    """Flatten an event entry into a clean row."""
    event = entry.get("event", {})
    calendar = entry.get("calendar", {})
    geo = event.get("geo_address_info", {})
    coord = event.get("coordinate", {})
    hosts = entry.get("hosts", [])

    host_names = []
    for h in hosts:
        if isinstance(h, dict):
            name = h.get("name") or ""
            if not name:
                first = h.get("first_name", "")
                last = h.get("last_name", "")
                name = f"{first} {last}".strip()
            if name:
                host_names.append(name)

    source = entry.get("source", "featured")

    # Extract category tags
    categories = entry.get("categories", [])
    cat_names = [c.get("name", "") for c in categories if isinstance(c, dict) and c.get("name")]

    return {
        "event_id": event.get("api_id", entry.get("api_id", "")),
        "name": event.get("name", ""),
        "url": f"https://lu.ma/{event['url']}" if event.get("url") else "",
        "start_at": event.get("start_at", ""),
        "end_at": event.get("end_at", ""),
        "timezone": event.get("timezone", ""),
        "location_type": event.get("location_type", ""),
        "city": geo.get("city", ""),
        "sublocality": geo.get("sublocality", ""),
        "country": geo.get("country", ""),
        "latitude": coord.get("latitude"),
        "longitude": coord.get("longitude"),
        "cover_url": event.get("cover_url", ""),
        "guest_count": entry.get("guest_count"),
        "hosts": ", ".join(host_names),
        "calendar_name": calendar.get("name", ""),
        "calendar_slug": calendar.get("slug", ""),
        "event_type": event.get("event_type", ""),
        "visibility": event.get("visibility", ""),
        "waitlist_active": entry.get("waitlist_active", False),
        "source": source,
        "tags": ", ".join(cat_names),
    }


def save_events(city: str, events: list[dict]) -> list[dict]:
    """Save events to JSON and CSV."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # JSON (full raw data)
    raw_path = f"{OUTPUT_DIR}/{city}_raw_{timestamp}.json"
    with open(raw_path, "w") as f:
        json.dump(events, f, indent=2, default=str)
    print(f"  Raw data: {raw_path}")

    # Flatten
    flat = [flatten_event(e) for e in events]

    # Sort by start_at
    flat.sort(key=lambda e: e.get("start_at", ""))

    # CSV (flattened)
    csv_path = f"{OUTPUT_DIR}/{city}_events_{timestamp}.csv"
    if flat:
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=flat[0].keys())
            writer.writeheader()
            writer.writerows(flat)
    print(f"  CSV: {csv_path} ({len(flat)} events)")

    # Latest copies
    latest_json = f"{OUTPUT_DIR}/{city}_latest.json"
    latest_csv = f"{OUTPUT_DIR}/{city}_latest.csv"
    with open(latest_json, "w") as f:
        json.dump(flat, f, indent=2, default=str)
    if flat:
        with open(latest_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=flat[0].keys())
            writer.writeheader()
            writer.writerows(flat)

    return flat


def save_calendars(city: str, events: list[dict]) -> dict:
    """Extract and persist all unique calendar IDs from events."""
    cal_path = f"{OUTPUT_DIR}/{city}_calendars.json"

    # Load existing calendars
    existing = {}
    if os.path.exists(cal_path):
        with open(cal_path) as f:
            existing = json.load(f)

    # Extract new calendars
    for entry in events:
        cal = entry.get("calendar", {})
        cal_id = cal.get("api_id")
        if cal_id and cal_id not in existing:
            existing[cal_id] = {
                "name": cal.get("name", ""),
                "slug": cal.get("slug", ""),
                "added": datetime.now(timezone.utc).isoformat(),
            }

    with open(cal_path, "w") as f:
        json.dump(existing, f, indent=2)

    return existing
