"""Tiny disk cache for TinyFish results (Search, Fetch, Agent extraction).

Why: Agent runs cost credits and Search/Fetch take seconds. Caching makes a
repeated demo instant and protects the credit budget.

Privacy: keys are SHA-256 hashes of the query/URL. Cached *values* are only
scholarship/page data, never a student's profile.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, Callable

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.environ.get("CACHE_DIR", os.path.join(ROOT, ".cache"))
TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", str(24 * 3600)))


def enabled() -> bool:
    return os.environ.get("CACHE", "1") != "0"


def _key(namespace: str, material: Any) -> str:
    blob = json.dumps(material, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _path(namespace: str, material: Any) -> str:
    return os.path.join(CACHE_DIR, namespace, _key(namespace, material) + ".json")


def get(namespace: str, material: Any) -> Any | None:
    """Return the cached value, or None if missing/expired/disabled."""
    if not enabled():
        return None
    path = _path(namespace, material)
    try:
        if time.time() - os.path.getmtime(path) > TTL_SECONDS:
            return None
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)["value"]
    except (OSError, ValueError, KeyError):
        return None


def put(namespace: str, material: Any, value: Any) -> None:
    if not enabled():
        return
    path = _path(namespace, material)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"namespace": namespace, "saved_at": time.time(), "value": value}, fh, default=str)
    os.replace(tmp, path)


def cached(namespace: str, material: Any, producer: Callable[[], Any]) -> tuple[Any, bool]:
    """Return (value, hit). Calls producer() only on a miss."""
    hit = get(namespace, material)
    if hit is not None:
        return hit, True
    value = producer()
    put(namespace, material, value)
    return value, False
