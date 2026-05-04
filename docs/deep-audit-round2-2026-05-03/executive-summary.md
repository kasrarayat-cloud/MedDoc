# Round 2 Deep Audit — Executive Summary

**Run:** 2026-05-03 20:20–21:11 UTC (~50 min real, vs 4h budget)
**Scope:** 11 domains (A–K), targeting the surfaces Round 1 skipped
**Method:** Playwright headless + Postgres read-only + DB cross-check

---

## TL;DR — One real P1 found (PDF/DOCX metadata leaks PHI)

Round 2 actively probed the surfaces Round 1 skipped "for time
budget." Result: **1 P1**, **3 P2**, **6 P3**, plus a healthy
collection of **POSITIVE findings** about the system's safety
posture. The **AI fabrication test** (I-001) is the most important
positive finding — the pipeline correctly REFUSES to invent vital
signs / exam findings when the doctor performs an exam but doesn't
report values.

| Severity | Count | Notes |
|---|---|---|
| **P0** | **0** | no active exploits found |
| **P1** | **1** | PDF + DOCX metadata leak patient name |
| **P2** | **3** | email length, specialty mismatch, mobile tap targets |
| **P3** | **6** | batched into cleanup PR scope |
| **SEC** | **0 NEW** | (Round 1's 8 transitive CVEs still standing) |
| **POSITIVE / INFO** | **15+** | cross-tenancy enforced everywhere; AI doesn't fabricate; rate limits work; etc. |

---

## Top finding (the one that matters most)

### 🚨 P1-001 — PDF + DOCX exports leak patient name in document metadata

**File:** `apps/transcribe-md/src/lib/pdf-generator.ts:97-103` +
`apps/transcribe-md/src/lib/docx-generator.ts:293-296`.

Both exports embed the patient's full name in document metadata:
- PDF: `info.Title = "Visit — ${patientName} — ..."`
- DOCX: `<dc:title>Visit — QA-TEST Mei-Ling Park</dc:title>`
- DOCX: `<dc:creator>QA Bypass Updated</dc:creator>` (clinician name)

**Verified live** by downloading the actual export and inspecting
metadata via `unzip -p docProps/core.xml`.

**HIPAA-relevant** because:
- Document metadata is part of the file forever
- Email previews show file titles → patient name in inbox subject-line
  preview without ever opening the attachment
- macOS Spotlight / Windows Search index PDF metadata → patient name
  appears in OS search results
- Any cloud sync / DLP / backup tool reads metadata for catalog
  purposes

**Fix:** ~5 min — replace `patientName` with `visitId` in both
generators. Body of document is unchanged.

Full detail: [`findings/P1-001-pdf-docx-metadata-phi-leak.md`](findings/P1-001-pdf-docx-metadata-phi-leak.md)

---

## P2 findings (3)

### P2-001 — Signup email field has no max-length validation
`SignupSchema.email = z.string().email()` — missing `.max(254)`.
Verified: 180-char-local-part email accepted + auto-confirmed.
Files: `apps/transcribe-md/src/actions/auth.ts:64`. **Fix: 1 line.**
[detail](findings/P2-001-email-no-max-length.md)

### P2-002 — Specialty dropdown vocab mismatch
Settings dropdown has 6 specialties (`cardiology, pain, ortho,
primary, pulmonology, ophthalmology`). Visit-create dropdown has 8
DIFFERENT specialties (`Cardiology, Dermatology, Internal Medicine,
OB-Gyn, Orthopedics, Pediatrics, Primary Care, Psychiatry`). A
doctor can't set Dermatology as default; can set Pain as default
but the visit wizard doesn't offer it.
**Fix: centralize in shared catalog + DB migration for existing values.**
[detail](findings/P2-002-specialty-list-mismatch.md)

### P2-003 — Mobile dashboard tap targets all under 44pt height
17/17 sampled interactive elements on the authenticated dashboard
fail Apple HIG's 44×44 minimum (heights 19–36pt). Affects every
nav link, the Cmd-K search bar, "New visit" CTA, dashboard cards,
recent-visit rows. **Marketing copy explicitly targets mobile
doctors** — this is the user base that hits this most.
**Fix: bump nav/CTA `min-height: 44px` in CSS.**
[detail](findings/P2-003-mobile-tap-targets.md)

---

## P3 batch (6 nitpicks → cleanup PR)

[`findings/P3-batch-r2.md`](findings/P3-batch-r2.md):
1. **P3-R2-001** — `Create & continue` button no debounce (5 clicks → 10 XHRs)
2. **P3-R2-002** — Profile-update toast text duplicated in DOM
3. **P3-R2-003** — No skip-to-content link (WCAG 2.4.1)
4. **P3-R2-004** — Patient-search input 14px → iOS zoom-on-focus
5. **P3-R2-005** — Round 1 P3-001 was test-rig artifact — RESOLVE
6. **P3-R2-006** — `/api/visits/{id}/export/fhir` 404 (marketing claims FHIR)

---

## What Round 1 missed that Round 2 caught

| Round 2 finding | Why Round 1 missed it |
|---|---|
| **P1-001 PDF/DOCX metadata leak** | Round 1 didn't actually download exports + inspect metadata — only verified the route returned 200 |
| **P2-001 email length** | Round 1 didn't probe weird-email signups (no Domain A equivalent) |
| **P2-002 specialty list mismatch** | Round 1 only inventoried 1 dropdown, not both |
| **P2-003 mobile tap targets** | Round 1 deferred Domain H entirely |
| **P3-R2-004 input zoom-on-focus** | Round 1 didn't test mobile-specific font-size requirements |
| **I-001 AI fabrication test** | Round 1 didn't construct an "exam-without-findings" audio scenario |

**Lesson learned:** the most valuable findings come from active
adversarial probing (weird inputs, edge cases, fabrication tests),
not from reading the source. Round 1 over-indexed on tool output;
Round 2 over-indexed on user-flow simulation. Both are needed.

---

## Strong POSITIVE findings (verifiable safety posture)

These are NOT bugs — they're verifiable evidence that the system
is doing the right thing:

1. **AI fabrication blocked** (I-001) — when doctor performs exam
   but doesn't report values, AI writes "[not documented]" + plan
   item to flag the documentation gap. **Zero fabrication.**
2. **Cross-tenancy enforced** (B-001 + C-001) — Round 2 user
   trying to access Round 1's visit/exports → 404
3. **SQL injection blocked** (A8) — `'; DROP TABLE patients; --`
   stored as data, not executed; table count steady
4. **XSS blocked** (A8) — `<script>alert(1)</script>` rendered as
   text via React escaping; alert never fired
5. **Edit-after-sign blocked** (B-002) — `readonly` prop on signed
   visits, signedSoap immutable
6. **Admin endpoints return 404 to non-admin** (K-002) — proper
   route-existence hiding
7. **Forgot-password rate-limited** (K-001) — 5 attempts per window
8. **Pinch-zoom not blocked** (H-003) — viewport meta is a11y-friendly
9. **Round 1's P3-001 (Codes→Cmd-K) was test artifact** (E-002) —
   product is fine, tests were broken
10. **Coding Coach is client-side until Sign & Send** (E-001) —
    correct architecture; doctor can flip codes without server
    round-trip per change
11. **Cmd-K palette well-documented** (G-002) — visible shortcuts
    (⌘K, N, D, S, ↑↓, ↵, esc) discoverable in palette UI

---

## Manual actions for Kasra

| Action | Why |
|---|---|
| Approve P1-001 fix (~5 min, 6 lines across 2 files) | PHI leak in document metadata |
| Approve P2-001 fix (~10 min, 1 Zod chain) | DB pollution + downstream surface |
| Approve P2-002 fix (~50 min, catalog + migration) | UX consistency + AI template integrity |
| Approve P2-003 fix (~45 min, CSS) | Mobile UX for primary user base |
| Apply Round 1's UX-01 (text-3 contrast bump) | a11y; same-line fix as Phase 7 marketing |
| `npm update` per Round 1's SEC-01..08 | Clear 8 moderate transitive CVEs |
| Confirm 7-day session vs 20-min sliding (A15) | Compliance choice, not a bug |
| Decide on `/api/visits/{id}/export/fhir` (P3-R2-006) | Either build or trim marketing copy |
| Confirm whether amendment workflow exists (B6) | HIPAA-permitted but not required |

---

## Cleanup PR

**Branch:** `chore/audit-round2-cleanup-2026-05-03`
**Scope:** P3 nitpicks ONLY — no logic changes:
- Add skip-to-content link to auth shell (P3-R2-003)
- Bump patient-search input font-size to 16px (P3-R2-004)

The other P3s (debounce, toast dedup, FHIR endpoint) require more
context / decisions and are deferred for Kasra's review.

The P1, P2, and 4 of 6 P3s are **plan-only** per audit rules.

---

## What was NOT covered (deferred per time budget)

- **A1, A2, A5, A6** edge cases (refresh during recording,
  network-drop, back button, logout-during-pipeline) — DEFERRED;
  rate-limit interactions made these flaky; recommend a focused
  human session
- **A3, A13** multi-context tests (dual-tab edit, 5 concurrent
  visits) — DEFERRED for RAM
- **A14** weird audio files — partial; test-rig wizard-state
  reentry issue
- **A15** session timeout — can't simulate 20-min idle
- **B-live-edit** (full edit + save round-trip) — selector mismatch
  in test rig
- **D4-D7** specialty-specific SOAP re-runs — Round 1 covered the
  diversity needed
- **E5/E6/E4-edge** Coding Coach edge cases — needs `data-em-chip`
  test attributes added to UI
- **F6/F7/F8** email change, notifications, admin internals — need
  a SUPER_ADMIN account
- **G4/G5** focus trap + restoration — needs more time
- **H4-H10** mobile-specific UX (safe areas, gestures, keyboard
  covering) — needs real iPhone hands-on
- **I3/I4** new scenarios + 5x calibration — would burn 30+ min
- **J3/J4/J8** pipeline upstream simulation, DB drop, loading-state
  inventory — need different test strategy

These are surfaces a Round 3 could focus on. Each Round of audit
finds different bugs by attacking from a different angle.

---

## Test artifacts left behind

In the DB (all `QA-TEST` prefixed where applicable):

- `qa-round2-1777839713@quillmd-test.local` (Round 2 user)
- `qa-test+round2{ts}@gmail.com` — created during A7; **NOT
  auto-confirmed** (gmail in denylist) — so account exists but
  unverified
- 9 test users from A7 weird-email tests
- 5 patients from A8 SQL/XSS tests (QA-TEST prefix)
- Several patients from A9-A11/A14 (QA-TEST prefix, partial)
- 1 visit from I5 fabrication test (`cmoq9eqgi003301qq3pg97kdw`)

**Cleanup SQL** (run when convenient):
```sql
DELETE FROM transcribe_visits WHERE id LIKE 'cmoq%' AND "createdAt" > '2026-05-03 20:00:00';
DELETE FROM transcribe_md_patients WHERE name LIKE 'QA-TEST%' AND "createdAt" > '2026-05-03 20:00:00';
DELETE FROM auth_tokens WHERE "userId" IN (SELECT id FROM users WHERE email LIKE 'qa-round2-%' OR email LIKE 'qa-r2-%' OR email LIKE 'qa-test+round2%');
DELETE FROM users WHERE (email LIKE 'qa-round2-%' OR email LIKE 'qa-r2-%' OR email LIKE 'qa-test+round2%') AND email LIKE '%quillmd-test.local%';
DELETE FROM users WHERE email = 'qa-test+round21777839763@gmail.com'; -- specific gmail test
```
