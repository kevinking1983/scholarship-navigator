"""Prove the TinyFish key works: one Search (free) + one Agent run (costs credits).

    python backend/smoke_test.py [--url https://...] [--skip-agent]

Writes evidence/smoke_<timestamp>.json with both raw responses (proof for the deck).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, ".env"))

DEFAULT_URL = "https://www.aicte-india.org/schemes/students-development-schemes/Pragati"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=DEFAULT_URL, help="public scholarship page for the Agent run")
    ap.add_argument("--query", default="NSP post matric scholarship 2026-27")
    ap.add_argument("--skip-agent", action="store_true", help="only run the free Search call")
    args = ap.parse_args()

    key = (os.environ.get("TINYFISH_API_KEY") or "").strip()
    if not key or key.startswith("your_"):
        print("ERROR: TINYFISH_API_KEY is missing. Copy .env.example to .env and paste your key from "
              "https://agent.tinyfish.ai/api-keys", file=sys.stderr)
        return 2

    from tinyfish import AgentConfig, TinyFish
    from tinyfish_client import SCHOLARSHIP_SCHEMA, extraction_goal

    client = TinyFish(api_key=key)
    evidence = {"ran_at": datetime.now().isoformat(timespec="seconds"), "sdk": _sdk_version()}

    # ---- 1. Search (free) -------------------------------------------------
    print(f"\n[1/2] Search: {args.query!r} (location=IN)")
    t = time.time()
    resp = client.search.query(args.query, location="IN", language="en",
                               purpose="Find official National Scholarship Portal pages for post-matric scholarships.")
    took = round(time.time() - t, 2)
    print(f"      {resp.total_results} results in {took}s")
    for r in resp.results[:5]:
        print(f"      {r.position:>2}. {r.title[:70]}\n          {r.url}")
    evidence["search"] = {"query": args.query, "seconds": took, "response": resp.model_dump()}

    # ---- 2. Agent run (credits) --------------------------------------------
    if args.skip_agent:
        evidence["agent"] = {"skipped": True}
    else:
        print(f"\n[2/2] Agent extraction on {args.url}")
        t = time.time()
        run = client.agent.run(goal=extraction_goal(), url=args.url, browser_profile="stealth",
                               agent_config=AgentConfig(mode="default", max_steps=40, max_duration_seconds=240),
                               output_schema=SCHOLARSHIP_SCHEMA)
        took = round(time.time() - t, 2)
        print(f"      status={run.status} steps={run.num_of_steps} run_id={run.run_id} time={took}s")
        if run.result:
            print(json.dumps(run.result, indent=2, ensure_ascii=False)[:3000])
        if run.error:
            print(f"      error: {run.error.message}")
        evidence["agent"] = {"url": args.url, "seconds": took, "response": run.model_dump(mode="json")}

    os.makedirs(os.path.join(ROOT, "evidence"), exist_ok=True)
    path = os.path.join(ROOT, "evidence", f"smoke_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(evidence, fh, indent=2, ensure_ascii=False, default=str)
    print(f"\nEvidence saved to {os.path.relpath(path, ROOT)}")
    return 0


def _sdk_version() -> str:
    try:
        from importlib.metadata import version
        return version("tinyfish")
    except Exception:
        return "unknown"


if __name__ == "__main__":
    sys.exit(main())
