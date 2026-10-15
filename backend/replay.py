"""Record a live discovery run and replay it later with realistic delays.

DEMO_RECORD=1  -> while running live, events are saved to demo/replay_snapshot.json
DEMO_REPLAY=1  -> /api/discover replays that file (no network, no credits) — demo-day safety net
DEMO_REPLAY_SPEED=2 -> play twice as fast
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Iterator

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT = os.environ.get("REPLAY_SNAPSHOT", os.path.join(ROOT, "demo", "replay_snapshot.json"))


def record(events: Iterator[dict[str, Any]], path: str = SNAPSHOT, recorded_from: str = "live") -> Iterator[dict[str, Any]]:
    """Pass-through generator that stores (seconds_since_start, event) pairs."""
    start = time.time()
    frames: list[dict[str, Any]] = []
    try:
        for ev in events:
            frames.append({"t": round(time.time() - start, 3), "event": ev})
            yield ev
    finally:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"recorded_from": recorded_from, "recorded_at": time.time(), "frames": frames}, fh,
                      default=str, indent=1)


def load(path: str = SNAPSHOT) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def available(path: str = SNAPSHOT) -> bool:
    return os.path.exists(path)


def play(path: str = SNAPSHOT, speed: float | None = None) -> Iterator[dict[str, Any]]:
    speed = speed or float(os.environ.get("DEMO_REPLAY_SPEED", "1") or 1)
    snap = load(path)
    last = 0.0
    for frame in snap["frames"]:
        gap = max(0.0, (frame["t"] - last) / speed)
        if gap:
            time.sleep(min(gap, 8.0))         # never stall a demo on one slow agent run
        last = frame["t"]
        ev = dict(frame["event"])
        if ev.get("stage") == "ranked":
            meta = dict(ev.get("meta") or {})
            meta.update(mode="replay", recorded_from=snap.get("recorded_from", "unknown"),
                        sample=snap.get("recorded_from") != "live")
            ev["meta"] = meta
        yield ev
