"""Shared API helper for Luma event fetching."""

import json
import urllib.request
import urllib.parse

BASE_URL = "https://api2.luma.com"
REQUEST_DELAY = 0.4  # seconds between API calls
PAGE_SIZE = 50

HEADERS = {
    "Accept": "*/*",
    "Origin": "https://luma.com",
    "Referer": "https://luma.com/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "x-luma-client-type": "luma-web",
    "x-luma-timezone": "UTC",
}


def api_get(path: str, params: dict | None = None) -> dict:
    """Make a GET request to the Luma API."""
    url = f"{BASE_URL}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())
