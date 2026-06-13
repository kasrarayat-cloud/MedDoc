# Live-voice prod-smoke defects — fixes (2026-06-13, branch fix/live-smoke-defects)

A live-voice signed note (internal-medicine HTN follow-up) surfaced four defects. The
anchored pipeline handled the clinical core correctly (digits verbatim, negation polarity,
lisinopril [CONTINUE] in the body, E/M gate fired 99213→99214).

## 1. Empty Assessment (BLOCKER) — FIXED
Root cause: anchored body composition keeps the exempt `## Assessment` header but drops
every demoted claim line; when all Assessment narrative sentences demoted to the lane, the
block rendered blank. Fix (`04b-anchor-verify.ts`): `backfillEmptySections` injects a
visible review placeholder into any section that LOST content (never the demoted content
itself — that stays quarantined in the lane), flags `filledEmptySections` → `needsReview` +
banner. **An empty Assessment in a signed note is now impossible by construction.** Adopting
real content into the section retires the placeholder.

## 2. Plan numbering holes (4,5,6,8,9) — FIXED
Surviving ordered-list items kept their original ordinals after demotion.
`renumberOrderedLists` (`src/lib/soap-format.ts`) renumbers every section's list 1..n over
whatever lines compose the final note — applied at generation AND at adoption (an adopted
lane item carries its old ordinal). Top-level items only; never touches doses/dates/prose.

## 3. Rx safety DB coverage + severity — FIXED
- **Coverage:** added 18 common drugs to the verified dose-range table (64→82): amlodipine
  (the trigger) + top antihypertensives (atenolol, carvedilol, chlorthalidone, diltiazem,
  furosemide, hydralazine, losartan, valsartan), statins (lovastatin, pravastatin), and
  common antibiotics (amoxicillin-clavulanate, cefdinir, clindamycin, levofloxacin,
  metronidazole, nitrofurantoin, trimethoprim-sulfamethoxazole). Conservative FDA/Lexicomp
  caps + class-accurate contraindications.
- **Severity:** `RX_DRUG_NOT_IN_VERIFIED_DATABASE` re-tiered `major` (rail `serious`) →
  `minor` (rail `info`/coaching). A coverage gap is "verify against reference," not a
  clinical emergency. Genuine contraindications + dose-exceeds keep `critical`; the sign
  gate still counts ONLY `critical`, so the alarm level changed, never the safety gate.

## 4. "Bariatric Surgery" specialty on a general IM visit — NOT A CODE BUG (account data)
Investigated: a visit's specialty is selected at creation, defaulting to the doctor's
most-recent-visit specialty; for a brand-new doctor the default is
`SPECIALTIES_FOR_VISIT_CREATE[0]` = **Primary Care** (verified — `unspecified` is filtered
out, Primary Care is first). Nothing in code defaults to Bariatric Surgery. So the label
came from account/visit DATA — a prior visit created under Bariatric Surgery carried forward
as the new-visit default and wasn't changed (the carry-forward is sticky until the doctor
picks another specialty).

**For Kasra (account action — not changed unprompted):** on the affected visit/account,
select **Primary Care** (Internal Medicine maps to primary-care) as the specialty; future
visits will then carry that forward. No code change required.
