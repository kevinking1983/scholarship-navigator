# Unstop submission checklist — Scholarship Navigator

Deadline: **[FILL IN DATE/TIME]** · target: everything below done **24 hours before**.

## Must-haves (organiser rules)
- [ ] TinyFish API used and **visibly central**: named on the title slide and on slide 9 (integration), shown in the demo video.
- [ ] Deck covers, in order: Team Details · Problem Statement · Proposed Solution · Target Users · Technical Architecture & Stack · TinyFish Integration · Scalability, Feasibility & Use Case · MVP/Prototype (screenshots + video link). (`deck/DECK.md` is in that order.)

## Evidence to generate with a real key (not possible without one)
- [x] `python backend/smoke_test.py` → `evidence/smoke_20261016_070313.json` (Search 7 results in 1.2 s; Agent COMPLETED, 10 steps, 487 s). Paste on slide 9.
- [x] `demo/replay_snapshot.json` is a genuine live run (`recorded_from: "live"`, 2026-10-16).
- [x] Live discovery run for all 3 sample students; timings in `evidence/live_bench.json` and on slide 10. Cost per fresh profile computed from the wallet API's published per-step/per-minute rates (slide 10).
- [x] Screenshots re-captured from the genuine replay (Agent-extracted badges, no *Sample*).
- [ ] Confirm one real public CSR form the agent can open without login; note any portal that blocked the cloud browser (good "challenges" material).

## Deck & video
- [ ] Deck built from `deck/DECK.md`, exported to **PDF**, size under Unstop's limit `[FILL IN limit]`.
- [ ] Every statistic has a citation or is marked measured; no `[SOURCE NEEDED]` left.
- [ ] `[FILL IN]` team details completed on slide 2 and in README.
- [ ] 2-minute video recorded per `docs/DEMO_SCRIPT.md`, uploaded **unlisted**, link opened in an incognito window.
- [ ] Live URL (Render/Railway/Fly) is up: `GET /api/health` → `"mode": "live"`; `/demo-form` loads publicly.

## Repo
- [ ] Repository is **public**; README pitch, screenshots, architecture image, setup, modes, deploy, TinyFish table, safety rules, team.
- [ ] `.env` is NOT committed; `.env.example` is.
- [ ] `python backend/test_pipeline.py` → all tests pass on a fresh clone.

## Final
- [ ] Submitted on Unstop ≥ 24 h early; confirmation screenshot saved.
