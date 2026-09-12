# RULED-MUTATION DECLARATION — certify the colon operative-note twin under REGISTRY-2 (#319)

**Written and committed BEFORE the act.** Owner-ordered (ruling #319): re-propose
the colon operative-note twin's mappings under the new `procedure.*` registry,
certify through the REAL production path, and SUPERSEDE the existing PDF-native
"Operative Note" (retired, never deleted). The practice DEFAULT is pinned to the
GI consult; the visit picker then offers the certified templates including this twin.

## WHY A NEW ACT (not the SLICE-0 draft `5091c82c`)

SLICE-0's auto-certify (draft `5091c82c`) was correctly DECLINED: with no
operative-note concepts, the model mapped a colon note's Findings onto
`exam.vascular` and Procedure onto `plan`. #319 adds the `procedure.*` family so
the mapping is correct BY CONSTRUCTION, and re-authors the twin's numbered slots
to share one bullet-group identity so they distribute. This act ingests the
RE-AUTHORED, re-pinned `.docx` (a NEW draft); `5091c82c` (draft, NEEDS_CONFIRMATION,
built from the old structure) is left untouched.

## THE ACT

`scripts/run-ruled-mutation.sh --declaration <this> --in transcribe-md-worker
-- npx tsx scripts/certify-colon-twin-319.ts <docx> <userId> <userEmail>
<practiceId> cmtxznk2u001v01qjpq2296qm 3877d5cf-ad03-4412-a322-6be0c7dcb3ff` — which:
1. `createTemplateTwinDraft` of the PINNED committed re-authored
   `apps/transcribe-md/src/lib/template-twin/colon-operative-note/colon-operative-note.docx`
   (package sha `a378c4e1…`) into the owner's practice.
2. Logs the model's proposal under REGISTRY-2 (evidence the mis-mapping is fixed),
   then sets the ruling's 17-mapping set EXPLICITLY: the record-derived header
   confirmed (owner-authorised), the clinical bodies to their `procedure.*`
   concepts, and the three Findings / three Recommendations slots to BYTE-IDENTICAL
   mappings (bullet-group G7, so they distribute).
3. `updateTemplateTwinMappings` → LIVE L3/L4 synthetic round-trip self-test
   (PHI-free synthetic dictation over an ephemeral fixture visit) →
   `certifyAndActivateTemplateTwin`.
4. Retires the PDF-native `cmtxznk2u001v…` (status → inactive; row kept), and
   pins `Practice.defaultNoteTemplateId` = `3877d5cf…` (GI consult; certified).

**ACTOR:** `cmo5ye2nm000c01s3ofudqzi6` (kasra.rayat@gmail.com, OWNER) /
practice `cmo5ye2nf000b01s3q0xlkaxb`.

⚠️ **NO REAL VISIT IS TOUCHED.** The self-test dictation is synthetic and PHI-free;
any fixture visit it creates is ephemeral and cleaned. Certification binds a
synthetic ROUND-TRIP proof, not a real note.

## OUTCOME — DETERMINED BY THE CERTIFICATION GATE

The path is self-gating: it either certifies+activates, or throws
CERTIFICATION_BLOCKED / a proof failure and leaves a NEEDS_CONFIRMATION draft with
the reason. Both declared:

**On CERTIFY (proof passes, no blocker):**

| # | row | from | to |
|---|-----|------|----|
| M1 | note_templates | 19 | 20 (the new colon twin draft) |
| M2 | compiled versions / certifications | 7 / 5 | 8 / 6 |
| M3 | active operative-note template | `cmtxznk2u001v…` (PDF-native) | the new colon twin — PDF-native DEACTIVATED (retired), row kept |
| M4 | `Practice.defaultNoteTemplateId` | null | `3877d5cf…` (GI consult) |

**On DECLINE / BLOCK (proof cannot be derived, or a certification blocker):**

| # | row | effect |
|---|-----|--------|
| D1 | note_templates | 19 → 20 (a NEEDS_CONFIRMATION draft) |
| D2 | compiled versions | 7 → 8; certifications UNCHANGED (5) |
| D3 | active template / default | UNCHANGED — nothing activated, default not set; the reason is reported |

## MUST NOT CHANGE (RE-READ at act)

| # | row | baseline |
|---|-----|----------|
| N1 | visits / patients / signed | **61 / 49 / 41** — the act writes NO clinical data; any ephemeral fixture visit is cleaned |
| N2 | practices / users | 199 / 198 |
| N3 | applied migrations | 118 |
| N4 | the GI consult `3877d5cf…` | stays CERTIFIED; only referenced as the default, never edited |
