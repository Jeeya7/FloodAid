"""
Cache service — lightweight JSON file cache.
No real database; swappable for Redis or a DB later.
"""

import json
import os
from typing import Any

_CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", ".cache.json")


def load_cache() -> dict[str, Any]:
    """Load the full cache dict from disk. Returns {} if the file does not exist."""
    try:
        with open(_CACHE_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_cache(cache: dict[str, Any]) -> None:
    """Persist the full cache dict to disk."""
    with open(_CACHE_FILE, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, indent=2)


def get_cached_location_data(key: str) -> Any | None:
    """Return cached data for *key*, or None if the key is absent."""
    return load_cache().get(key)


def set_cached_location_data(key: str, data: Any) -> None:
    """Write *data* under *key* and flush to disk."""
    cache = load_cache()
    cache[key] = data
    save_cache(cache)
