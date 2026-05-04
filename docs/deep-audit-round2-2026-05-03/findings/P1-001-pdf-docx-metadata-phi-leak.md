# P1-001 — PDF + DOCX exports leak patient name in document metadata

**Severity:** P1 (HIPAA-relevant — PHI in export-document metadata
travels outside the system once the doctor downloads or shares)
**Files:**
- `apps/transcribe-md/src/lib/pdf-generator.ts:97-103`
- `apps/transcribe-md/src/lib/docx-generator.ts:293-296`

## What

Both export generators write the patient's full name into the
document-level metadata fields:

**PDF** (pdfkit):
```js
info: {
  Title:    `Visit — ${data.patientName ?? 'Anonymous'} — ${formatVisitDate(...)}`,
  Author:   data.clinicianName ?? 'QuillMD',
  Creator:  'QuillMD',
  Producer: 'QuillMD PDF Generator (pdfkit)',
}
```

**DOCX** (`docx` lib):
```js
const doc = new Document({
  creator: data.clinicianName ?? 'QuillMD',
  title:   `Visit — ${data.patientName ?? 'Anonymous'}`,
  description: `QuillMD visit note exported ${formatVisitDate(new Date())}`,
  ...
});
```

The patient's name is therefore visible in:

**PDF** (anywhere a PDF metadata reader looks):
- Browser tab title when opened in Chrome/Safari/Firefox
- `File > Properties` in Adobe Reader / Preview
- `pdfinfo file.pdf` (poppler-utils)
- macOS Spotlight indexing → file shows up in search by patient name
- Windows Search → same
- Email client preview headers
- DLP scanners flag PHI presence

**DOCX** (anywhere `app.xml` / `core.xml` is parsed):
- File Properties dialog in Word / Pages / LibreOffice
- `unzip -p file.docx docProps/core.xml`
- Outlook preview pane

## Why this matters

HIPAA's "minimum necessary" doctrine says PHI should appear only
where it has clinical purpose. Document metadata is decorative — the
patient's name is on the cover page already. Putting the name in
PDF `Title` AND DOCX `title` AND `creator` doesn't help the doctor
identify the file (the body does that), but it WILL leak the name to:

- Anyone with file-system access on the doctor's laptop
- Cloud sync services (Dropbox, OneDrive, iCloud) that index metadata
- Backup systems that scan metadata for catalog purposes
- Any third party who receives the file via email — even if they
  never open it, their mail client's preview shows the title

A doctor sending a visit note to a specialist would expect the
recipient to see the patient name only in the body, not as the file
title visible in their inbox subject-line preview.

## Reproduction

1. Sign in as any doctor with at least one signed visit
2. Click "Sign & Send" with `pdf` (or `docx`) destination
3. Download the file
4. `pdfinfo /tmp/visit.pdf | grep -E 'Title|Author'`
   OR
   `unzip -p /tmp/visit.docx docProps/core.xml | grep -E 'title|creator'`
5. Observe patient full name + clinician name in metadata

## Risk if NOT fixed

- HIPAA breach if a metadata-leaking PDF is forwarded outside the
  practice (the recipient's inbox preview now shows PHI in the file
  title without ever opening the file)
- Audit / compliance flag during a Privacy Rule review
- Realistic doctor workflow: download PDF → AirDrop to colleague →
  AirDrop preview shows patient name in the file-title field

## Proposed remediation (mechanical)

```diff
// pdf-generator.ts:97-103
info: {
-  Title:    `Visit — ${data.patientName ?? 'Anonymous'} — ${formatVisitDate(...)}`,
-  Author:   data.clinicianName ?? 'QuillMD',
+  Title:    `Visit ${data.visitId ?? 'note'}`,
+  Author:   'QuillMD',
   Creator:  'QuillMD',
   Producer: 'QuillMD PDF Generator (pdfkit)',
}

// docx-generator.ts:293-296
const doc = new Document({
-  creator: data.clinicianName ?? 'QuillMD',
-  title:   `Visit — ${data.patientName ?? 'Anonymous'}`,
+  creator: 'QuillMD',
+  title:   `Visit ${data.visitId ?? 'note'}`,
   description: `QuillMD visit note exported ${formatVisitDate(new Date())}`,
```

(Or — replace the patient name with their ID/MRN, which is also
PHI but at least less human-readable in a preview pane.)

The body of the document is unchanged — patient name remains on the
cover page and inside the SOAP body, where it serves a clinical
purpose.

## Effort

- Code change: 2 files × 3 lines = ~5 min
- Smoke test (download a fresh PDF + DOCX, verify metadata): ~10 min
- Total: ~15 min

## Risk to fix

VERY LOW — pure metadata edit; no behavior change to the document
body, no DB schema change, no public API change.

## Status

Plan-only per audit rules (P1 stays plan-only). Recommend Kasra
approve the 6-line PR. This is the highest-impact finding in
Round 2 — fix should be prioritized.

## Side-channel: also affects clipboard exports?

Need to verify — `apps/transcribe-md/src/lib/ehr-formatters.ts`
emits plain-text clipboard payloads for Epic/Athena/Cerner/eCW.
Plain text has no metadata so this finding doesn't apply there.
But the CLINICIAN'S BROWSER would have the patient name in the
clipboard ring if they paste-and-cancel — out of scope for this fix.
