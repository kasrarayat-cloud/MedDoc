# RULED-MUTATION DECLARATION — certify the colon operative-note twin (#317)

**Written and committed BEFORE the act.** Owner-ordered (SLICE-0): certify the
colon DOCX Template Twin through the REAL production path, and SUPERSEDE the
existing PDF-native "Operative Note" (retired, never deleted). The practice
DEFAULT stays the GI consult; the visit picker then offers GI (default) +
Operative Note (this twin).

## THE ACT

`scripts/run-ruled-mutation.sh --declaration <this> --in transcribe-md-worker
-- npx tsx scripts/certify-native-twin.ts` — which:
1. `createTemplateTwinDraft` of the PINNED committed
   `apps/transcribe-md/src/lib/template-twin/colon-operative-note/colon-operative-note.docx`
   (package sha `64aef465…`) into the owner's practice.
2. `runAutoCertifyTwin` — the SAME path the production worker runs: plan the
   mappings (`planAutoConfirm`), and iff 0 fields decline, run the LIVE L3/L4
   synthetic round-trip self-test (PHI-free synthetic dictation over an ephemeral
   fixture visit) and `certifyAndActivateTemplateTwin`.

**ACTOR:** `cmo5ye2nm000c01s3ofudqzi6` (kasra.rayat@gmail.com, OWNER) /
practice `cmo5ye2nf000b01s3q0xlkaxb`.

⚠️ **NO REAL VISIT IS TOUCHED.** The self-test dictation is synthetic and
PHI-free; any fixture visit it creates is ephemeral and cleaned. Certification
binds a synthetic ROUND-TRIP proof, not a real note.

## OUTCOME — DETERMINED BY THE AUTO-CERTIFY GATE

The auto-certify path is self-gating; it either certifies+activates or leaves a
NEEDS_CONFIRMATION draft with the declined fields named. Both branches declared:

**On CERTIFY (0 declined + proof passes):**

| # | row | from | to |
|---|-----|------|----|
| M1 | note_templates | 18 | 19 (the colon twin) |
| M2 | compiled versions / certifications | 6 / 5 | 7 / 6 |
| M3 | active operative-note template | `cmtxznk2u001v…` (PDF-native) | the colon twin — the PDF-native one DEACTIVATED (retired), row kept |

**On DECLINE (any field unconfirmed, or proof cannot be derived):**

| # | row | effect |
|---|-----|--------|
| D1 | note_templates | 18 → 19 (a NEEDS_CONFIRMATION draft) |
| D2 | compiled versions | 6 → 7; certifications UNCHANGED (5) |
| D3 | active template | UNCHANGED — nothing activated; declined fields reported for a follow-up mapping act |

## MUST NOT CHANGE (RE-READ at act)

| # | row | baseline |
|---|-----|----------|
| N1 | visits / patients / signed | **61 / 49 / 41** — the act writes NO clinical data; any ephemeral fixture visit is cleaned, so these are unchanged AFTER |
| N2 | practices / users | 199 / 198 |
| N3 | applied migrations | 118 |

## AFTER THE ACT (separate, small OWNER-setter writes, declared here)

- Set `Practice.defaultNoteTemplateId` = the current certified GI-consult template
  (the practice default stays GI), via the audited `updatePractice` verb.
- The duplicate certified GI/Gastroenterology twins already in the practice are a
  pre-existing picker-hygiene question surfaced to the owner, not touched here.

## ROLLBACK

The colon twin can be deactivated and the PDF-native operative note re-activated;
no data is destroyed. The draft/compiled rows are additive.
