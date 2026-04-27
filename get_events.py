#!/usr/bin/env python3
"""
Luma Event Fetcher — fetches ALL upcoming events for configured cities,
including non-featured events discovered via calendar snowball crawling.

Strategy:
  1. Featured events — from the discover page (get-paginated-events)
  2. Map pins — events visible on the map (get-map-pins)
  3. Calendar snowball — crawl each organizer's calendar for all their events,
     then fetch full details for non-featured ones
  4. Deduplicate and filter by city geo-bounds

Usage:
    python get_events.py                  # Get events for all configured cities
    python get_events.py singapore        # Get events for a specific city
    python get_events.py bengaluru sf     # Get events for multiple cities
"""

import sys
from datetime import datetime, timezone

from lib.api import api_get
from lib.utils import CITIES, OUTPUT_DIR, save_events, save_calendars, flatten_event
from sources import featured, map_pins, calendar_crawl


def resolve_city(slug: str) -> str | None:
    """Resolve a city slug to a discover_place_api_id."""
    data = api_get("/url", {"url": slug})
    if data.get("kind") == "discover-place":
        return data["data"]["place"]["api_id"]
    return None


def print_summary(city: str, flat_events: list[dict]):
    """Print a human-readable summary."""
    featured_events = [e for e in flat_events if e["source"] == "featured"]
    discovered = [e for e in flat_events if e["source"] != "featured"]

    print(f"\n{'='*60}")
    print(f"  {city.upper()} — {len(flat_events)} total events")
    print(f"  ({len(featured_events)} featured + {len(discovered)} discovered)")
    print(f"{'='*60}")

    for e in flat_events:
        start = e["start_at"]
        if start:
            dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            start_str = dt.strftime("%b %d, %I:%M %p")
        else:
            start_str = "TBD"

        loc_detail = e["sublocality"] or e["city"] or ""
        if e["location_type"] == "online":
            loc_detail = "Online"

        tag = "" if e["source"] == "featured" else " [NEW]"
        guests = f"({e['guest_count']} guests)" if e.get("guest_count") else ""

        print(f"\n  {start_str} | {e['name']}{tag}")
        if e["hosts"]:
            print(f"    by {e['hosts']}")
        if loc_detail:
            print(f"    {loc_detail} {guests}")
        print(f"    {e['url']}")


def get_events_for_city(city: str):
    """Get all events for a city using multiple sources."""
    city_config = CITIES.get(city)

    if not city_config:
        # Try to resolve dynamically
        print(f"Resolving city slug '{city}'...")
        place_id = resolve_city(city)
        if not place_id:
            print(f"  Could not resolve '{city}' — skipping")
            return
        city_config = {"place_id": place_id, "bounds": None}
        print(f"  Found place ID: {place_id}")

    place_id = city_config["place_id"]
    bounds = city_config.get("bounds")

    # Source 1: Featured events
    featured_entries = []
    print(f"\n[{city}] Step 1: Fetching featured events...")
    try:
        featured_entries = featured.fetch(place_id, bounds, city)
        print(f"  Featured: {len(featured_entries)} events")
    except Exception as e:
        print(f"  Featured events failed: {e}")

    # Source 2: Map pins (to catch non-featured visible on map)
    map_entries = []
    if bounds:
        print(f"[{city}] Step 2: Fetching map pins...")
        try:
            map_entries = map_pins.fetch(place_id, bounds, city)
            print(f"  Map pins: {len(map_entries)} events")
        except Exception as e:
            print(f"  Map pins failed: {e}")

    # Source 3: Calendar snowball
    snowball_entries = []
    if bounds:
        print(f"[{city}] Step 3: Calendar snowball crawl...")
        try:
            all_so_far = featured_entries + map_entries
            snowball_entries = calendar_crawl.fetch(
                place_id, bounds, city, known_entries=all_so_far
            )
        except Exception as e:
            print(f"  Calendar snowball failed: {e}")

    # Merge and deduplicate
    all_events = featured_entries + map_entries + snowball_entries
    seen = set()
    deduped = []
    for e in all_events:
        eid = e.get("api_id") or e.get("event", {}).get("api_id", "")
        if eid and eid not in seen:
            seen.add(eid)
            deduped.append(e)

    print(f"\n[{city}] Total: {len(deduped)} unique events "
          f"({len(featured_entries)} featured + {len(map_entries)} map + {len(snowball_entries)} snowball)")

    # Save calendar registry for future runs
    calendars = save_calendars(city, deduped)
    print(f"  Calendar registry: {len(calendars)} organizers tracked")

    flat = save_events(city, deduped)
    print_summary(city, flat)


def main():
    cities = sys.argv[1:] if len(sys.argv) > 1 else list(CITIES.keys())

    print(f"Luma Event Fetcher — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Cities: {', '.join(cities)}")
    print(f"Strategy: Featured + Map Pins + Calendar Snowball")

    for city in cities:
        get_events_for_city(city.lower())

    print(f"\nDone! Data saved to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
