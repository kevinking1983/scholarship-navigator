"""Offline tests — no network, no key, no credits.  Run:  python backend/test_pipeline.py

Fixtures PRAGATI_EXTRACTION / KOTAK_EXTRACTION are transcriptions of what the Agent returns for those pages
with SCHOLARSHIP_SCHEMA (kept here so the matcher is tested against real-world label wording, e.g. "Girls",
"Scheduled Caste", "₹8 lakh per annum", "31st October 2026").
"""
from __future__ import annotations

import os
import sys
import tempfile
import traceback
from datetime import date

os.environ["MOCK"] = "1"
os.environ["CACHE"] = "0"
os.environ.pop("DEMO_REPLAY", None)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import replay  # noqa: E402
import tinyfish_client as tf  # noqa: E402
from ics import build_ics  # noqa: E402
from matcher import (Profile, course_stream, document_checklist, normalize_category, normalize_gender,  # noqa: E402
                     normalize_level, normalize_state, parse_deadline, parse_money, rank, score)
from mock_data import SAMPLE_STUDENTS, mock_discover_events, mock_prefill_events, sample_schemes  # noqa: E402

TODAY = date(2026, 10, 15)

PRAGATI_EXTRACTION = {
    "name": "Pragati Scholarship Scheme for Girl Students",
    "provider": "All India Council for Technical Education (AICTE)",
    "source_type": "government",
    "amount": "Rs. 50,000/- per annum for every year of study",
    "deadline": "Last date: 31st October 2026",
    "eligibility": {
        "states": ["All India"], "gender": "Girls", "categories": ["All"],
        "course_levels": ["Degree", "Diploma"], "streams": ["Technical"], "years_of_study": "1st year (2nd year lateral)",
        "income_limit": "Rs. 8 lakh per annum", "min_marks_12": "", "institution_type": "AICTE approved",
    },
    "documents_required": ["Aadhaar Card", "Income Certificate", "Class 10th marksheet", "Class 12th marksheet",
                           "Admission letter", "Tuition fee receipt", "Bank passbook", "Parent's declaration"],
    "application_url": "https://scholarships.gov.in", "is_open": True,
}

KOTAK_EXTRACTION = {
    "name": "Kotak Kanya Scholarship",
    "provider": "Kotak Mahindra Group CSR",
    "source_type": "private",
    "amount": "₹1.5 lakh per year",
    "deadline": "30/09/2026",
    "eligibility": {
        "states": ["Pan India"], "gender": "Female", "categories": ["Open to all"], "course_levels": ["Undergraduate"],
        "streams": ["Engineering", "MBBS", "Law", "Architecture", "Design"], "years_of_study": "First year",
        "income_limit": "Rs 3,20,000 per annum", "min_marks_12": "85%",
    },
    "documents_required": ["12th marksheet", "Income proof", "Aadhar", "Admission letter", "Fee receipt",
                           "Bank account details", "Photograph"],
    "application_url": "https://kotakeducation.org/kotak-kanya-scholarship/",
}

TELANGANA_GIRL = Profile.from_dict(SAMPLE_STUDENTS["telangana_sc_btech"])
BIHAR_BOY = Profile.from_dict(SAMPLE_STUDENTS["bihar_obc_ba"])
MAHA_MBBS = Profile.from_dict(SAMPLE_STUDENTS["maharashtra_general_mbbs"])


def test_normalise_gender():
    for raw in ("Girls", "Women", "Female", "girl students", "F"):
        assert normalize_gender(raw) == "female", raw
    for raw in ("Boys", "Men", "male"):
        assert normalize_gender(raw) == "male", raw
    for raw in ("All", "Any", "Open to all", "Both"):
        assert normalize_gender(raw) == "all", raw
    assert normalize_gender("") is None and normalize_gender(None) is None   # unspecified -> neutral


def test_normalise_category():
    assert normalize_category("Scheduled Caste") == "SC"
    assert normalize_category("Scheduled Tribe") == "ST"
    assert normalize_category("Other Backward Classes") == "OBC"
    assert normalize_category("OBC-NCL") == "OBC"
    assert normalize_category("Economically Weaker Section") == "EWS"
    assert normalize_category("General") == "General"
    assert normalize_category("Any category") == "all"


def test_normalise_state_and_level():
    assert normalize_state("TS") == "Telangana"
    assert normalize_state("Telangana State") == "Telangana"
    assert normalize_state("UP") == "Uttar Pradesh"
    assert normalize_state("Orissa") == "Odisha"
    assert normalize_state("All India") == "all"
    assert normalize_state("Pan India") == "all"
    assert normalize_level("Undergraduate") == "UG" and normalize_level("Degree") == "UG"
    assert normalize_level("Post Matric") == "all"
    assert course_stream("MBBS") == "medicine" and course_stream("B.A.", "History") == "arts"
    assert course_stream("B.Tech", "CSE") == "engineering"


def test_parse_years():
    from matcher import parse_years
    assert parse_years("1, 2") == {1, 2}
    assert parse_years("First year (2nd year lateral)") == {1, 2}
    assert parse_years("1st year") == {1} and parse_years("Final year") == {4}
    assert parse_years("All years") == set() and parse_years("") == set()


def test_parse_money_and_percent():
    assert parse_money("₹2.5 lakh") == 250_000
    assert parse_money("Rs. 8 lakh per annum") == 800_000
    assert parse_money("Rs 3,20,000 per annum") == 320_000
    assert parse_money("8,00,000") == 800_000
    assert parse_money(450000) == 450_000
    assert parse_money("not stated") is None


def test_parse_deadline_formats():
    for raw in ("31 Oct 2026", "2026-10-31", "October 31, 2026", "31/10/2026", "Last date: 31st October 2026"):
        d = parse_deadline(raw, TODAY)
        assert d["date"] == date(2026, 10, 31), (raw, d)
        assert d["days_left"] == 16 and not d["closed"]
    assert parse_deadline("Rolling", TODAY)["rolling"] is True
    assert parse_deadline("Closed", TODAY)["closed"] is True
    assert parse_deadline("01/09/2026", TODAY)["closed"] is True
    assert parse_deadline("", TODAY)["date"] is None and parse_deadline("garbage!!", TODAY)["date"] is None


def test_pragati_extraction_matches_telangana_girl_but_blocks_boy():
    m = score(TELANGANA_GIRL, PRAGATI_EXTRACTION, TODAY)
    assert not m.blockers, m.blockers
    assert m.verdict in ("Likely eligible", "Possibly eligible"), m
    assert any("female" in r for r in m.reasons) and any("income" in r.lower() for r in m.reasons)
    boy = score(BIHAR_BOY, PRAGATI_EXTRACTION, TODAY)
    assert boy.verdict == "Not eligible" and any("female" in b for b in boy.blockers), boy
    assert boy.score <= 25


def test_kotak_extraction_income_and_marks_rules():
    m = score(MAHA_MBBS, KOTAK_EXTRACTION, TODAY)           # year 3, income 2.5L, 12th 91%
    assert any("year" in b for b in m.blockers), m.blockers  # first-year only
    assert any("91" in r and "85" in r for r in m.reasons), m.reasons
    rich = Profile.from_dict({**SAMPLE_STUDENTS["telangana_sc_btech"], "family_income": "₹5 lakh", "year": 1, "marks_12": 80})
    m2 = score(rich, KOTAK_EXTRACTION, TODAY)
    assert any("above" in b for b in m2.blockers) and any("below" in b for b in m2.blockers), m2.blockers


def test_unknown_profile_fields_are_neutral_cautions():
    p = Profile.from_dict({"state": "Telangana", "course": "B.Tech"})   # no gender, income, category
    m = score(p, PRAGATI_EXTRACTION, TODAY)
    assert not m.blockers
    assert any("add your gender" in c for c in m.cautions) and any("income" in c for c in m.cautions)
    assert m.verdict == "Possibly eligible", m


def test_minority_pwd_single_girl_flags():
    schemes = {s["name"]: s for s in sample_schemes()}
    minority = schemes["Post-Matric Scholarship for Minority Communities"]
    pwd = schemes["Post-Matric Scholarship for Students with Disabilities"]
    assert any("minority" in b.lower() for b in score(TELANGANA_GIRL, minority, TODAY).blockers)
    yes = Profile.from_dict({**SAMPLE_STUDENTS["bihar_obc_ba"], "minority": True, "pwd": True, "family_income": 150000})
    assert not score(yes, minority, TODAY).blockers and not score(yes, pwd, TODAY).blockers
    unknown = Profile.from_dict({**SAMPLE_STUDENTS["bihar_obc_ba"], "minority": None, "pwd": None})
    m = score(unknown, pwd, TODAY)
    assert not m.blockers and any("tick the box" in c for c in m.cautions)


def test_closed_schemes_sorted_last_and_deadline_labels():
    ranked = rank(TELANGANA_GIRL, sample_schemes())
    closed_idx = [i for i, r in enumerate(ranked) if r["match"]["deadline"]["closed"]]
    assert closed_idx and closed_idx[0] >= len(ranked) - len(closed_idx), closed_idx
    kotak = next(r for r in ranked if r["name"] == "Kotak Kanya Scholarship")
    assert "closes in" in kotak["match"]["deadline"]["label"]
    assert any("Closing soon" in c for c in kotak["match"]["cautions"])
    assert ranked[0]["match"]["verdict"] == "Likely eligible"


def test_three_sample_students_each_get_an_open_government_scheme():
    for key, data in SAMPLE_STUDENTS.items():
        p = Profile.from_dict(data)
        out = tf.discover(p)
        good = [r for r in out["results"] if r["source_type"] == "government"
                and r["match"]["verdict"] == "Likely eligible" and not r["match"]["deadline"]["closed"]]
        assert good, (key, [(r["name"], r["match"]["verdict"]) for r in out["results"]])
        assert all(r["documents_required"] for r in good)
        assert out["meta"]["sample"] is True


def test_build_queries_follow_course_and_state():
    qs = tf.build_queries(MAHA_MBBS)
    text = " | ".join(q["query"] for q in qs).lower()
    assert "mbbs" in text and "engineering" not in text, text
    gov = [q for q in qs if q["source_type"] == "government"]
    assert gov and all("gov.in" in q["include_domains"] for q in gov)
    assert any("mahadbt.maharashtra.gov.in" in q["include_domains"] for q in gov)
    priv = [q for q in qs if q["source_type"] == "private"]
    assert priv and all("facebook.com" in q["exclude_domains"] for q in priv)
    arts = " | ".join(q["query"] for q in tf.build_queries(BIHAR_BOY)).lower()
    assert "b.a." in arts and "history" in arts and "bihar" in arts and "obc" in arts
    assert len(qs) <= 6 and len({q["query"] for q in qs}) == len(qs)


def test_source_type_tagging_and_relevance_filter():
    assert tf.classify_domain("https://scholarships.gov.in/x") == "government"
    assert tf.classify_domain("https://telanganaepass.cgg.gov.in/") == "government"
    assert tf.classify_domain("https://pmsonline.bih.nic.in/") == "government"
    assert tf.classify_domain("https://kotakeducation.org/") == "private"
    assert tf.looks_like_scholarship("Rajarshi Shahu Maharaj Shikshan Shulkh Shishyavrutti")
    assert not tf.looks_like_scholarship("Buy cheap laptops online")


def test_document_checklist_dedupes_and_counts():
    ranked = rank(TELANGANA_GIRL, sample_schemes())
    checklist = document_checklist(ranked)
    names = [c["document"] for c in checklist]
    assert "Aadhaar card" in names and names.count("Aadhaar card") == 1
    aad = next(c for c in checklist if c["document"] == "Aadhaar card")
    assert aad["count"] >= 2 and len(aad["schemes"]) == aad["count"]
    assert checklist == sorted(checklist, key=lambda d: (-d["count"], d["document"]))
    assert not any("Reliance" in s for c in checklist for s in c["schemes"])      # closed scheme excluded


def test_ics_contains_only_open_deadlines():
    ranked = rank(TELANGANA_GIRL, sample_schemes())
    text, count = build_ics(ranked)
    assert text.startswith("BEGIN:VCALENDAR") and text.rstrip().endswith("END:VCALENDAR")
    assert count == text.count("BEGIN:VEVENT") and count >= 5
    assert "Reliance" not in text and "Sitaram" not in text      # closed + rolling have no date
    assert "TRIGGER:-P3D" in text


def test_output_schemas_use_only_basic_keywords():
    allowed = {"type", "properties", "items", "required"}

    def walk(node):
        if isinstance(node, dict):
            keys = set(node.keys()) - allowed
            if "type" in node:          # a schema node
                assert not keys, keys
            for v in node.values():
                walk(v)

    walk(tf.SCHOLARSHIP_SCHEMA)
    walk(tf.PREFILL_SCHEMA)
    assert set(tf.PREFILL_SCHEMA["properties"]) == {"filled", "needs_manual_input", "stopped_before"}


def test_prefill_goal_forbids_submit_and_omits_sensitive_ids():
    fields = tf.prefill_fields(TELANGANA_GIRL)
    goal = tf.prefill_goal(fields, "AICTE Pragati")
    for word in ("Never click Submit", "OTP", "captcha", "never upload a file", "STOP and report"):
        assert word in goal, word
    labels = {f["field"] for f in fields}
    assert "Full name" in labels and "Category" in labels
    assert not any(k in labels for k in ("Aadhaar", "Bank", "Password"))


def test_mock_discover_event_sequence():
    events = list(mock_discover_events(TELANGANA_GIRL, delay=0))
    stages = [e["stage"] for e in events]
    assert stages[:3] == ["searching", "found", "kept"] and stages[-1] == "ranked"
    extracting = [e for e in events if e["stage"] == "extracting"]
    assert len(extracting) == len(sample_schemes()) and all("scheme" in e and "match" in e["scheme"] for e in extracting)
    assert extracting[-1]["done"] == extracting[-1]["total"]
    final = events[-1]
    assert final["meta"]["sample"] and final["checklist"] and len(final["results"]) == len(sample_schemes())


def test_mock_prefill_stream_has_streaming_url_and_result_shape():
    events = list(mock_prefill_events(tf.prefill_fields(TELANGANA_GIRL), "/demo-form", delay=0))
    types = [e["type"] for e in events]
    assert types[0] == "STARTED" and types[1] == "STREAMING_URL" and types[-1] == "COMPLETE"
    assert events[1]["streaming_url"].startswith("/demo-form")
    res = events[-1]["result"]
    assert set(res) == {"filled", "needs_manual_input", "stopped_before"}
    assert res["filled"] and res["needs_manual_input"] and "Submit" in res["stopped_before"]


def test_replay_record_and_play_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "snap.json")
        recorded = list(replay.record(mock_discover_events(TELANGANA_GIRL, delay=0), path, recorded_from="test"))
        assert replay.available(path)
        played = list(replay.play(path, speed=1000))
        assert [e["stage"] for e in played] == [e["stage"] for e in recorded]
        assert played[-1]["meta"]["mode"] == "replay" and played[-1]["meta"]["recorded_from"] == "test"
        assert played[-1]["meta"]["sample"] is True


def test_gated_agent_config_fallback():
    """max_steps is a gated beta feature on some accounts; the client must retry without it, once."""
    tf._GATED_FIELDS_OK = None
    calls = []

    def fake(cfg):
        calls.append(cfg.model_dump(exclude_none=True))
        if len(calls) == 1:
            raise tf.__class__ if False else PermissionError("Your account is not enabled for custom max steps yet. Join the beta program at /beta")
        return "ok"

    assert tf.call_with_config_fallback(fake, "strict", 60, 300) == "ok"
    assert calls[0] == {"mode": "strict", "max_steps": 60, "max_duration_seconds": 300}
    assert calls[1] == {"mode": "strict"} and tf._GATED_FIELDS_OK is False
    assert tf.agent_config("strict", 60, 300).model_dump(exclude_none=True) == {"mode": "strict"}   # remembered
    tf._GATED_FIELDS_OK = None
    try:
        tf.call_with_config_fallback(lambda cfg: (_ for _ in ()).throw(RuntimeError("other error")), "strict", 60, 300)
        assert False, "unrelated errors must propagate"
    except RuntimeError:
        pass
    tf._GATED_FIELDS_OK = None


def test_gated_fallback_retries_in_every_parallel_thread():
    """Six parallel extractions all get the gated error at once; each must retry, not just the first."""
    import concurrent.futures as cf
    import threading
    tf._GATED_FIELDS_OK = None
    gate = threading.Barrier(6)
    attempts = []

    def fake(cfg):
        d = cfg.model_dump(exclude_none=True)
        attempts.append(d)
        if "max_steps" in d:
            gate.wait(timeout=5)          # make all six fail simultaneously
            raise PermissionError("Your account is not enabled for custom max steps yet.")
        return "ok"

    with cf.ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: tf.call_with_config_fallback(fake, "default", 40, 240), range(6)))
    assert results == ["ok"] * 6, results
    assert sum(1 for a in attempts if "max_steps" in a) == 6 and sum(1 for a in attempts if a == {"mode": "default"}) == 6
    tf._GATED_FIELDS_OK = None


def test_agent_budget_prefers_js_only_then_government():
    import cache as _cache
    cands = [{"url": "https://kotak.org/a", "title": "Kotak scholarship", "snippet": "", "position": 1, "source_type": "private"},
             {"url": "https://scholarships.gov.in/b", "title": "NSP scholarship", "snippet": "", "position": 2, "source_type": "government"},
             {"url": "https://ts.gov.in/c", "title": "ePASS scholarship", "snippet": "", "position": 3, "source_type": "government"}]
    long = "scholarship " * 200
    fake = {"results": [{"url": cands[0]["url"], "title": "Kotak scholarship", "text": long},
                        {"url": cands[1]["url"], "title": "NSP scholarship", "text": long}],
            "errors": [{"url": cands[2]["url"], "error": "timeout"}]}
    orig = _cache.cached
    _cache.cached = lambda ns, m, producer: (fake, True)
    try:
        kept = tf.fetch_filter(cands)
    finally:
        _cache.cached = orig
    assert [k["url"] for k in kept] == [cands[2]["url"], cands[1]["url"], cands[0]["url"]]
    assert kept[0]["needs_agent"] and not kept[1]["needs_agent"]


def test_profile_from_dict_is_forgiving():
    p = Profile.from_dict({"family_income": "2,50,000", "marks_12": "88%", "year": "2", "minority": "yes", "pwd": "no",
                           "state": "TS"})
    assert p.family_income == 250_000 and p.marks_12 == 88 and p.year == 2
    assert p.minority is True and p.pwd is False and p.n_state == "Telangana" and p.n_domicile == "Telangana"


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]

if __name__ == "__main__":
    failed = 0
    for t in TESTS:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL  {t.__name__}")
            traceback.print_exc()
    print(f"\n{len(TESTS) - failed}/{len(TESTS)} tests passed")
    sys.exit(1 if failed else 0)
