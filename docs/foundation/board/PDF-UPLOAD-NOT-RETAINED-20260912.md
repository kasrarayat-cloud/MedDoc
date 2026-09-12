# Measurement — the owner's uploaded PDF was not retained (upload-and-certified arc, #1)

**Filed 2026-09-12. MEASUREMENT ONLY — do not build on this yet (owner directive).**
The owner asked, alongside SLICE 0, to record *why* the actual upload
`colon_questions_only.pdf` was not retained on the box, as the first measurement
of the upload-and-certified arc. This traces the PDF upload path and what it
stores. No fix is proposed here.

## FINDING

**The original uploaded source PDF is NOT retained. It is text-extracted in
memory and dropped.** The only durable PDF bytes anywhere are a certify-time
*derived* canvas, produced only if a separate PDF-native certify step is
completed and its label anchors resolve — and that canvas is not the original
file.

### The primary path — "My Note Format" upload

- UI `note-format-manager.tsx` → `extractNoteFileAction` (`extract-note-file.ts`).
- That action was rewritten (RC-2 / ruling #106(b)) to **persist-then-extract**
  so a doctor's original file survives a parse failure — **but retention is gated
  on `isKeepableUpload()` (`extract-note-file.ts:68-74`), which returns true ONLY
  for `.docx`.**
- For a **PDF**: the predicate is false → the `storeUploadArtifact` branch
  (`:109-118`) is **skipped** → `source` stays undefined → bytes go to
  `extractNoteTextFromUpload` (`:132`, in-memory) → garbage-collected when the
  request returns. The saved template row gets `sourceObjectKey = null`
  (`note-template-lifecycle.ts:186-207` only sets a source ref when the client
  carried one).
- The retention store itself is **DOCX-only by construction**:
  `createUploadArtifactKey` ends in `.docx` (`keys.ts:147`); `storeUploadArtifact`
  tags/validates everything as `DOCX_MIME_TYPE` (`artifact-store.ts:287/305/362`).

### The PDF-native certify path — separate, opt-in, and not the original

- `certify-pdf-template.ts`'s own header states the My-Note-Format upload
  "extracts text and DISCARDS the PDF bytes," so the doctor "re-uploads his blank
  form ONCE" at certify.
- Certify stores a **derived canvas** at `pdf-native/<templateId>/canvas.pdf`
  (`putTemplateCanvas`, `store.ts:11`) — keyed by templateId, **not** under the
  template-twin `uploads/` prefix, and only if certify completes and anchors
  resolve. `putTemplateCanvas` stores `input.pdfBytes` — whatever was handed to
  certify, which need not be the original first-picked file.

## WHY `colon_questions_only.pdf` IS GONE

It was uploaded through the My-Note-Format path, text-extracted for the template,
and its bytes dropped because it is a PDF, not a `.docx`. Nothing wrote the
original to minio, DB, or disk. This is **the same class of loss RC-2 was created
to end for `.docx`, still open for PDF** — the load-bearing comment at
`extract-note-file.ts:66` justifies dropping PDF bytes with *"PDF has its own
certification path that already persists its canvas,"* which is only true if the
doctor completes certify AND anchors resolve; an uploaded-but-not-certified PDF
leaves **zero** durable bytes and is unrecoverable.

## FOR THE ARC (not built here)

The upload-and-certified arc should decide whether PDF uploads get the same
persist-then-extract retention `.docx` got under RC-2 — a class-(a)/(b) question
(a capability doctors would reasonably expect; losing the original is an
accepted-capability question). Filed as the arc's first measurement; no build.
