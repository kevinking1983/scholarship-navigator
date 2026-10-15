"""Capture deck screenshots with Playwright (Chromium is pre-installed; do NOT run `playwright install`).

    python scripts/capture.py [--mode replay|mock] [--port 8787]

Starts the app in DEMO_REPLAY (falls back to MOCK if no snapshot), clicks through the flow and saves
deck/assets/01-profile.png … 06-prefill-result.png at 1440×900, plus *-mobile.png at 390×844.
"""
from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "deck", "assets")
SHOTS = ["01-profile", "02-progress", "03-results", "04-checklist", "05-prefill-live", "06-prefill-result"]


def wait_http(url: str, timeout: float = 30) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            urllib.request.urlopen(url, timeout=2).read()
            return
        except Exception:
            time.sleep(0.4)
    raise RuntimeError(f"server did not start: {url}")


def start_server(mode: str, port: int) -> subprocess.Popen:
    env = dict(os.environ, PORT=str(port), MOCK_DELAY="0.4", DEMO_REPLAY_SPEED="3")
    env.pop("TINYFISH_API_KEY", None)                       # screenshots never spend credits
    if mode == "replay" and os.path.exists(os.path.join(ROOT, "demo", "replay_snapshot.json")):
        env["DEMO_REPLAY"] = "1"
    else:
        env["MOCK"] = "1"
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(port)],
                            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    wait_http(f"http://127.0.0.1:{port}/api/health")
    return proc


def shoot(page, name: str, suffix: str, selector: str | None = None, full: bool = False) -> None:
    path = os.path.join(ASSETS, f"{name}{suffix}.png")
    if selector:
        page.locator(selector).first.scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        page.locator(selector).first.screenshot(path=path)
    else:
        page.screenshot(path=path, full_page=full)
    print("  saved", os.path.relpath(path, ROOT))


def run_flow(browser, base: str, viewport: dict, suffix: str) -> None:
    ctx = browser.new_context(viewport=viewport, device_scale_factor=2, color_scheme="light")
    page = ctx.new_page()
    page.goto(base + "/", wait_until="networkidle")
    page.wait_for_selector("#samples .chip")
    page.locator("#samples .chip").first.click()
    shoot(page, SHOTS[0], suffix, "#profile-section")

    page.click("#findBtn")
    page.wait_for_selector(".step.active", timeout=15000)
    page.wait_for_selector("#cards .sch", timeout=30000)                 # at least one card arrived mid-run
    shoot(page, SHOTS[1], suffix, "#progress-section")

    page.wait_for_selector(".step[data-step=ranked].done", timeout=120000)
    page.wait_for_timeout(500)
    shoot(page, SHOTS[2], suffix, "#results-section")
    shoot(page, SHOTS[3], suffix, "#checklist-section")

    page.check("#pfConsent")
    page.click("#pfStart")
    page.wait_for_selector("#liveFrame:not(.hidden)", timeout=20000)
    page.wait_for_timeout(2500)
    shoot(page, SHOTS[4], suffix, "#prefill-section")

    page.wait_for_selector("#pfResult:not(.hidden)", timeout=90000)
    page.wait_for_timeout(400)
    shoot(page, SHOTS[5], suffix, "#prefill-section")
    ctx.close()


def chromium_kwargs() -> dict:
    """Use the pre-installed Chromium when the pip Playwright version expects a different build (never run `playwright install`)."""
    for cand in (os.environ.get("CHROMIUM_PATH"), "/opt/pw-browsers/chromium",
                 "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"):
        if cand and os.path.isfile(cand) and os.access(cand, os.X_OK):
            return {"executable_path": cand}
    return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="replay", choices=["replay", "mock"])
    ap.add_argument("--port", type=int, default=0)
    args = ap.parse_args()
    port = args.port or _free_port()
    os.makedirs(ASSETS, exist_ok=True)
    proc = start_server(args.mode, port)
    base = f"http://127.0.0.1:{port}"
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(**chromium_kwargs())
            print("desktop 1440x900")
            run_flow(browser, base, {"width": 1440, "height": 900}, "")
            print("mobile 390x844")
            run_flow(browser, base, {"width": 390, "height": 844}, "-mobile")
            # bonus: the practice form + the BLOCKED page as evidence
            ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
            pg = ctx.new_page()
            pg.goto(base + "/demo-form", wait_until="networkidle")
            pg.screenshot(path=os.path.join(ASSETS, "07-demo-form.png"), full_page=False)
            pg.click("#submitBtn")
            pg.wait_for_load_state("networkidle")
            pg.screenshot(path=os.path.join(ASSETS, "08-blocked.png"))
            print("  saved deck/assets/07-demo-form.png, 08-blocked.png")
            browser.close()
    finally:
        proc.terminate()
    return 0


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


if __name__ == "__main__":
    sys.exit(main())
