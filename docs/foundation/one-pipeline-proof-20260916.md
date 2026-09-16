# ONE-PIPELINE proof — the owner's colonoscopy form (ruling #326)

**2026-09-16. No deploy.** Proof that the render → detect → map → fill → certify
pipeline works end-to-end on the owner's real colonoscopy form, as ruling #326
directed before any migration. Run in an isolated venv; scratch reaped after.

## Verdict: 🟢 GO

The pipeline is feasible and works on the owner's actual colonoscopy PDF and the
colon Word file. Detection matches the visible blanks, fills land in-box, and the
page is **pixel-identical outside the detected boxes** on both paths. The detector
is self-hosted on CPU. The open items (AI mapping preview, overflow→continuation,
multi-line grouping, the pixel-diff certify gate) are build work in the slices —
not feasibility blockers.

## What was run

- **Detector:** `commonforms` 0.2.1 + **FFDNet-L**, self-hosted, `pip install commonforms`
  (ONNX / ultralytics, **CPU** — no GPU, no external service). Weights pulled once
  from HuggingFace (`jbarrow/FFDNet-L`).
- **Stage 1 (normalize):** the colon `.docx` → PDF via the existing Gotenberg
  `/forms/libreoffice/convert` (200, 1 page). The owner PDF (`a06159ece48c`, the
  certified source, fetched from MinIO) is already a flat PDF (US Letter, **0**
  AcroForm fields — visible blanks only).
- **Stage 4 (fill):** `pdf-lib` filled every detected box with a bounded sample
  value; appearance streams baked with an embedded font (FFDNet boxes carry no `/DR`).
- **Stage 5 (fidelity):** `pypdfium2` rasterized original vs filled at 150 DPI;
  `numpy` diffed every pixel OUTSIDE a padded union of the detected boxes.

## Field counts vs visible blanks

| Form | input | detected | fills | outside-box pixels changed | notes |
|---|---|---|---|---|---|
| **Owner colonoscopy PDF** (`a06159…`, flat) | 0 native fields | **29** boxes (FFDNet-L, 3.7 s CPU) | **29 / 29** in-box | **0** of 1,144,995 (**0.0000 %**) | every visible blank hit; multi-line sections (DESCRIPTION ~4–5 lines, CONSENT 2 lines, FINDINGS/RECS 1-2-3) split into per-line boxes |
| **Colon `.docx`** → Gotenberg PDF | 17 content controls → **17** native AcroForm fields | (native, no FFDNet needed) | **17 / 17** in-box | **0** of 1,957,339 (**0.0000 %**) | LibreOffice carries controls through as fields |

The old structural-twin pipeline captured **24** fields on this PDF (16 clinical +
8 headers). FFDNet's **29** are the *same* fields plus the multi-line sections split
into one box per visible blank line — **more granular**, not wrong. Stage 3 can group
per-line boxes back to one concept (or fill line-by-line with overflow).

## Fill correctness & layout fidelity

- **In-box:** every sample value (S0–S28 / S0–S16) renders inside its box, on the
  correct blank line (see screenshots: detection overlay, filled PDF, filled Word).
- **Outside-box: 0 pixels changed** on both paths — the "pixel-identical outside the
  boxes" certify criterion is met exactly at 150 DPI, ≥24/255 per-channel threshold.
  Inside-box pixels change (21,411 / 3,726), proving the fills rendered.
- **Overflow:** the deliberately long sample fit the wide CONSENT box, so
  continuation-page overflow was not triggered; it remains a stage-4 feature to build.

## Migration findings (recorded so they are not re-derived)

1. **A Word-with-controls form must NOT be flattened into stage 2.** Its (empty)
   controls flatten to nothing and the blanks disappear. Gotenberg instead carries
   content controls through as AcroForm fields, so stage 2 for such a form is "use
   the native fields". **FFDNet detection is for flat PDF and prose Word** (visible
   blanks). This is exactly why #326 keeps the Word-with-controls path alive until
   each form is migrated deliberately.
2. **FFDNet boxes carry `/DA` but no form `/DR`** — pdf-lib must supply a font and
   bake appearances (`updateAppearances`) or the fill is invisible in strict viewers.
3. **The colon `.docx` in-repo is the minimal SLICE-0 skeleton**, not the rich form;
   the owner's rich colonoscopy lives as the **PDF** (`a06159…`). The PDF path is the
   representative one.

## Migration slices (each with its own adversarial pass; owner acceptance before cutover)

- **A — new pipeline behind a flag** (`lib/form-fill/`: `detect-fields`, `map-fields`
  wrapping `proposeSemanticMappings`, `fill-boxes` reusing `pdf-native/fill-engine`'s
  pdf-lib drawing, `certify-boxes` = synthetic visit + pixel-diff-outside-boxes).
  Additive; a new box-geometry binding kind (do NOT alter `TemplateField.rendererBinding`
  — that de-certifies live DOCX twins). No routing yet. Breakage risk to kept path: none.
- **B — route PDF uploads** onto it (the `wasPdf` branch of `createTemplateTwinDraft`);
  wire the flat-PDF UI + the visit PDF-export route to prefer box-fill when flagged.
- **C — route prose-Word uploads** onto it (the `ir.fields.length === 0` branch);
  must NOT catch Word-with-controls (they have fields > 0 and never enter that branch).
- **D — cutover + validation** on real forms; **owner acceptance test (class c)**
  before any real doctor form cuts over.
- **E — retire** `prose-form/` + `pdf-form/` and the two derivation branches in
  `create-draft.ts` (keep the function + `fieldCreateInput`).
- **F — retire** `lib/pdf-native/` (the anchor/styled render, `pdfNativeCertified`,
  the canvas store); keep the DOCX→Gotenberg→PDF export as the DOCX-twin fallback.

Keep byte-stable throughout: `certification-lifecycle`, `synthetic-test`,
`semantic-mapping`, the DOCX compiler/renderer, the resolve/validate core, and every
persisted mapping/field column (any shape change de-certifies live DOCX twins, #217/#185).

## Toolchain deltas the migration will need (not on prod today)

- `commonforms`/FFDNet must be **self-hosted as a service** (a sidecar container with
  the ONNX runtime + pinned weights), reached like Gotenberg on the internal network —
  not a per-request `pip` process. Pin the weights; the model is the input to a
  clinical layout, so its version is part of the certification signature.
- `pypdfium2` (or an equivalent rasterizer) for the stage-5 pixel-diff gate.
