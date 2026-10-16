# Changelog

## Phase 0 — scaffold (the "working prototype" this plan assumed did not exist in the repo, so it was built)
- FastAPI backend (`/api/health`, `/api/discover`, `/api/prefill`), `tinyfish_client.py` holding every TinyFish call
  (Search → Fetch filter → parallel Agent extraction → Agent pre-fill), rule-based `matcher.py`, labelled `mock_data.py`.
- Single-file vanilla-JS frontend; 22 offline tests in `backend/test_pipeline.py` (includes Pragati and Kotak Kanya extraction fixtures).
- SDK shapes verified against the installed `tinyfish 0.9.0` source, not guessed.

## Phase 1 — prove the key works
- `backend/smoke_test.py`: fails clearly without `TINYFISH_API_KEY`; one Search (`location="IN"`) + one Agent run with
  `SCHOLARSHIP_SCHEMA`; saves `evidence/smoke_<timestamp>.json`. README documents getting a key at agent.tinyfish.ai/api-keys.
- Not yet executed with a real key in this environment (no key available) — run it once before the deck is final.

## Phase 2 — harden the core flow
- Queries built from the real course/branch/level/state/category (no more hard-coded "engineering"); dedicated government
  query set with `include_domains` (gov.in, nic.in, scholarships.gov.in, myscheme.gov.in + the student's state portal);
  results tagged `source_type` government/private and shown as badges.
- Synonym normalisation before matching: gender (Girls/Women→female), category (Scheduled Caste→SC, OBC-NCL→OBC, EWS…),
  states and abbreviations (TS→Telangana, UP→Uttar Pradesh, Orissa→Odisha), course levels, streams, ordinal years. Tests for each.
- Profile extended: domicile state, minority flag, PwD, 10th/12th %, institution type, single girl child. Unknown = neutral + caution.
- Fetch batches over all candidates (10 per call); thin/JS-only pages flagged `needs_agent` and prioritised for the Agent.
- `/api/discover/stream` (SSE): searching → found N → kept M → extracting k/N (one event per finished Agent run, with the
  scheme already scored) → ranked. Live step tracker in the UI; cards appear as they arrive. Plain JSON `/api/discover` kept for tests.
- Disk cache (`.cache/`, sha-256 keys, 24 h TTL) for Search, Fetch and Agent; `DEMO_RECORD=1` / `DEMO_REPLAY=1` with
  `scripts/record_replay.py`. The shipped snapshot was recorded from the sample pipeline (no key here) — re-record live.
- Results: deadline "closes in N days" (red ≤ 14), ✓/✗/⚠ reasons, combined de-duplicated document checklist,
  `.ics` export with 3-day alarms, filters (likely eligible / government / closing soon). Optional narrower second Agent
  goal for thin extractions behind `RETRY_THIN_EXTRACTION=1`.

## Phase 3 — pre-fill demo, UI, assets
- `/demo-form`: NSP-style practice replica with a loud "not a government site" banner; POST → **403 BLOCKED** page.
  In mock mode the replica simulates the agent typing so the same UI path is exercised without a key.
- Pre-fill moved to `client.agent.stream(...)` with `browser_profile="stealth"`, `AgentConfig(mode="strict", max_steps=60,
  max_duration_seconds=300)`, `PREFILL_SCHEMA` → `{filled, needs_manual_input, stopped_before}`; non-200, timeouts and a
  missing `STREAMING_URL` handled; mock stream emits `STREAMING_URL` too.
- UI polish: 3-section form, sample students, mobile layout, one accent colour, Hindi toggle for static text.
- `scripts/capture.py` (Playwright) → `deck/assets/01…08` at 1440×900 and 390×844; `docs/DEMO_SCRIPT.md`;
  `render.yaml`, `Procfile`, `railway.json` for a public URL (TinyFish's browser cannot reach localhost).

## Phase 4 — deck
- `deck/DECK.md` (12 slides, every number sourced or marked `[SOURCE NEEDED]` / measured), `deck/architecture.mmd` + rendered PNG.

## Live verification (2026-10-16, real TinyFish key)
- Smoke test passed: Search returned 7 real NSP results in 1.2 s; Agent extracted the AICTE Pragati page
  (status COMPLETED, 10 steps, 487 s, stealth profile) → `evidence/smoke_20261016_070313.json`.
- **TinyFish behaved differently from the brief:** `AgentConfig(max_steps=…)` is a gated beta feature; the API
  answered `PermissionDeniedError: Your account is not enabled for custom max steps yet`. The client now tries the
  full config once and falls back to `AgentConfig(mode=…)` only, remembering the answer for the process. Safety
  then rests on strict mode plus the never-submit goal, and the practice form's 403 guard. Test added.
- Agent runs on this account take ~8 min each with the stealth profile, so discovery runs all TOP_K extractions in
  parallel (`EXTRACT_WORKERS=6`) and the replay snapshot caps inter-event gaps at 8 s.

## Phase 5 — polish
- README final pass, `SUBMISSION_CHECKLIST.md`, edge cases (no results, all closed, TinyFish error → friendly message + sample fallback).
