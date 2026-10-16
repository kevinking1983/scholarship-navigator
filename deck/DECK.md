# Scholarship Navigator — deck content (12 slides)

Format per slide: **headline** · bullets · *speaker note* · screenshot. Numbers: every figure is cited or measured (slide 10 numbers come from `evidence/live_bench.json`); anything still unverified is marked `[SOURCE NEEDED]`. Do not present an unsourced number.

---

## 1 · Title
**Scholarship Navigator** — find every scheme you qualify for, and let an agent fill the form.
- Team Twin Paradox · HackIIITD 2026 (Tech Council, IIIT Delhi)
- **Powered by TinyFish** (Search · Fetch · Agent)
- Live: `[FILL IN live URL]` · Code: `[FILL IN GitHub URL]`

*Note: One line, then move. "We built the thing a first-year student from a small town wishes existed in August."*
Image: `deck/assets/03-results.png` (cropped to the top 2 cards) as a soft background.

## 2 · Team Details
**Team Twin Paradox**
- `[FILL IN name]` — role (backend / TinyFish integration) — `[college, year]` — `[email]`
- `[FILL IN name]` — role (frontend / demo) — …
- `[FILL IN name]` — role (research / deck) — …
- Contact: `[FILL IN]`

*Note: 10 seconds. Who did what, in one phrase each.*

## 3 · Problem Statement
**Eligible students don't get the money that already exists for them.**
- Scholarship information is scattered across the National Scholarship Portal, myScheme, 30+ state portals (Telangana ePASS, MahaDBT, PMS Bihar…), and hundreds of CSR/trust sites, each with its own layout and login.
- Many government portals are JavaScript-heavy and change often; ordinary scrapers and aggregators can't read them, so listings go stale.
- Eligibility is a maze of overlapping rules: category, income cap, domicile vs. study state, minority, disability, marks, year, institution type.
- Deadlines fall in the same few weeks (Sep–Dec) and are missed; forms are long, repetitive, and abandoned.
- Scale of the loss: `[SOURCE NEEDED — e.g. NSP dashboard applications vs. disbursed; Lok Sabha replies on unspent scholarship funds; Ministry of Social Justice / Minority Affairs annual reports; press coverage of unclaimed scholarships]`.
- One real student story: `[FILL IN — a classmate who found out about a scheme after the deadline]`.

*Note: Put the loss in human terms. If you cannot verify a rupee figure by the deadline, say "crores" qualitatively and cite the NSP dashboard page you looked at.*
Image: a collage of 3 portal screenshots (NSP, ePASS, a CSR page) with different layouts — `[FILL IN]`.

## 4 · Why existing options fail
**Nothing out there checks *your* eligibility or helps you apply.**
- Aggregator sites: ad-heavy, stale, copy-pasted eligibility text, no personalisation.
- NSP lists central and some state schemes, but not CSR/trust scholarships; state portals list only their own.
- Nothing tells a student *why* they qualify (or don't), and nothing touches the form itself.
- Chat-bots that answer from training data hallucinate deadlines; they don't read the live page.

*Note: "The missing piece is a reader that can open a real browser on a real portal, today."*

## 5 · Proposed Solution
**Describe once → discover → understand → rank → pre-fill.**
- One profile (state, category, course, marks, income, minority/PwD flags) — never stored.
- TinyFish **Search** finds candidate pages on government and open web; **Fetch** filters them; **Agent** reads each page in a real browser and returns structured JSON.
- Rule-based matcher explains every verdict: ✓ reasons, ✗ blockers, ⚠ cautions; "closes in N days"; combined document checklist; calendar export.
- A TinyFish agent **pre-fills the form and stops before Submit** — the student reviews and submits.

*Note: Click through the hero screenshot: card → reasons → checklist → pre-fill panel.*
Image: `deck/assets/03-results.png` (hero).

## 6 · Target Users
**Primary: students who have the most to gain and the least help.**
- UG / PG / diploma students, especially first-generation, rural, SC/ST/OBC/EWS, minority, PwD, and girls in STEM (e.g. AICTE Pragati).
- Class 11–12 students entering the post-matric system for the first time.
- **Secondary:** college scholarship cells and NSP nodal officers (run it for a whole batch), NGOs and school counsellors, hostels and coaching centres.

*Note: "Our sample students are Priya (Telangana, SC, B.Tech), Rahul (Bihar, OBC, B.A.) and Sneha (Maharashtra, General, MBBS). Each gets a different government scheme first."*
Image: `deck/assets/01-profile-mobile.png` next to `01-profile.png` (mobile-first).

## 7 · Technical Architecture
**Browser UI → FastAPI → TinyFish Search → Fetch → Agent (parallel) → Matcher → results; Agent stream → live browser → pre-fill (stops at Submit); cache layer.**
- Discovery is streamed (SSE): the UI shows *searching → found N → kept M → extracting k/N → ranked* and cards appear as each Agent run finishes.
- All TinyFish calls live in one module (`tinyfish_client.py`); the matcher is pure Python and free.
- Disk cache (SHA-256 keys, 24 h) in front of Search, Fetch and Agent; replay mode for demos; sample mode when no key.

*Note: Walk the diagram left to right, then the dashed return path for the live browser events.*
Image: `deck/architecture.png`.

## 8 · Tech Stack
**Deliberately small.**
- Python 3.12 · FastAPI · Uvicorn · Server-Sent Events
- TinyFish Python SDK 0.9 (`search.query`, `fetch.get_contents`, `agent.run`, `agent.stream`)
- One HTML file, vanilla JS, system fonts, no build step, EN/हिंदी toggle
- Playwright (screenshots), Render/Railway free tier (public URL so the cloud browser can reach the practice form)
- No database, no accounts, no other LLM provider

*Note: "Everything that reads the web is TinyFish. Everything that decides is explainable rules."*

## 9 · How We Integrate the TinyFish API  ★ most important slide
**Five calls, three products, one safety contract.**

| Step | API | Cost | Role |
|---|---|---|---|
| Discover | Search (`location="IN"`, `include_domains=gov.in,nic.in,scholarships.gov.in,myscheme.gov.in,<state portal>`) | free | government set + open-web set, social sites excluded |
| Filter | Fetch (`format="markdown"`, batches of 10) | free | keep scholarship pages; thin/JS-only pages → `needs_agent` |
| Extract | Agent `run` + `output_schema` (parallel ×4, `stealth` on `.gov.in`) | credits | amount, deadline, eligibility, documents as strict JSON |
| Match | — | free | explainable rules |
| Apply | Agent `stream` (`strict`, `max_steps=60`, `max_duration_seconds=300`) | credits | live `STREAMING_URL`, progress, `{filled, needs_manual_input, stopped_before}` |

- **Why a real browser:** JS-only `.gov.in` pages come back empty from Fetch; those are exactly the ones routed first to the Agent.
- **Safety contract in the goal and in config:** never Submit/Pay, no accounts, no OTP/captcha/passwords, no uploads, no Aadhaar/bank numbers; stop and report. The hosted practice form returns **403 BLOCKED** on any POST.
- **Evidence:** `evidence/smoke_20261016_070313.json` — Search: 7 real NSP results in 1.2 s; Agent: AICTE Pragati page extracted, status COMPLETED, 10 steps, 487 s, with amount (₹50,000/yr), ₹8 lakh income cap, 10 documents.
- **Challenges we hit:** `max_steps` / `max_duration_seconds` turned out to be a gated beta feature (API: "not enabled for custom max steps") → client retries once without them, safety stays in strict mode + the never-submit goal + the 403 guard; stealth Agent runs take ~8 min each on our account → all extractions run in parallel and results stream in as each finishes; no India proxy (US/GB/CA/DE/FR/JP/AU) so some portals block cloud browsers → expected failures with snippet fallback; login/OTP walls → agent stops early by design; `output_schema` accepts only basic JSON-schema keywords.

*Note: Spend 40 seconds here. Show the evidence JSON. Say "free, free, credits, free, credits".*
Image: `deck/assets/05-prefill-live.png` + a screenshot of the evidence JSON.

## 10 · Scalability, Feasibility & Use Case
**Cheap per student, because reading is cached and matching is free.**
- Search and Fetch are free; only Agent extraction and pre-fill cost credits. Extraction is cached 24 h and capped (`TOP_K=6`); a nightly re-crawl of the top ~200 scheme pages serves every student from cache.
- **Measured (2026-10-16, stealth profile, TOP_K=6, 6 parallel Agent runs):** discovery for a fresh profile took 422 s (Telangana), 905 s (Bihar), 672 s (Maharashtra) — average 11 min, of which Search + Fetch ≈ 80 s and the rest is Agent reading; a repeat/cached profile takes < 1 s with 0 Agent runs.
- **Measured Agent cost:** 21 extraction runs averaged 8.0 steps and 2.0 min each. At the published rates (Agent $0.016/step, browser $0.002/min, Search & Fetch $0 — from the wallet API) that is ≈ **$0.79 per fresh student profile** and $0 for every cached repeat; a nightly re-crawl of ~200 scheme pages ≈ $26/night serves a whole college from cache.
- Matching is instant and deterministic; adding a state = adding its portal domain and synonyms (minutes, no retraining).
- Weekly deadline-watch job: re-extract deadlines, push `.ics`/notifications.
- Risks → mitigations: portal layout changes (Agent reads semantically, not by selector); login walls (stop early, hand off); no India proxy (stealth profile, snippet fallback); venue Wi-Fi (replay mode); credit spikes (cap + cache).
- Privacy: profiles never persisted; DPDP Act 2023-aligned by design.

*Note: All numbers above are measured (see `evidence/live_bench.json`); say so on stage. Live runs also caught two real bugs (parallel fallback race, query-string de-dup) — good 'challenges' material.*
Image: `deck/assets/02-progress.png`.

## 11 · Use Cases & Impact
**One student, one batch, one district.**
- Individual: find, verify, collect documents, pre-fill, submit — in one sitting.
- College scholarship cell: run the whole first-year batch through it; checklist per student; calendar for the office.
- NGOs / counsellors in rural districts: works on a phone; Hindi toggle today, regional languages next.
- Next: WhatsApp bot front-end, regional languages, DigiLocker document check, deadline reminders.

*Note: "Impact is not the app; it is a form that gets submitted on time."*
Image: `deck/assets/04-checklist.png`.

## 12 · MVP / Prototype
**Working today.**
- Screenshots: `01-profile.png` · `02-progress.png` · `03-results.png` · `06-prefill-result.png` (+ `08-blocked.png` as proof of the guard)
- Demo video: `[FILL IN unlisted link]` · Live URL: `[FILL IN]` · GitHub: `[FILL IN]`
- Works now: streamed discovery with government/private tagging, explainable ranking, checklist, calendar export, agent pre-fill on a public practice form, sample/replay modes, 26 offline tests; verified live for 3 student profiles — each returned at least one real, likely-eligible government scheme (Telangana PMS-SC, Bihar BC/EBC post-matric, Maharashtra Rajarshi Shahu fee reimbursement on MahaDBT).
- Next: one verified public CSR form in the demo, nightly re-crawl cache, WhatsApp front-end.

*Note: End on the BLOCKED page: "and it never submits."*
