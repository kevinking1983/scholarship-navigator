"""Scholarship Navigator API.

GET  /api/health            mode, version, replay availability
GET  /api/samples           sample student profiles for the "Try a sample student" button
POST /api/discover          plain JSON  {results, checklist, meta}
POST /api/discover/stream   SSE stage events (searching → found → kept → extracting… → ranked)
POST /api/prefill           SSE agent events (STARTED → STREAMING_URL → PROGRESS… → COMPLETE), never submits
POST /api/calendar          .ics of open deadlines
GET  /demo-form             practice replica of an NSP-style form (public, labelled)
POST /demo-form/submit      always answers BLOCKED — proof the agent never reaches it
GET  /                      frontend

Privacy: profiles are read from the request, used in memory and discarded. Nothing is logged or written.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Iterator
from urllib.parse import parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

import replay  # noqa: E402
import tinyfish_client as tf  # noqa: E402
from ics import build_ics  # noqa: E402
from matcher import Profile  # noqa: E402
from mock_data import SAMPLE_STUDENTS  # noqa: E402

VERSION = "0.3.0"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(ROOT, "frontend")

app = FastAPI(title="Scholarship Navigator", version=VERSION, docs_url="/api/docs", redoc_url=None)


def sse(events: Iterator[dict[str, Any]]) -> StreamingResponse:
    def gen():
        yield ": connected\n\n"
        try:
            for ev in events:
                yield "data: " + json.dumps(ev, default=str) + "\n\n"
        except Exception as exc:  # last line of defence: never drop the connection silently
            yield "data: " + json.dumps({"stage": "error", "type": "ERROR", "message": str(exc)}) + "\n\n"
        yield "data: " + json.dumps({"stage": "end", "type": "END"}) + "\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})


async def read_json(request: Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


@app.get("/api/health")
def health():
    return {"status": "ok", "version": VERSION, "mode": tf.mode(), "replay_available": replay.available(),
            "top_k": tf.TOP_K, "sdk": _sdk_version()}


def _sdk_version() -> str:
    try:
        from importlib.metadata import version
        return version("tinyfish")
    except Exception:
        return "unknown"


@app.get("/api/samples")
def samples():
    return SAMPLE_STUDENTS


@app.post("/api/discover")
async def discover(request: Request):
    body = await read_json(request)
    profile = Profile.from_dict(body.get("profile") or body)
    try:
        return tf.discover(profile)
    except Exception as exc:
        return JSONResponse({"error": str(exc), "results": [], "checklist": [], "meta": {"mode": tf.mode()}}, status_code=502)


@app.post("/api/discover/stream")
async def discover_stream(request: Request):
    body = await read_json(request)
    profile = Profile.from_dict(body.get("profile") or body)
    return sse(tf.discover_events(profile))


@app.post("/api/prefill")
async def prefill(request: Request):
    body = await read_json(request)
    url = str(body.get("url") or "").strip()
    if not url:
        return JSONResponse({"error": "url is required"}, status_code=400)
    profile = Profile.from_dict(body.get("profile") or {})
    scheme_name = str(body.get("scheme_name") or "the scholarship")
    if url.startswith("/"):                       # our own replica form: make it absolute for the cloud browser
        public = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
        if public and tf.mode() == "live":
            url = public + url
    return sse(tf.prefill_events(url, profile, scheme_name))


@app.post("/api/calendar")
async def calendar(request: Request):
    body = await read_json(request)
    text, count = build_ics(body.get("results") or [])
    return Response(text, media_type="text/calendar",
                    headers={"Content-Disposition": "attachment; filename=scholarship-deadlines.ics",
                             "X-Event-Count": str(count)})


@app.get("/demo-form", response_class=HTMLResponse)
def demo_form():
    return FileResponse(os.path.join(FRONTEND, "demo_form.html"), media_type="text/html")


@app.post("/demo-form/submit", response_class=HTMLResponse)
async def demo_form_submit(request: Request):
    raw = (await request.body()).decode("utf-8", "ignore")
    fields = {k: v[0] for k, v in parse_qs(raw).items()}
    # Nothing is stored. We only count how many fields arrived, as evidence on screen.
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>BLOCKED</title>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <style>body{{font-family:system-ui,sans-serif;background:#fff3f3;color:#7a1212;display:grid;place-items:center;min-height:100vh;margin:0;text-align:center;padding:24px}}
    .box{{max-width:560px;border:3px solid #c62828;border-radius:16px;padding:32px;background:#fff}}h1{{margin:0 0 8px;font-size:2rem}}p{{line-height:1.5}}a{{color:#0b5fff}}</style></head>
    <body><div class="box"><h1>⛔ BLOCKED</h1><p><strong>The agent should never reach this page.</strong></p>
    <p>This practice replica received a submission with {len(fields)} field(s). Nothing was saved. If you are seeing this
    during a demo, the safety rule failed — report it. If you clicked Submit yourself, that is expected: only a human may submit.</p>
    <p><a href="/demo-form">← Back to the practice form</a> · <a href="/">Home</a></p></div></body></html>"""
    return HTMLResponse(html, status_code=403)


@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(os.path.join(FRONTEND, "index.html"), media_type="text/html")


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), reload=False)
