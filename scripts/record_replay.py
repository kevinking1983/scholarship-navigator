"""Record a discovery run into demo/replay_snapshot.json for DEMO_REPLAY=1.

    python scripts/record_replay.py [--student telangana_sc_btech]

With a real TINYFISH_API_KEY this records a GENUINE live run (recorded_from="live").
Without a key it records the sample pipeline (recorded_from="mock") so replay mode still works;
the UI then labels the replay as sample data. Re-run with a key before the demo.
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, ".env"))
os.environ.pop("DEMO_REPLAY", None)       # we are recording, not replaying

import replay  # noqa: E402
import tinyfish_client as tf  # noqa: E402
from matcher import Profile  # noqa: E402
from mock_data import SAMPLE_STUDENTS  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--student", default="telangana_sc_btech", choices=sorted(SAMPLE_STUDENTS))
    ap.add_argument("--out", default=replay.SNAPSHOT)
    args = ap.parse_args()
    profile = Profile.from_dict(SAMPLE_STUDENTS[args.student])
    m = tf.mode()
    print(f"mode={m} student={args.student} -> {os.path.relpath(args.out, ROOT)}")
    events = tf.discover_events(profile) if m == "live" else tf.discover_events(profile, mock_delay=0.9)
    for ev in replay.record(events, args.out, recorded_from=m):
        print(f"  {ev.get('stage'):<11} {str(ev.get('message', ''))[:90]}")
    print("saved." if m == "live" else "saved (SAMPLE run — re-record with a TINYFISH_API_KEY for a genuine snapshot).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
