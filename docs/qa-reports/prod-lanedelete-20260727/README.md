# Prod — suggestion lane deleted, verifier audit-only, preview framed (2026-07-27)

Two deploys. Rollbacks `:pre-auditonly-20260727` and `:pre-lanedelete-20260727`.

| | commit | app | worker |
|---|---|---|---|
| checkpoint (backend) | `41ec3a44` | `8b72fe36cbcb` | `b76a991e84a1` |
| lane delete + preview | `0e5257ce` → `4719eef70099` | `4719eef70099` | `09ea62317b44` |

Migration `20260727190000_anchor_flags_recorded` applied; enum value live.

## Root cause

The six-FP-class provenance work shipped at 17:42 and a fresh ultrasound visit
at 18:22 still carried **ten** flags. Both true: `buildSectionPolicy` reads the
ACTIVE TEMPLATE's declared sections, and `provenance` is an OPTIONAL field only
the BUILT-IN templates set.

The production form that failed has eight sections, `provenance` on **none**,
`defaultText` on **all**, and it DECLARES `PROCEDURES / E&M` and
`PATIENT SUMMARY`. So:

- `s.provenance ?? 'dictation'` marked TECHNIQUE and IMPRESSION verifiable →
  2 flags.
- `if (!byLabel.has(label))` let that declaration beat `PIPELINE_SECTION_POLICY`
  → the cross-step sections were judged too → 8 flags, 7 of them
  patient-summary paraphrase.

The smoke that "proved" the fix used a doctor with no custom template, fell back
to the built-in ultrasound template — the one carrying the declarations — and
measured the single path that was never broken.

## Fixes

1. `PIPELINE_SECTION_POLICY` wins **unconditionally**. No template can claim
   authorship of content a later step writes.
2. `inferProvenance` covers protocol-by-nature sections (technique, comparison)
   for templates that never declared any.
3. Template boilerplate is exempt **per line**, not per section — the fixed
   prose a form supplies becomes mandated lines. Section-level was tried first
   and would have exempted FINDINGS, where the measurements live; caught by
   reading the real template before deploying, and pinned by a test.
4. Verifier is **audit-only**: `suggestedClaims` actively cleared, the draft
   comes from a new `fullBody` (all lines, anchors stripped, nothing demoted
   away), findings recorded as `ANCHOR_FLAGS_RECORDED`.

## E/M relocation

The `⋯ details` collapsible housed `em-stale-badge` and the lazy re-score — the
only control that clears the E/M gate. Deleting it wholesale would have left the
sign route refusing for a reason folded behind a disclosure.

**New home:** an inline gate card in the stack next to the signature —
`review-doc-em-stale-gate`, carrying `em-stale-badge` and
`review-doc-em-rescore`. The sign bar names it too. Then the collapsible was
deleted; its billing / codes / dictation panels render inline, with
`data-chat-target="codes"` preserved so "show billing" still resolves.

## Prod evidence

**Custom-template ultrasound** (`isSystemDefault=f` — the regressed path):

| | before (18:22) | after |
|---|---|---|
| suggested claims | 10 | **0** (cleared) |
| sections evacuated | TECHNIQUE, PROCEDURES/E&M | **0** |
| DOM suggestion nodes | card stack | **0** across 5 selectors |
| `⋯ details` toggle | present | **0** |
| letter | flooded | all 6 sections incl. PATIENT SUMMARY |

Audit sample — counts only, no note text:
```json
{"visitId":"cms3msa3l…","flagCount":2,
 "categories":{"no_anchor":1,"not_entailed":1},"anchored":12,"demoted":2}
```

**Preview framing** — page capped at `--qm-page-w: 820px`, one number both
formats obey:

| viewport | PDF paper | Word paper | gutter | side-scroll |
|---|---|---|---|---|
| 1024 | 584 (column-limited) | — | 41px | none |
| 1440 | **820** | **820** | 131px | none |
| 1920 | **820** | **820** | 371px | none |

0px parity, where PDF previously stretched to 1082 / 1562. Canvas
`rgb(8,9,10)` = #08090a, `padding-top: 0` (dead band gone), one toolbar row.

**Three gates:**

- **E/M — verified end-to-end on a primary-care visit.** Edit → `emStale=true`
  with baseline 99214 → inline gate + badge + "Re-check the documentation level
  above" → re-check (`EM_RESCORED` audit row) → flag cleared → **SIGNED**.
  Not verifiable on imaging: `emNotApplicable` is true for ultrasound by design.
- **VIEWED_VISIT** — 13 rows across the walk.
- **critical-Rx typed override — NOT exercised live.** Neither smoke visit drew
  a critical warning, so the override path was not walked on prod. It is covered
  by unit tests and by the structural fact that the sign route references
  `suggestedClaims` zero times, but this report does not claim a live pass.

## QA walker — DID NOT RUN

`sweep-visit-page.mjs` fails at its own login stage against prod
(`page.waitForURL` timeout, no `LOGIN_SUCCESS`/`LOGIN_FAILED` audit row — the
submit never reached the server). Not a product fault: the smoke account has
`mfaEnabled=false`, a verified email and the TRANSCRIBE_MD product, and the same
credentials log in through a browser seconds earlier. The walker is a QA-stack
tool whose default user and fixtures live there.

Recorded as unverified rather than skipped quietly. The same surface was
asserted directly (DOM counts across five suggestion selectors, the collapsible,
the gate testids, the panels, the section list) — narrower than a walker sweep,
and named as such.

## Cleaned to baseline

visits 0 / patients 0 / templates 0; user, practice and **158 audit rows**
preserved. Downloaded signed PDF removed from the box.

## Observations

- A prior session's real patient export (`visit-eleanor-whitfield-*.pdf/.docx`)
  is sitting in `.playwright-mcp/` on the box. Gitignored (line 117) and not
  tracked, so no PHI reached the repo — but it is a filled clinical document on
  disk and worth a deliberate clean-up decision.
- The gap between the visit title row and the chat card is unchanged. The dead
  band this work removed is the one **above the page**, inside the document
  frame; the header spacing is a different surface.
