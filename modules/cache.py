"""
File-based JSON caching module with TTL support.
"""

import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any


CACHE_DIR = Path(__file__).parent.parent / "cache"


def _ensure_cache_dir():
    """Ensure cache directory exists."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _get_cache_file(key: str) -> Path:
    """Get cache file path for a given key."""
    _ensure_cache_dir()
    return CACHE_DIR / f"{key}.json"


def cache_get(key: str, ttl_seconds: int = 1800) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached data if it exists and is still fresh.

    Args:
        key: Cache key (will be used as filename)
        ttl_seconds: Time to live in seconds (default 30 minutes)

    Returns:
        Cached data dict if found and fresh, None otherwise
    """
    cache_file = _get_cache_file(key)

    if not cache_file.exists():
        return None

    try:
        with open(cache_file, "r") as f:
            cached = json.load(f)

        timestamp = datetime.fromisoformat(cached.get("_timestamp", ""))
        age = (datetime.now() - timestamp).total_seconds()

        if age < ttl_seconds:
            return cached.get("data")
    except (json.JSONDecodeError, ValueError):
        pass

    return None


def cache_set(key: str, data: Dict[str, Any]) -> None:
    """
    Store data in cache with timestamp.

    Args:
        key: Cache key
        data: Data to cache
    """
    _ensure_cache_dir()
    cache_file = _get_cache_file(key)

    cached = {
        "_timestamp": datetime.now().isoformat(),
        "data": data,
    }

    with open(cache_file, "w") as f:
        json.dump(cached, f, indent=2)


def cache_clear(key: str = None) -> None:
    """
    Clear cache. If key is None, clears all cached files.

    Args:
        key: Specific key to clear, or None for all
    """
    if key:
        cache_file = _get_cache_file(key)
        if cache_file.exists():
            cache_file.unlink()
    else:
        _ensure_cache_dir()
        for f in CACHE_DIR.glob("*.json"):
            f.unlink()


def get_cache_age(key: str) -> Optional[int]:
    """
    Get age of cached data in seconds.

    Args:
        key: Cache key

    Returns:
        Age in seconds if cached, None otherwise
    """
    cache_file = _get_cache_file(key)

    if not cache_file.exists():
        return None

    try:
        with open(cache_file, "r") as f:
            cached = json.load(f)
        timestamp = datetime.fromisoformat(cached.get("_timestamp", ""))
        return int((datetime.now() - timestamp).total_seconds())
    except (json.JSONDecodeError, ValueError):
        return None
