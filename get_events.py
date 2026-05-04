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

Cities run in parallel for speed.

Usage:
    python get_events.py                  # Get events for all configured cities
    python get_events.py singapore        # Get events for a specific city
    python get_events.py bengaluru sf     # Get events for multiple cities
"""

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from lib.api import api_get
from lib.utils import CITIES, OUTPUT_DIR, save_events, save_calendars


def resolve_city(slug: str) -> str | None:
    """Resolve a city slug to a discover_place_api_id."""
    data = api_get("/url", {"url": slug})
    if data.get("kind") == "discover-place":
        return data["data"]["place"]["api_id"]
    return None


def get_events_for_city(city: str) -> dict:
    """Get all events for a city using multiple sources. Returns a summary dict."""
    from sources import featured, map_pins, calendar_crawl

    t_start = time.time()
    city_config = CITIES.get(city)

    if not city_config:
        print(f"[{city}] Resolving slug...")
        place_id = resolve_city(city)
        if not place_id:
            print(f"[{city}] Could not resolve — skipping")
            return {"city": city, "total": 0, "error": "not found"}
        city_config = {"place_id": place_id, "bounds": None}

    place_id = city_config.get("place_id")
    bounds = city_config.get("bounds")
    scan_from = city_config.get("scan_from", [])

    # For coordinate-only cities (no place_id), load calendars from related cities
    if not place_id and scan_from:
        print(f"[{city}] Coordinate-only city — loading calendars from {', '.join(scan_from)}")
        import json, os
        cal_path = f"{OUTPUT_DIR}/{city}_calendars.json"
        cals = {}
        if os.path.exists(cal_path):
            with open(cal_path) as f:
                cals = json.load(f)
        for related in scan_from:
            related_path = f"{OUTPUT_DIR}/{related}_calendars.json"
            if os.path.exists(related_path):
                with open(related_path) as f:
                    related_cals = json.load(f)
                for k, v in related_cals.items():
                    if k not in cals:
                        cals[k] = v
        with open(cal_path, "w") as f:
            json.dump(cals, f, indent=2)
        print(f"[{city}] Calendar pool: {len(cals)} calendars from {len(scan_from)} related cities")

    # Source 1: Featured events (skip for coordinate-only cities)
    featured_entries = []
    if place_id:
        print(f"[{city}] Fetching featured events...")
        try:
            featured_entries = featured.fetch(place_id, bounds, city)
            print(f"[{city}] Featured: {len(featured_entries)}")
        except Exception as e:
            print(f"[{city}] Featured failed: {e}")

    # Source 2: Map pins (skip for coordinate-only cities)
    map_entries = []
    if place_id and bounds:
        try:
            map_entries = map_pins.fetch(place_id, bounds, city)
            print(f"[{city}] Map pins: {len(map_entries)}")
        except Exception as e:
            print(f"[{city}] Map pins failed: {e}")

    # Source 3: Calendar snowball
    snowball_entries = []
    if bounds:
        try:
            all_so_far = featured_entries + map_entries
            snowball_entries = calendar_crawl.fetch(
                place_id, bounds, city, known_entries=all_so_far
            )
        except Exception as e:
            print(f"[{city}] Calendar snowball failed: {e}")

    # Merge and deduplicate
    all_events = featured_entries + map_entries + snowball_entries
    seen = set()
    deduped = []
    for e in all_events:
        eid = e.get("api_id") or e.get("event", {}).get("api_id", "")
        if eid and eid not in seen:
            seen.add(eid)
            deduped.append(e)

    elapsed = time.time() - t_start

    # Save
    try:
        calendars = save_calendars(city, deduped)
        flat = save_events(city, deduped)
    except Exception as e:
        print(f"[{city}] Save failed: {e}")
        flat = []
        calendars = {}

    summary = {
        "city": city,
        "featured": len(featured_entries),
        "map": len(map_entries),
        "snowball": len(snowball_entries),
        "total": len(deduped),
        "calendars": len(calendars),
        "time": f"{elapsed:.1f}s",
    }
    print(f"[{city}] Done: {len(deduped)} events "
          f"({len(featured_entries)}F + {len(map_entries)}M + {len(snowball_entries)}S) "
          f"in {elapsed:.1f}s")
    return summary


def main():
    cities = sys.argv[1:] if len(sys.argv) > 1 else list(CITIES.keys())

    print(f"Luma Event Fetcher — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Cities: {', '.join(cities)}")
    print(f"Strategy: Featured + Map Pins + Calendar Snowball (parallel)\n")

    t_start = time.time()

    if len(cities) == 1:
        # Single city — run directly
        get_events_for_city(cities[0].lower())
    else:
        # Multiple cities — run in parallel
        summaries = []
        with ThreadPoolExecutor(max_workers=len(cities)) as pool:
            futures = {pool.submit(get_events_for_city, c.lower()): c for c in cities}
            for future in as_completed(futures):
                try:
                    summaries.append(future.result())
                except Exception as e:
                    city = futures[future]
                    print(f"[{city}] Failed entirely: {e}")
                    summaries.append({"city": city, "total": 0, "error": str(e)})

        # Print summary table
        print(f"\n{'='*65}")
        print(f"  {'City':<15} {'Featured':>8} {'Map':>5} {'Hidden':>7} {'Total':>6} {'Time':>7}")
        print(f"  {'-'*55}")
        for s in sorted(summaries, key=lambda x: -x.get("total", 0)):
            print(f"  {s['city']:<15} {s.get('featured',0):>8} {s.get('map',0):>5} "
                  f"{s.get('snowball',0):>7} {s.get('total',0):>6} {s.get('time','?'):>7}")
        print(f"{'='*65}")

    total_time = time.time() - t_start
    print(f"\nDone in {total_time:.1f}s! Data saved to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
