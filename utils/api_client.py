"""Thin wrapper around the Cricbuzz RapidAPI with retries and a local JSON cache."""
import json
import os
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://cricbuzz-cricket.p.rapidapi.com"
HEADERS = {
    "x-rapidapi-key": os.getenv("RAPIDAPI_KEY", ""),
    "x-rapidapi-host": os.getenv("RAPIDAPI_HOST", "cricbuzz-cricket.p.rapidapi.com"),
}
CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
_QUOTA_PAUSED_UNTIL = 0.0   # after a 429, skip API calls for a while and serve cache
PAUSE_SECONDS = 1800


def quota_paused():
    """True while the API is paused because the quota/rate limit was hit."""
    return time.time() < _QUOTA_PAUSED_UNTIL


def _read_cache(cache_file):
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    return None


def fetch(endpoint, max_age=300, retries=3):
    """GET an endpoint (e.g. 'matches/v1/live').

    Uses a cached copy if it is younger than `max_age` seconds, to save
    free-tier API calls. Retries on timeouts. Returns parsed JSON or None.
    """
    safe_name = re.sub(r"[^A-Za-z0-9_-]", "_", endpoint.strip("/"))
    cache_file = CACHE_DIR / (safe_name + ".json")
    global _QUOTA_PAUSED_UNTIL
    if cache_file.exists() and time.time() - cache_file.stat().st_mtime < max_age:
        return _read_cache(cache_file)
    if quota_paused():
        return _read_cache(cache_file)  # don't hit the API again until the pause ends

    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(f"{BASE_URL}/{endpoint.strip('/')}",
                                headers=HEADERS, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                cache_file.write_text(json.dumps(data), encoding="utf-8")
                return data
            if resp.status_code == 429:
                _QUOTA_PAUSED_UNTIL = time.time() + PAUSE_SECONDS
                print("Cricbuzz API quota reached (429) - serving cached data for the next 30 min")
                break
            print(f"API error {resp.status_code} for {endpoint}")
            return None
        except requests.RequestException as e:
            print(f"Attempt {attempt} failed for {endpoint}: {e}")
            time.sleep(2 * attempt)

    # Fall back to a stale cache rather than nothing
    return _read_cache(cache_file)
