---
id: A06-P1-009
title: Pediatric mg/kg dosing has no deterministic validator; weight not even captured
severity: P1
domain: AI safety / pediatric clinical correctness
files:
  - apps/transcribe-md/src/worker/prompts/specialty-guidance.ts (lines 31-36)
  - apps/transcribe-md/src/worker/layers/07c-rx-drafting.ts
  - packages/db/prisma/schema.prisma (no patient.weight field)
---

## Issue

The pediatrics-specialty path provides no protection against
mg/kg dosing errors:

1. **No patient weight field** in the canonical patient model. The
   visit doesn't know how much the kid weighs.
2. **No per-drug mg/kg max table** anywhere in the codebase.
3. **L7c Rx drafting** has prompt-instruction-only safety:
   "Dose appears out of the adult (or pediatric if applicable)
   therapeutic range" → critical warning. The "if applicable" is
   model-judgment.
4. **Pediatrics specialty guidance** asks the model to "Document
   growth parameters (weight, height, head circumference,
   percentiles) if given. Document developmental milestones."
   "Use age-appropriate language in patient education." None of
   this is a dose-validity check.

## Evidence

`grep -rn "mg.*kg\|mg/kg\|weight.*kg\|patient.*weight\|dose.*range\|max.*dose" /opt/meddoc-pro/apps/transcribe-md /opt/meddoc-pro/packages/`
returns nothing related to pediatric dose validation.

The patient schema in `apps/meddoc-pro` has weight (visible in
`apps/meddoc-pro/src/components/patients/intake.tsx`) — but the
transcribe-md app is the QuillMD scribe product post-CRM
decommission and uses its own `transcribe_visits.patient_*` model
with no weight field.

A 3-year-old gets the same Rx warning rail as a 70-year-old. A
fentanyl patch dose, a Tylenol dose, a clindamycin dose are all
validated against "what Claude knows about adult dosing" with a
gentle prompt suggestion to consider peds.

## Risk

P1 because:

- Pediatric mg/kg errors are a published top-3 cause of inpatient
  pediatric harm. A 10x calculation error on amoxicillin is
  rarely fatal; on digoxin or methadone it absolutely is.
- The pediatrics specialty *exists* in the catalog, so this path
  WILL be exercised by clinics that select it.
- The marketing page lists pediatrics as a supported specialty
  (specialty-catalog.test.ts:32) — implying validated peds use is
  a product feature.

## Recommended Fix (plan only)

1. **Add `weightKg` (Decimal, nullable) to the visit-creation
   form** when `specialty === 'pediatrics'`. Make it required.
   Persist on `transcribe_visits`.

2. **Static peds-dose table** for top-50 outpatient peds drugs:
   amoxicillin, clindamycin, azithromycin, ibuprofen,
   acetaminophen, prednisolone, albuterol, ondansetron, etc.
   Schema: `{ drug: string, mg_per_kg_per_day_min: number,
   mg_per_kg_per_day_max: number, max_per_24h_mg: number }`.

3. **Post-L7c validator**: for each prescription with
   `specialty === 'pediatrics'` AND `weightKg != null`:
   ```ts
   const expected_max = max_per_kg_per_day * weightKg;
   const actual = parseRxDose(prescription) * doses_per_day;
   if (actual > expected_max * 1.2) emit critical warning;
   ```
   Independent of the model.

4. **Reject Rx without weight** when `specialty === 'pediatrics'`:
   refuse to render a prescription line; surface a critical
   "weight required for pediatric dose validation" warning.

5. **Documentation banner** on pediatric visits: "Pediatric dosing
   is checked against a static table for top-50 drugs only.
   Verify all prescriptions manually."

This complements P0-004 (drug interaction DB). The two together
get pediatric Rx safety from "model only" to "model + static
backstop", which is the floor for pre-pilot.
