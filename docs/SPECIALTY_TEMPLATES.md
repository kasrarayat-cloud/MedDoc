# Specialty Templates — authoring guide

Scribe's specialty templates live at `apps/scribe/specialties/*.yaml`. Each
file becomes one `ScribeSpecialtyTemplate` row after `npm run
seed:specialties`. Templates are the single biggest lever on output
quality — the SOAP / coding / Rx / referral / summary passes all inherit
their guidance.

## Status: DRAFT

**Every template currently in this directory was authored by engineering
without sign-off from a licensed specialist in the field.** The database
column `clinicalReviewStatus` defaults to `DRAFT`; the review UI shows a
warning banner so clinicians know not to trust an M5 template blindly.

A specialist in each field should review their template and PR a change
to `clinicalReviewStatus: specialist_reviewed` once they've verified:

- Required exam elements reflect what a competent specialist documents
  on every visit
- The SOAP schema keys fit the specialty's note convention
- ICD-10 / CPT hints match the specialty's typical billing patterns
- The system prompt doesn't contradict ACC/AHA/DSM-5/etc. terminology
- Any safety clauses (e.g. psychiatry's 988 escalation) behave correctly

When all seven reviews are in and at least one real-patient pilot has
passed, status can be bumped to `production`.

## File shape

```yaml
slug: cardiology                    # unique, lowercase, hyphenated
displayName: Cardiology
version: "1.0.0"
clinicalReviewStatus: draft         # draft | specialist_reviewed | production

# 4–6 cardinal findings a competent specialist documents every visit.
# Informational — missing elements land in soap.missing_required_elements[],
# never block signing.
requiredExamElements:
  - cardiac_rhythm
  - ...

# Section keys the SOAP generator will populate. Arbitrary strings —
# match the specialty's standard note structure.
soapSchema:
  subjective:  [chief_complaint, hpi, ...]
  objective:   [vitals, cardiac_exam, ...]
  assessment:  [problem_list_with_icd10]
  plan:        [diagnostics, medications, ...]

# Prompt hints the coder pass seeds with. Non-exhaustive.
defaultIcd10Hints:  [I10, I25.10, ...]
defaultCptHints:    ["99213", "99214", "93000", ...]
defaultFormularyHints: [aspirin, atorvastatin, ...]

# Specialty-specific system prompt layered on top of the universal
# rules in server/prompts/generate-soap.md.
systemPrompt: |
  You are documenting a cardiology visit. …
```

## Versioning

The seeder upserts by slug. If `version` matches the DB row, it updates
in place. If it differs, the same row is updated to the new version — we
don't retain historical rows under the same slug. `ScribeOutput`
carries `templateVersion` as a provenance stamp, but historical re-renders
from a bumped template aren't supported yet (flagged for M7 hardening).

Bump the version any time you change content: prompt wording, required
elements, ICD-10 / CPT / formulary hints, or SOAP schema keys.

## How templates flow through the pipeline

1. `apps/scribe/src/server/workers/finalize-visit.ts` loads the row
   associated with `ScribeVisit.specialtyId`.
2. SOAP generation: `systemPrompt` + `soapSchema` + `requiredExamElements`
   concatenate into the generator system prompt.
3. Coding extraction: `defaultIcd10Hints` + `defaultCptHints` go into
   the extract-coding prompt as suggestions (never a whitelist).
4. Rx / referral / summary passes: currently don't read specialty content
   directly. The patient-summary prompt reads the SOAP's
   `requires_immediate_follow_up` flag to decide whether to append
   crisis resources — psychiatry's template instructs the SOAP
   generator to set that flag when safety concerns surface.

## Psychiatry safety clause (M5)

The `psychiatry.yaml` system prompt contains a hard rule: if the visit
mentions self-harm, suicidal or homicidal ideation, or any safety
concern, the SOAP generator must set `requires_immediate_follow_up: true`
and surface the concern as a high-priority `ambiguities[]` entry. The
patient-summary prompt reads this flag and verbatim-appends the 988
Suicide & Crisis Lifeline + 911 resources. This clause is non-negotiable
even under review.
