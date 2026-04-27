#!/usr/bin/env python3
"""
Luma Event Scraper — fetches all upcoming events for configured cities
using Luma's internal discover API (no auth required).

Usage:
    python scrape_luma.py                  # Scrape all configured cities
    python scrape_luma.py singapore        # Scrape specific city
    python scrape_luma.py singapore bangalore  # Scrape multiple cities
"""

import json
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

# ── Config ──────────────────────────────────────────────────────────────────

CITIES = {
    # Asia
    "singapore": "discplace-mUbtdfNjfWaLQ72",
    "bengaluru": "discplace-G0tGUVYwl7T17Sb",
    "mumbai": "discplace-Q5hkYsjZs1ZDJcU",
    "new-delhi": "discplace-CzipmKodUYN2Dfx",
    "tokyo": "discplace-9H7asQEvWiv6DA9",
    "seoul": "discplace-eQieweHXBFCWbCj",
    "jakarta": "discplace-D0vMN5ttALav9XP",
    "dubai": "discplace-d3kg1aLIJ5ROF6S",
    "tel-aviv": "discplace-fHkSoyCyugTZSbr",
    # Americas
    "sf": "discplace-BDj7GNbGlsF7Cka",
    "nyc": "discplace-Izx1rQVSh8njYpP",
    "la": "discplace-OgfEAh5KgfMzise",
    "austin": "discplace-0tPy8KGz3xMycnt",
    "seattle": "discplace-FQ4E58PeBMHGTKK",
    "boston": "discplace-VWeZ1zUvnawYHMj",
    "chicago": "discplace-NdGm35qFD0vaXNF",
    "miami": "discplace-fSrrRYurTwydAGK",
    "toronto": "discplace-Cx3JMS6vXKAbhV5",
    "vancouver": "discplace-4fa7ldlAkBTTivm",
    # Europe
    "london": "discplace-QCcNk3HXowOR97j",
    "berlin": "discplace-gCfX0s3E9Hgo3rG",
    "paris": "discplace-NdLrh1xJfeotJZC",
    "amsterdam": "discplace-FC4SDMUVXiFtMOr",
    # Oceania
    "sydney": "discplace-TPdKGPI56hGfOdi",
    "melbourne": "discplace-DlA8FnyHTxhIkN2",
}

BASE_URL = "https://api2.luma.com"
PAGE_SIZE = 50
OUTPUT_DIR = "data"

HEADERS = {
    "Accept": "*/*",
    "Origin": "https://luma.com",
    "Referer": "https://luma.com/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "x-luma-client-type": "luma-web",
    "x-luma-timezone": "UTC",
}


# ── Helpers ─────────────────────────────────────────────────────────────────

def api_get(path: str, params: dict | None = None) -> dict:
    """Make a GET request to the Luma API."""
    url = f"{BASE_URL}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def resolve_city(slug: str) -> str | None:
    """Resolve a city slug (e.g. 'singapore') to a discover_place_api_id."""
    data = api_get("/url", {"url": slug})
    if data.get("kind") == "discover-place":
        return data["data"]["place"]["api_id"]
    return None


def fetch_all_events(place_id: str) -> list[dict]:
    """Fetch all paginated events for a discover place."""
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

        print(f"  Fetched {len(entries)} events (total: {len(all_entries)})")

        if not data.get("has_more") or not entries:
            break

        cursor = data.get("next_cursor")
        time.sleep(0.3)  # be polite

    return all_entries


def fetch_map_pins(place_id: str, bounds: dict) -> list[dict]:
    """Fetch map pin events within a bounding box."""
    params = {
        "discover_place_api_id": place_id,
        "north": bounds["north"],
        "south": bounds["south"],
        "east": bounds["east"],
        "west": bounds["west"],
    }
    data = api_get("/discover/get-map-pins", params)
    return data.get("entries", [])


def flatten_event(entry: dict) -> dict:
    """Flatten a paginated event entry into a clean row."""
    event = entry.get("event", {})
    calendar = entry.get("calendar", {})
    geo = event.get("geo_address_info", {})
    coord = event.get("coordinate", {})
    hosts = entry.get("hosts", [])

    host_names = []
    for h in hosts:
        name = h.get("name") or ""
        if not name:
            first = h.get("first_name", "")
            last = h.get("last_name", "")
            name = f"{first} {last}".strip()
        if name:
            host_names.append(name)

    return {
        "event_id": event.get("api_id", ""),
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
    }


def save_events(city: str, events: list[dict]):
    """Save events to JSON and CSV."""
    import csv
    import os

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # JSON (full raw data)
    raw_path = f"{OUTPUT_DIR}/{city}_raw_{timestamp}.json"
    with open(raw_path, "w") as f:
        json.dump(events, f, indent=2)
    print(f"  Raw data: {raw_path}")

    # CSV (flattened)
    flat = [flatten_event(e) for e in events]
    csv_path = f"{OUTPUT_DIR}/{city}_events_{timestamp}.csv"
    if flat:
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=flat[0].keys())
            writer.writeheader()
            writer.writerows(flat)
    print(f"  CSV: {csv_path} ({len(flat)} events)")

    # Also save a "latest" symlink-style copy
    latest_json = f"{OUTPUT_DIR}/{city}_latest.json"
    latest_csv = f"{OUTPUT_DIR}/{city}_latest.csv"
    with open(latest_json, "w") as f:
        json.dump(flat, f, indent=2)
    if flat:
        with open(latest_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=flat[0].keys())
            writer.writeheader()
            writer.writerows(flat)

    return flat


def print_summary(city: str, flat_events: list[dict]):
    """Print a human-readable summary."""
    print(f"\n{'='*60}")
    print(f"  {city.upper()} — {len(flat_events)} upcoming events")
    print(f"{'='*60}")

    for e in flat_events:
        start = e["start_at"]
        if start:
            dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            start_str = dt.strftime("%b %d, %I:%M %p")
        else:
            start_str = "TBD"

        loc = e["location_type"]
        loc_detail = e["sublocality"] or e["city"] or ""
        if loc == "online":
            loc_detail = "Online"
        elif loc_detail:
            loc_detail = f"📍 {loc_detail}"

        guests = f"({e['guest_count']} guests)" if e.get("guest_count") else ""
        host = f"by {e['hosts']}" if e["hosts"] else ""

        print(f"\n  {start_str} | {e['name']}")
        if host:
            print(f"    {host}")
        print(f"    {loc_detail} {guests}")
        print(f"    {e['url']}")


# ── Main ────────────────────────────────────────────────────────────────────

def scrape_city(city: str):
    """Scrape all events for a city."""
    place_id = CITIES.get(city)

    if not place_id:
        print(f"Resolving city slug '{city}'...")
        place_id = resolve_city(city)
        if not place_id:
            print(f"  Could not resolve '{city}' — skipping")
            return
        print(f"  Found place ID: {place_id}")

    print(f"\nFetching events for {city} (place_id={place_id})...")
    events = fetch_all_events(place_id)
    print(f"  Total: {len(events)} events")

    flat = save_events(city, events)
    print_summary(city, flat)


def main():
    cities = sys.argv[1:] if len(sys.argv) > 1 else list(CITIES.keys())

    print(f"Luma Event Scraper — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Cities: {', '.join(cities)}")

    for city in cities:
        scrape_city(city.lower())

    print(f"\nDone! Data saved to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
