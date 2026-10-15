# Unstop submission checklist — Scholarship Navigator

Deadline: **[FILL IN DATE/TIME]** · target: everything below done **24 hours before**.

## Must-haves (organiser rules)
- [ ] TinyFish API used and **visibly central**: named on the title slide and on slide 9 (integration), shown in the demo video.
- [ ] Deck covers, in order: Team Details · Problem Statement · Proposed Solution · Target Users · Technical Architecture & Stack · TinyFish Integration · Scalability, Feasibility & Use Case · MVP/Prototype (screenshots + video link). (`deck/DECK.md` is in that order.)

## Evidence to generate with a real key (not possible without one)
- [ ] `python backend/smoke_test.py` → `evidence/smoke_<ts>.json` exists; paste the Search + Agent result on slide 9.
- [ ] `python scripts/record_replay.py` with the key → `demo/replay_snapshot.json` is a **genuine** live run (`recorded_from: "live"`); commit it.
- [ ] Run the live demo end-to-end 3× for the 3 sample students; record average discover time and credits per run → slide 10 (replace `[MEASURED]`).
- [ ] Re-run `python scripts/capture.py --mode replay` so screenshots show real extracted data (no *Sample* badge).
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
