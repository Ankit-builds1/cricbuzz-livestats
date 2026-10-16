# © 2026 Ankit Dash (github.com/Ankit-builds1) - Cricbuzz LiveStats. All rights reserved.
"""Player photos from Wikipedia / Wikimedia Commons (openly licensed images).

Looks up the player's Wikipedia page and returns its lead image, a one-line
description and the page URL. Results (including misses) are cached on disk
so each player is looked up only once.
"""
import json
from pathlib import Path
from urllib.parse import quote

import requests

CACHE = Path(__file__).resolve().parent.parent / "data" / "cache" / "photos.json"
HEADERS = {"User-Agent": "CricbuzzLiveStats/1.0 (student analytics project)"}
API = "https://en.wikipedia.org/api/rest_v1/page/summary/"


def _load():
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(data):
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(data, indent=1), encoding="utf-8")


def _lookup(title):
    try:
        r = requests.get(API + quote(title.replace(" ", "_")), headers=HEADERS, timeout=8)
        if r.status_code != 200:
            return None
        d = r.json()
        if d.get("type") == "disambiguation" or "cricket" not in (d.get("description") or "").lower():
            return None  # not the cricketer page
        return {"img": (d.get("thumbnail") or {}).get("source"),
                "desc": d.get("description"),
                "url": d.get("content_urls", {}).get("desktop", {}).get("page")}
    except requests.RequestException:
        return None


def get_photo(full_name):
    """Return {'img', 'desc', 'url'} or None. Tries 'Name' then 'Name (cricketer)'."""
    cache = _load()
    if full_name in cache:
        return cache[full_name]
    result = None
    for title in (full_name, f"{full_name} (cricketer)"):
        result = _lookup(title)
        if result:
            break
    cache[full_name] = result
    _save(cache)
    return result


def initials(name):
    parts = [p for p in name.split() if p]
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()
