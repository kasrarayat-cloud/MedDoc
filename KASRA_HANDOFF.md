# Pilot launch handoff
*One page. Read on your phone. Act on it.*

---

## A. What's live right now

- **app.quillmd.com** — doctor surface (record, transcribe, sign, export)
- **pro.quillmd.com** — MedDoc Pro CRM (charts, patients, appointments)
- **admin.quillmd.com** — your admin dashboard (you, qa-audit, anyone with SUPER_ADMIN)
- **main HEAD**: `b77e55d` (PR #73 — pilot launch announcement)
- **Today's smoke proof**: visit `cmofzxpoi004y01nzrpu8n01d` walked SIGNED in 3:29 by ash@meddoc.com — Deepgram + 10 Anthropic layers + OpenAI embed + Resend email all billed (12 api_usage_events rows). The pipeline is verified working with real PHI, on the deployed code, today.

---

## B. The three announcement variants — pick + post

### A) Twitter / X (post here for reach)

> QuillMD is in pilot. HIPAA-compliant AI medical scribe — record the visit, the SOAP note writes itself, you sign it. Admin dashboard with full audit trail.
>
> Open to 5 doctors. Reply if you spend more than an hour a day on charting.

### B) LinkedIn (post here for clinical/professional credibility)

Doctors spend two hours on charting for every hour of patient care. That's what QuillMD is built to fix.

QuillMD records the visit (audio in the room or dictation after), transcribes it with medical-grade speech recognition, and generates a structured SOAP note the doctor reviews and signs. Diagnosis codes, prescriptions, referrals — all drafted from the conversation, all editable, all auditable.

The hard parts of "AI in medicine" are the parts you don't see: HIPAA §164.312 audit controls on every PHI access, threat detection on the export surface, encrypted-at-rest storage on the roadmap, single-session enforcement, no training on your data. The product passes its own internal audit before any patient touches it.

Today we're opening a 5-doctor pilot. Looking for clinicians who:
- Spend more than an hour a day on documentation,
- Want to evaluate honestly (find what's wrong, not just what's nice),
- Are comfortable with a 30-day commitment.

Reply or DM if that's you. Tehran-based, global-friendly.

— Kasra

### C) Long-form (post here as the anchor people link to)

~520 words covering the why, the architecture, HIPAA posture, pilot scope, and feedback loop. **Full text in `LAUNCH_ANNOUNCEMENT.md` (Variant C)**. Best home: a personal blog, Substack, or a `quillmd.com/pilot` landing page that A and B can link back to.

---

## C. Where to send people who reply

You don't have a form yet. Pick one of these for the first few replies:

1. **DMs only** (simplest) — reply with your email, take the conversation private.
2. **A simple Google Form** (10 minutes to make) — name, practice name, specialty, average daily charting time, current EHR. Embed the form link in your replies.
3. **Email alias** — `pilot@quillmd.com` if your DNS is on Resend already; forwards to you.

**What to collect from each pilot intake**:
- Name + practice name
- Specialty
- Average daily charting time (sets the "is this person painful enough?" bar)
- Current EHR (Epic, Athena, eClinicalWorks, etc — tells you whether your PDF/DOCX export integrates with their workflow)
- One sentence on why they want in (not why they need it — anyone can articulate that — but why specifically YOUR product)

**Pilot length**: suggest 30 days. Long enough to use it for real, short enough that a doctor can commit. After 30 days, decide together whether to keep going + start paying.

---

## D. First-week monitoring routine (5 min/day)

Open `https://admin.quillmd.com` first thing every morning. Look at:

1. **Top of Overview page**:
   - Threats banner — should be GREEN ("No active threats"). If amber/red, click View all → investigate before doing anything else.
   - 4 service cards (Database, Redis, Object storage, External APIs) — all green dots.
   - HIPAA card — "3 open" badge. Should still be the 3 expected: `h8-h3-pilot-followup`, `h8-h4-pilot-followup`, `h9-meddoc-e2e-residual`. If a NEW finding appears, click in.

2. **Activity feed** (right side of Overview):
   - Should show real doctor traffic: LOGIN_SUCCESS, VISIT_SIGNED, EXPORT_PDF_DOWNLOADED, etc.
   - If it's ALL `ADMIN_API_ACCESS` from your own browsing, no doctor used it that day — follow up.
   - If you see clusters of LOGIN_FAILED with the same IP, that's the failed-login-burst detector firing — it'll also surface on Threats.

3. **/admin/usage**:
   - Set window to "24h"
   - Per-doctor spend — sanity-check it. A typical 10-visit day costs ~$0.50–1.50 per doctor at current Sonnet pricing. If you see $20/doctor, somebody hit retry 100 times on a long visit — investigate (or it's legit; the per-user cost-cap question is for the pilot wrap-up).

4. **/admin/users**:
   - Total count should match invited doctors + you + qa-audit + the seed users.
   - Suspended count should be 0 (unless you suspended someone for cause).

If anything is weird: pause new pilot signups, investigate before inviting more doctors. The point of starting at ≤5 is so you have headroom to debug without breaking 50 people's day.

---

## E. Emergency rollback (one-line summary per tier)

Full procedure in `LAUNCH_READINESS.md` Section D.

- **Tier 1** — single container hung: `docker compose restart <service-name>`. ~5 sec downtime, that container only.
- **Tier 2** — recent commit broke prod: `git checkout <previous-good-SHA>` + sequential rebuild (worker → transcribe-md → meddoc-pro). ~3-5 min downtime end-to-end.
- **Tier 3** — DB corrupted / data loss: stop dependent services → drop+recreate `meddoc` DB → `gunzip -c /backups/last/meddoc-latest.sql.gz | psql` → restart services. Tested in Phase 9 — restore loop works.

Worst case is Tier 3 and that's ~10 min recovery to last-midnight state. You'll lose at most 24h of doctor visits which sucks but is recoverable (re-record the audio if it still exists in MinIO; the audio bucket is separate from postgres and doesn't get cleared).

---

## Two things left

1. **Read this doc** + merge PR #74 if you're happy with it.
2. **Pick announcement variants + hit publish** on whichever platforms you want.

That's it. The system is alive and listening.
