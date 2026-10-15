# 2-minute demo recording script

Record with OBS or Loom at 1440×900, browser zoom 110%, sound on. Keep the cursor slow. Say the bold lines.

**Before recording**

```bash
# option A — genuine live run (needs key, costs ~TOP_K agent credits per search)
TINYFISH_API_KEY=... PUBLIC_BASE_URL=https://<your-app>.onrender.com uvicorn backend.main:app --port 8000
# option B — replay of a recorded live run (safe on venue Wi-Fi; record it first: python scripts/record_replay.py)
DEMO_REPLAY=1 uvicorn backend.main:app --port 8000
```

Open `http://localhost:8000` (or the deployed URL). Check the header pill says **Live · TinyFish** or **Replay**. Close other tabs.

| Time | Do | Say |
|---|---|---|
| 0:00 | Show the header. | **"Every year crores of rupees in scholarships go unclaimed. Students never find them, miss the deadline, or give up on the form. Scholarship Navigator fixes all three, with TinyFish doing the reading."** |
| 0:12 | Click **"Priya · Telangana · SC · B.Tech yr 2"**. Scroll slowly through the 3 sections. | "A student describes themselves once: state, category, course, marks, income. Minority, disability and single-girl-child are separate flags because real rules treat them separately. Nothing here is stored." |
| 0:30 | Click **Find my scholarships**. Point at the step tracker as it moves. | "TinyFish **Search** runs two query sets, one restricted to gov.in, nic.in and the Telangana ePASS portal, one for CSR foundations. **Fetch** renders every page and keeps the scholarship ones. Pages that come back empty, the JavaScript-only government portals, are routed to the **Agent**, a real browser." |
| 0:50 | Cards appear one by one. Hover the first card's ✓ / ✗ / ⚠ lines. | "Each Agent run returns a strict JSON schema: amount, deadline, eligibility, documents. Our matcher is rule-based and explainable: green ticks are why you qualify, red crosses are hard blockers, yellow is what you must verify. Closed schemes drop to the bottom." |
| 1:05 | Tick **Government only**, then untick. Click **Add deadlines to calendar**. | "Filters, and one click puts every open deadline in your calendar with a 3-day reminder." |
| 1:15 | Scroll to **Documents to collect**. | "One combined checklist, de-duplicated across every scheme you are likely eligible for, with which schemes need each document." |
| 1:25 | Scroll to **Pre-fill**. Choose **Practice replica form**, tick consent, click **Start pre-fill**. | "Now the part only a real browser agent can do. We hand the agent the form and the profile with strict rules: never submit, never enter OTPs, IDs, bank numbers, never upload. Watch the live browser." |
| 1:40 | Let the iframe show fields turning green. Point to the log. | "Strict mode, max 60 steps. Real government portals demand login and OTP first, so there the agent correctly stops early. That's the point: it does the typing, the student stays in control." |
| 1:52 | Result panel: **Filled for you / You still need to do**. Point at "stopped before: Submit". | **"Filled for you. What you still need to do. And it stopped before Submit, every time. Scholarship Navigator, Team Twin Paradox, powered by TinyFish."** |

**If anything fails live:** the UI falls back to sample data automatically and says so in a yellow banner. Keep talking; switch to the replay tab you opened beforehand.

**Shots to keep:** the tracker mid-run, a card with ✓/✗/⚠, the checklist, the iframe with green fields, the final two-column panel, and the `/demo-form/submit` BLOCKED page (click Final Submit yourself at the end if you want to prove the guard).
