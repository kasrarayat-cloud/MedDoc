# RULED-ACT DECLARATION — Slice D acceptance: certify the owner's colon form via the DETECT pipeline

**Written before the act.** Runs the owner's `Colonoscopy_Operative_Template.pdf`
through the #326 ONE-PIPELINE detect→map→certify, mapping each detected box by
TRANSFER-BY-IDENTITY from his CERTIFIED colon twin (compiled `4de6f662`), and emits the
sample-filled preview PDF for his acceptance. Owner directive 2026-09-17 (Path B).

## The act

```
bash scripts/run-ruled-mutation.sh \
  --declaration docs/foundation/mutations/2026-09-17-certify-owner-colon-detected.md \
  --in transcribe-md-worker \
  -- npx tsx scripts/certify-owner-colon-detected.ts \
       cmo5ye2nm000c01s3ofudqzi6 kasra.rayat@gmail.com cmo5ye2nf000b01s3q0xlkaxb \
       /app/apps/transcribe-md/src/lib/pdf-native/__tests__/__fixtures__/colon-operative-reportlab.pdf
```

The script (deployed in the worker image at the same revision as this declaration):
detect (29 boxes) → group (25) → transfer-by-identity from the twin (24 mapped, 1
unlabeled box excluded) → mint a **DRAFT** NoteTemplate "Colonoscopy Operative Note
(detected · #326)" on the owner's practice → `certifyDetectedForm` (synthetic proof +
pixel fidelity) → write `/tmp/colon-detected-sample.pdf`. It REFUSES (certifies nothing)
if any LABELED box has no approved twin concept.

## Expected delta

| declared | expected | why |
|---|---|---|
| `note_templates` | 22 → **23** | the ruled act mints ONE draft detected-form template |
| owner templates | 14 → **15** | same row |
| **formDetectCertified** templates | 0 → **1** | the detected form is certified |
| new template status | **draft** (NOT active) | no cutover — the real-visit acceptance selects it |
| active templates | **7 (unchanged)** | a draft is not active; nothing is displaced |
| `template_twin` certifications | **7 (unchanged)** | this is the detect path, not the twin |
| `pdfNativeCertified` templates | **7 (unchanged)** | not the pdf-native path |
| `transcribe_visits` | **73 (unchanged)** | no visit is created |
| signed visits | **41 (unchanged)** | — |
| patients | **0 (unchanged)** | — |
| the owner's existing certified colon twin (`8f027c50`) | **unchanged** | read-only source of the mappings |

## What must be true, or the act REFUSES

- Every LABELED detected box transfers to a concept the twin approved (validated
  off-line: 24/24 labeled boxes map; the 25th is an unlabeled box, excluded).
- The synthetic proof fills every fillable box and the page is pixel-identical outside
  the detected boxes (certifyDetectedForm's gate).

A refusal certifies nothing and mints nothing usable — it is the safe outcome, and it
means the transfer or the fidelity gate found a gap, which is the acceptance signal.

## After

Hand the owner the sample PDF. The real-visit acceptance: New Visit → pick "Colonoscopy
Operative Note (detected · #326)" (the visit picker shows his draft templates) → dictate
→ export PDF (routes through the detect pipeline, his practice being allowlisted). His
eyeball on that filled page is the acceptance.
