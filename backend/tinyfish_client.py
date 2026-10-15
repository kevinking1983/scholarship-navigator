"""ALL TinyFish calls live here.

Pipeline (see README table):
  1. Discover  Search  (free)    client.search.query        1 open-web set + 1 government set (include_domains)
  2. Filter    Fetch   (free)    client.fetch.get_contents  batches of 10 over *all* candidates
  3. Extract   Agent   (credits) client.agent.run           parallel, output_schema, cached 24h, capped by TOP_K
  4. Match     none    (free)    matcher.rank
  5. Apply     Agent   (credits) client.agent.stream        strict mode, max_steps=60, NEVER submits

Modes:  live (key present) · mock (MOCK=1 or no key) · replay (DEMO_REPLAY=1)
"""
from __future__ import annotations

import concurrent.futures as cf
import os
import re
import time
from typing import Any, Iterator
from urllib.parse import urlparse

from dotenv import load_dotenv

import cache
import mock_data
import replay
from matcher import Profile, document_checklist, rank

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

TOP_K = int(os.environ.get("TOP_K", "6"))                # hard cap on Agent extraction runs per discovery
EXTRACT_WORKERS = int(os.environ.get("EXTRACT_WORKERS", "4"))
RETRY_THIN_EXTRACTION = os.environ.get("RETRY_THIN_EXTRACTION", "0") == "1"
SCHEMA_VERSION = "v3"                                     # bump to invalidate cached extractions

SOCIAL_EXCLUDE = ("facebook.com,instagram.com,twitter.com,x.com,youtube.com,linkedin.com,quora.com,reddit.com,"
                  "pinterest.com,t.me,telegram.me,whatsapp.com,tiktok.com")
GOV_DOMAINS = "scholarships.gov.in,myscheme.gov.in,gov.in,nic.in"
STATE_PORTALS = {
    "Telangana": "telanganaepass.cgg.gov.in", "Andhra Pradesh": "jnanabhumi.ap.gov.in",
    "Maharashtra": "mahadbt.maharashtra.gov.in", "Bihar": "pmsonline.bih.nic.in",
    "Karnataka": "ssp.postmatric.karnataka.gov.in", "Uttar Pradesh": "scholarship.up.gov.in",
    "West Bengal": "svmcm.wb.gov.in", "Rajasthan": "sje.rajasthan.gov.in",
    "Madhya Pradesh": "scholarshipportal.mp.nic.in", "Gujarat": "digitalgujarat.gov.in",
    "Odisha": "scholarship.odisha.gov.in", "Jharkhand": "ekalyan.cgg.gov.in",
    "Chhattisgarh": "postmatric-scholarship.cg.nic.in", "Punjab": "scholarships.punjab.gov.in",
    "Haryana": "harchhatravratti.highereduhry.ac.in", "Kerala": "dcescholarship.kerala.gov.in",
    "Delhi": "edistrict.delhigovt.nic.in", "Tamil Nadu": "tn.gov.in",
}
GOV_TLDS = (".gov.in", ".nic.in", ".gov", ".ac.in", ".edu.in")
SCHOLARSHIP_WORDS = ("scholarship", "scheme", "fellowship", "financial assistance", "stipend", "fee reimbursement",
                     "shishyavrutti", "chhatravriti", "chhatravratti", "छात्रवृत्ति", "vidyarthi", "yojana")

# Only basic JSON-schema keywords: type / properties / items / required. Anything else is rejected.
SCHOLARSHIP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "provider": {"type": "string"},
        "source_type": {"type": "string"},
        "amount": {"type": "string"},
        "deadline": {"type": "string"},
        "eligibility": {
            "type": "object",
            "properties": {
                "states": {"type": "array", "items": {"type": "string"}},
                "gender": {"type": "string"},
                "categories": {"type": "array", "items": {"type": "string"}},
                "minority_only": {"type": "boolean"},
                "pwd_only": {"type": "boolean"},
                "single_girl_child_only": {"type": "boolean"},
                "course_levels": {"type": "array", "items": {"type": "string"}},
                "streams": {"type": "array", "items": {"type": "string"}},
                "years_of_study": {"type": "string"},
                "income_limit": {"type": "string"},
                "min_marks_10": {"type": "string"},
                "min_marks_12": {"type": "string"},
                "min_marks_current": {"type": "string"},
                "institution_type": {"type": "string"},
            },
        },
        "documents_required": {"type": "array", "items": {"type": "string"}},
        "application_url": {"type": "string"},
        "how_to_apply": {"type": "string"},
        "is_open": {"type": "boolean"},
        "notes": {"type": "string"},
    },
    "required": ["name", "amount", "deadline", "eligibility", "documents_required"],
}

PREFILL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "filled": {"type": "array", "items": {"type": "object", "properties": {
            "field": {"type": "string"}, "value": {"type": "string"}}, "required": ["field", "value"]}},
        "needs_manual_input": {"type": "array", "items": {"type": "object", "properties": {
            "field": {"type": "string"}, "reason": {"type": "string"}}, "required": ["field", "reason"]}},
        "stopped_before": {"type": "string"},
    },
    "required": ["filled", "needs_manual_input", "stopped_before"],
}

NEVER_SUBMIT = (
    "SAFETY RULES (mandatory): Never click Submit, Pay, Final Save, Register, Confirm or any button that sends the "
    "application. Never create an account, never enter a password, OTP or captcha, never upload a file, never enter "
    "an Aadhaar, PAN or bank account number. If a login, OTP or captcha wall appears before the form, stop at once. "
    "When every allowed field is filled or you are blocked, STOP and report."
)


# --------------------------------------------------------------------------- #
# Mode / client
# --------------------------------------------------------------------------- #

def api_key() -> str | None:
    return (os.environ.get("TINYFISH_API_KEY") or "").strip() or None


def mode() -> str:
    if os.environ.get("DEMO_REPLAY") == "1":
        return "replay"
    if os.environ.get("MOCK") == "1" or not api_key():
        return "mock"
    return "live"


_client = None


def client():
    global _client
    if _client is None:
        from tinyfish import TinyFish
        _client = TinyFish(api_key=api_key(), timeout=float(os.environ.get("TINYFISH_TIMEOUT", "600")))
    return _client


def classify_domain(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return "government" if host.endswith(GOV_TLDS) else "private"


# --------------------------------------------------------------------------- #
# Step 1 — queries & search
# --------------------------------------------------------------------------- #

def build_queries(profile: Profile) -> list[dict[str, Any]]:
    """Profile-driven queries. Government set uses include_domains; open-web set excludes social sites."""
    course = " ".join(x for x in (profile.course, profile.branch) if x).strip()
    level = profile.n_level or profile.course_level or ""
    stream = profile.n_stream or ""
    who = course or stream or level or "college"
    gender = profile.n_gender if profile.n_gender in ("female", "male") else ""
    gender_word = {"female": "girls", "male": ""}.get(gender, "")
    cat = profile.n_category if profile.n_category and profile.n_category not in ("all", "General") else ""
    home = profile.n_domicile if profile.n_domicile not in (None, "all") else ""
    year_label = f"year {profile.year}" if profile.year else ""
    session = "2026-27"
    income = f"income below {profile.family_income // 100000} lakh" if profile.family_income else ""

    gov_domains = GOV_DOMAINS
    if home and STATE_PORTALS.get(home):
        gov_domains += "," + STATE_PORTALS[home]

    queries: list[dict[str, Any]] = [
        {"query": " ".join(x for x in ("post matric scholarship", home, cat, who, session) if x),
         "include_domains": gov_domains, "source_type": "government"},
        {"query": " ".join(x for x in (who, "students scholarship scheme", cat, gender_word, "eligibility documents") if x),
         "include_domains": gov_domains, "source_type": "government"},
        {"query": " ".join(x for x in (who, "scholarship", gender_word, year_label, session, "India apply online") if x),
         "exclude_domains": SOCIAL_EXCLUDE, "source_type": "private"},
        {"query": " ".join(x for x in ("CSR foundation trust scholarship", stream or who, "students", income, session) if x),
         "exclude_domains": SOCIAL_EXCLUDE, "source_type": "private"},
    ]
    extras = []
    if profile.minority:
        extras.append({"query": f"minority community scholarship {who} {session}", "include_domains": gov_domains,
                       "source_type": "government"})
    if profile.pwd:
        extras.append({"query": f"scholarship for students with disabilities {level} {session}",
                       "include_domains": gov_domains, "source_type": "government"})
    if profile.single_girl_child:
        extras.append({"query": f"single girl child scholarship {level} {session}", "exclude_domains": SOCIAL_EXCLUDE,
                       "source_type": "private"})
    seen, out = set(), []
    for q in queries + extras:
        q["query"] = re.sub(r"\s+", " ", q["query"]).strip()
        if q["query"].lower() not in seen:
            seen.add(q["query"].lower())
            out.append(q)
    return out[:6]


def _search_one(q: dict[str, Any]) -> list[dict[str, Any]]:
    def produce():
        resp = client().search.query(
            q["query"], location="IN", language="en",
            purpose="Find Indian government schemes and private scholarships a student can apply to, with eligibility, "
                    "amount, deadline and documents required.",
            include_domains=q.get("include_domains"), exclude_domains=q.get("exclude_domains"),
        )
        return [r.model_dump() for r in resp.results]
    results, _hit = cache.cached("search", {"q": q["query"], "inc": q.get("include_domains"), "exc": q.get("exclude_domains")}, produce)
    for r in results:
        r["query"] = q["query"]
        r["source_type"] = "government" if classify_domain(r["url"]) == "government" else q["source_type"]
    return results


def search_candidates(queries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for q in queries:
        try:
            results = _search_one(q)
        except Exception as exc:  # one failed query must not kill discovery
            results = []
            out.append({"_error": f"search failed for '{q['query']}': {exc}"})
        for r in results:
            key = re.sub(r"[#?].*$", "", r["url"]).rstrip("/").lower()
            if key in seen or not r["url"].startswith("http"):
                continue
            seen.add(key)
            out.append(r)
    errors = [o["_error"] for o in out if "_error" in o]
    cands = [o for o in out if "_error" not in o]
    for c in cands:
        c["search_errors"] = errors
    return cands


# --------------------------------------------------------------------------- #
# Step 2 — fetch filter
# --------------------------------------------------------------------------- #

def looks_like_scholarship(text: str) -> bool:
    low = (text or "").lower()
    return any(w in low for w in SCHOLARSHIP_WORDS)


def fetch_filter(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Render every candidate (batches of 10), keep scholarship pages, flag thin/JS-only pages as needs_agent."""
    kept: list[dict[str, Any]] = []
    for i in range(0, len(candidates), 10):
        batch = candidates[i:i + 10]
        urls = [c["url"] for c in batch]

        def produce(urls=urls):
            resp = client().fetch.get_contents(
                urls, format="markdown", per_url_timeout_ms=20_000,
                purpose="Check whether each page describes a scholarship or scheme for Indian students.")
            return {"results": [r.model_dump() for r in resp.results], "errors": [e.model_dump() for e in resp.errors]}

        try:
            data, _hit = cache.cached("fetch", {"urls": urls}, produce)
        except Exception as exc:
            data = {"results": [], "errors": [{"url": u, "error": str(exc)} for u in urls]}
        by_url = {r["url"]: r for r in data["results"]}
        failed = {e["url"]: e["error"] for e in data["errors"]}
        for c in batch:
            r = by_url.get(c["url"])
            text = (r or {}).get("text") or ""
            title = (r or {}).get("title") or c.get("title") or ""
            c["page_title"] = title
            c["page_chars"] = len(text)
            c["fetch_error"] = failed.get(c["url"])
            # JS-only / blocked government pages come back thin: that is exactly where a real browser agent is needed
            c["needs_agent"] = bool(c["fetch_error"]) or len(text) < 600
            relevant = looks_like_scholarship(" ".join((title, c.get("snippet", ""), text[:4000])))
            if relevant or (c["needs_agent"] and c.get("source_type") == "government"):
                c["page_excerpt"] = text[:1500]
                kept.append(c)
    # Agent budget: pages Fetch could not read go first (highest value), then search order
    kept.sort(key=lambda c: (0 if c["needs_agent"] else 1, c.get("position", 99)))
    return kept


# --------------------------------------------------------------------------- #
# Step 3 — agent extraction
# --------------------------------------------------------------------------- #

def extraction_goal(narrow: bool = False) -> str:
    base = (
        "You are reading a scholarship or government scheme page for an Indian student. Read the whole page "
        "(expand accordions, open 'eligibility', 'documents' or 'how to apply' tabs if present; follow at most one "
        "link to the official guidelines PDF/page on the same site if the details are not on this page). Extract: "
        "scheme name; provider (ministry/department/state/company/trust); source_type ('government' or 'private'); "
        "amount or benefit; application deadline exactly as written (or 'Rolling' / 'Closed' / 'Not stated'); "
        "eligibility — states (list, or ['All India']), gender ('All'/'Female'/'Male'), categories (list such as "
        "['SC','ST','OBC','EWS','General'] or ['All']), minority_only, pwd_only, single_girl_child_only (true/false), "
        "course_levels (e.g. ['Class 11-12','Diploma','UG','PG','PhD'] or ['Post Matric']), streams (e.g. "
        "['Engineering','Medicine','Arts','Commerce','Science','Law'] or ['All']), years_of_study, income_limit "
        "(annual family income cap as written), min_marks_10, min_marks_12, min_marks_current, institution_type "
        "('government'/'private'/'any'); documents_required (list); application_url; how_to_apply (1-2 lines); "
        "is_open; notes. Use empty strings/lists when the page does not say. Do NOT fill or submit any form, do NOT "
        "log in. Return only the JSON."
    )
    if narrow:
        base = ("The page may hide details behind tabs or a PDF. Focus ONLY on finding: the application deadline, "
                "the annual family income limit, the categories/gender/state restrictions, and the documents required. "
                + base)
    return base


def _is_thin(result: dict[str, Any]) -> bool:
    e = result.get("eligibility") or {}
    filled = sum(1 for v in (result.get("amount"), result.get("deadline"), e.get("income_limit"),
                             result.get("documents_required")) if v)
    return filled <= 1


def extract_scheme(cand: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Run the Agent on one page (cached). Returns (scheme, cache_hit). Never raises."""
    from tinyfish import AgentConfig

    url = cand["url"]
    gov = cand.get("source_type") == "government"

    def run(narrow: bool = False) -> dict[str, Any]:
        resp = client().agent.run(
            goal=extraction_goal(narrow), url=url,
            browser_profile="stealth" if gov else "lite",
            agent_config=AgentConfig(mode="default", max_steps=40, max_duration_seconds=240),
            output_schema=SCHOLARSHIP_SCHEMA,
        )
        if resp.status != "COMPLETED" or not resp.result:
            msg = resp.error.message if resp.error else f"status {resp.status}"
            raise RuntimeError(msg)
        out = dict(resp.result)
        out["_run"] = {"run_id": resp.run_id, "steps": resp.num_of_steps,
                       "seconds": (resp.finished_at - resp.started_at).total_seconds()
                       if resp.started_at and resp.finished_at else None}
        return out

    def produce() -> dict[str, Any]:
        out = run()
        if RETRY_THIN_EXTRACTION and _is_thin(out):
            second = run(narrow=True)
            for k, v in second.items():
                if v and not out.get(k):
                    out[k] = v
            out["_run"]["retried"] = True
        return out

    try:
        data, hit = cache.cached("agent", {"url": url, "schema": SCHEMA_VERSION}, produce)
        data = dict(data)
        data["extraction"] = "agent"
    except Exception as exc:
        # fall back to the search snippet so the student still sees the lead
        data = {
            "name": cand.get("page_title") or cand.get("title") or url, "provider": cand.get("site_name", ""),
            "amount": "", "deadline": "", "eligibility": {}, "documents_required": [],
            "notes": (cand.get("snippet") or "")[:300], "extraction": "snippet",
            "extraction_error": str(exc)[:200],
        }
        hit = False
    data.setdefault("name", cand.get("title") or url)
    data["source_url"] = url
    data["source_type"] = data.get("source_type") if data.get("source_type") in ("government", "private") else cand.get("source_type", classify_domain(url))
    data.setdefault("application_url", url)
    data["needs_agent"] = cand.get("needs_agent", False)
    return data, hit


# --------------------------------------------------------------------------- #
# Full discovery (streamed stages)
# --------------------------------------------------------------------------- #

def _live_discover_events(profile: Profile, top_k: int) -> Iterator[dict[str, Any]]:
    t0 = time.time()
    queries = build_queries(profile)
    yield {"stage": "searching", "queries": [q["query"] for q in queries], "message": f"Searching {len(queries)} queries"}
    cands = search_candidates(queries)
    errs = cands[0]["search_errors"] if cands else []
    yield {"stage": "found", "count": len(cands), "errors": errs, "message": f"Found {len(cands)} pages"}
    if not cands:
        yield {"stage": "ranked", "results": [], "checklist": [], "meta": {"mode": "live", "sample": False,
               "queries": [q["query"] for q in queries], "agent_runs": 0, "cache_hits": 0, "seconds": round(time.time() - t0, 1),
               "errors": errs}, "message": "No pages found"}
        return
    kept = fetch_filter(cands)
    yield {"stage": "kept", "count": len(kept), "needs_agent": sum(1 for k in kept if k["needs_agent"]),
           "message": f"Kept {len(kept)} scholarship pages"}
    todo = kept[:top_k]
    schemes: list[dict[str, Any]] = []
    hits = 0
    with cf.ThreadPoolExecutor(max_workers=max(1, min(EXTRACT_WORKERS, len(todo) or 1))) as pool:
        futs = {pool.submit(extract_scheme, c): c for c in todo}
        done = 0
        for fut in cf.as_completed(futs):
            scheme, hit = fut.result()
            hits += int(hit)
            done += 1
            schemes.append(scheme)
            ranked_now = rank(profile, schemes)
            just = next(r for r in ranked_now if r["source_url"] == scheme["source_url"])
            yield {"stage": "extracting", "done": done, "total": len(todo), "name": scheme["name"], "cache_hit": hit,
                   "scheme": just, "message": f"Extracted {done}/{len(todo)}: {scheme['name']}"}
    final = rank(profile, schemes)
    yield {"stage": "ranked", "results": final, "checklist": document_checklist(final),
           "meta": {"mode": "live", "sample": False, "queries": [q["query"] for q in queries],
                    "candidates": len(cands), "kept": len(kept), "agent_runs": len(todo) - hits, "cache_hits": hits,
                    "skipped_for_budget": max(0, len(kept) - top_k), "seconds": round(time.time() - t0, 1), "errors": errs},
           "message": f"Ranked {len(final)} schemes"}


def discover_events(profile: Profile, top_k: int | None = None, mock_delay: float | None = None) -> Iterator[dict[str, Any]]:
    """Yield stage events: searching -> found -> kept -> extracting (xN) -> ranked. Never persists the profile."""
    m = mode()
    if m == "replay" and replay.available():
        yield from replay.play()
        return
    if m == "mock" or m == "replay":           # replay requested but no snapshot: fall back to sample data
        delay = mock_delay if mock_delay is not None else float(os.environ.get("MOCK_DELAY", "0.35"))
        yield from mock_data.mock_discover_events(profile, delay=delay)
        return
    events = _live_discover_events(profile, top_k or TOP_K)
    if os.environ.get("DEMO_RECORD") == "1":
        events = replay.record(events, recorded_from="live")
    try:
        yield from events
    except Exception as exc:
        # friendly failure + automatic fallback so a live demo never ends on a stack trace
        yield {"stage": "error", "message": f"TinyFish call failed: {exc}. Showing sample data instead."}
        yield from mock_data.mock_discover_events(profile, delay=0.1)


def discover(profile: Profile, top_k: int | None = None) -> dict[str, Any]:
    """Plain (non-streamed) version for tests and simple clients."""
    final: dict[str, Any] = {"results": [], "checklist": [], "meta": {}}
    for ev in discover_events(profile, top_k=top_k, mock_delay=0.0):
        if ev.get("stage") == "ranked":
            final = {"results": ev["results"], "checklist": ev["checklist"], "meta": ev["meta"]}
    return final


# --------------------------------------------------------------------------- #
# Step 5 — form pre-fill (streamed, never submits)
# --------------------------------------------------------------------------- #

PREFILL_FIELD_LABELS = [
    ("name", "Full name"), ("gender", "Gender"), ("category", "Category"), ("domicile_state", "State of domicile"),
    ("state", "State of study"), ("course_level", "Course level"), ("course", "Course"), ("branch", "Branch / subject"),
    ("year", "Current year"), ("marks_10", "Class 10 percentage"), ("marks_12", "Class 12 percentage"),
    ("marks_current", "Latest exam percentage"), ("family_income", "Annual family income (INR)"),
    ("institution_type", "Institution type"),
]


def prefill_fields(profile: Profile) -> list[dict[str, str]]:
    out = []
    for key, label in PREFILL_FIELD_LABELS:
        v = getattr(profile, key)
        if v not in (None, ""):
            out.append({"field": label, "value": str(v)})
    if profile.minority is not None:
        out.append({"field": "Minority community", "value": "Yes" if profile.minority else "No"})
    if profile.pwd is not None:
        out.append({"field": "Person with disability", "value": "Yes" if profile.pwd else "No"})
    return out


def prefill_goal(fields: list[dict[str, str]], scheme_name: str) -> str:
    lines = "\n".join(f"- {f['field']}: {f['value']}" for f in fields)
    return (
        f"Pre-fill the scholarship application form for '{scheme_name}' on this page with the student's details "
        f"below. Fill text boxes, dropdowns, radio buttons and date fields that match these details. Leave anything "
        f"not listed blank.\n{lines}\n\n{NEVER_SUBMIT} Report which fields you filled, which fields still need the "
        f"student (and why), and the exact section/button you stopped before. Stop and report."
    )


def prefill_events(url: str, profile: Profile, scheme_name: str = "the scholarship",
                   mock_delay: float | None = None) -> Iterator[dict[str, Any]]:
    """Yield {type: STARTED|STREAMING_URL|PROGRESS|HEARTBEAT|COMPLETE|ERROR, ...} dicts."""
    fields = prefill_fields(profile)
    if mode() != "live" or url.startswith("/"):
        delay = mock_delay if mock_delay is not None else float(os.environ.get("MOCK_DELAY", "0.6"))
        yield from mock_data.mock_prefill_events(fields, url, delay=delay)
        return

    from tinyfish import (AgentConfig, APIStatusError, APITimeoutError, CompleteEvent, HeartbeatEvent,
                          ProgressEvent, StartedEvent, StreamingUrlEvent)
    goal = prefill_goal(fields, scheme_name)
    saw_url = False
    try:
        with client().agent.stream(
            goal=goal, url=url, browser_profile="stealth",
            agent_config=AgentConfig(mode="strict", max_steps=60, max_duration_seconds=300),
            output_schema=PREFILL_SCHEMA,
        ) as stream:
            for ev in stream:
                if isinstance(ev, StartedEvent):
                    yield {"type": "STARTED", "run_id": ev.run_id, "message": "Agent started (strict mode, max 60 steps)"}
                elif isinstance(ev, StreamingUrlEvent):
                    saw_url = True
                    yield {"type": "STREAMING_URL", "run_id": ev.run_id, "streaming_url": ev.streaming_url,
                           "message": "Live browser connected"}
                elif isinstance(ev, ProgressEvent):
                    yield {"type": "PROGRESS", "message": ev.purpose}
                elif isinstance(ev, HeartbeatEvent):
                    yield {"type": "HEARTBEAT"}
                elif isinstance(ev, CompleteEvent):
                    result = ev.result_json or {}
                    if ev.status != "COMPLETED":
                        msg = ev.error.message if ev.error else f"run ended with status {ev.status}"
                        yield {"type": "COMPLETE", "run_id": ev.run_id, "status": str(ev.status), "result": result,
                               "message": f"Agent stopped: {msg}", "error": msg}
                    else:
                        if not saw_url:
                            yield {"type": "PROGRESS", "message": "No live browser URL was provided for this run."}
                        yield {"type": "COMPLETE", "run_id": ev.run_id, "status": "COMPLETED", "result": result,
                               "message": "Agent finished and stopped before submit"}
    except APITimeoutError:
        yield {"type": "ERROR", "message": "TinyFish timed out. The portal may be slow or blocking cloud browsers (no India proxy)."}
    except APIStatusError as exc:
        code = exc.response.status_code if getattr(exc, "response", None) is not None else "?"
        yield {"type": "ERROR", "message": f"TinyFish returned HTTP {code}: {exc.message}"}
    except Exception as exc:
        yield {"type": "ERROR", "message": f"Pre-fill failed: {exc}"}
