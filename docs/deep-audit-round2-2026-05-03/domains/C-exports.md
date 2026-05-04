# Domain C — Exports (PDF, DOCX, FHIR, Clipboard)

**Run:** 2026-05-03 20:51 UTC
**Files generated:** `/tmp/r2-export.pdf` (47.4 KB), `/tmp/r2-export.docx` (13.7 KB)

## Summary

| # | Test | Status | Finding |
|---|---|---|---|
| C1 | PDF export `/api/visits/{id}/export/pdf` | ✓ 200 OK, 47.4 KB | **🚨 P1-001: PDF Title contains patient name** |
| C2 | DOCX export `/api/visits/{id}/export/docx` | ✓ 200 OK, 13.7 KB | **🚨 P1-001: DOCX dc:title contains patient name** (verified) |
| C3 | FHIR JSON export `/api/visits/{id}/export/fhir` | **404 — endpoint does not exist** | INFO finding (FHIR export not implemented) |
| C4 | Clipboard endpoints (epic / athena / cerner / ecw / generic) | 405 Method Not Allowed | endpoint is POST-only (called via Sign & Send) — not directly testable as GET |
| C5 | Cross-tenant export (Round 2 user → Round 1 visit) | ✓ 404 — TENANCY ENFORCED | positive finding |
| C6 | Export error handling (corrupt visit) | DEFERRED | requires inducing corruption — out of scope for read-only audit |

## Findings

### P1-001 — PDF + DOCX leak patient name in document metadata

**Confirmed via DOCX:**
```bash
$ unzip -p /tmp/r2-export.docx docProps/core.xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties ...>
  <dc:title>Visit — QA-TEST Mei-Ling Park</dc:title>
  <dc:creator>QA Bypass Updated</dc:creator>
  <dc:description>QuillMD visit note exported 2026-05-03</dc:description>
  ...
</cp:coreProperties>
```

The patient's full name **`QA-TEST Mei-Ling Park`** is embedded in
`<dc:title>` and the clinician's name **`QA Bypass Updated`**
(updated via Settings in Round 1) is in `<dc:creator>`. Both fields
are visible in any DOCX viewer's File Properties dialog WITHOUT
opening the document body.

For the PDF, source code at `apps/transcribe-md/src/lib/pdf-generator.ts:97-103`
shows the same pattern:
```js
info: {
  Title: `Visit — ${data.patientName ?? 'Anonymous'} — ${formatVisitDate(...)}`,
  Author: data.clinicianName ?? 'QuillMD',
  ...
}
```

Full finding + remediation in `findings/P1-001-pdf-docx-metadata-phi-leak.md`.

### C-001 — TENANCY enforced on exports (POSITIVE)

Round 2 user (`qa-round2-...`) tried `GET /api/visits/cmoq6q5s4000p01qqhdngm77n/export/pdf`
(visit owned by Round 1 user). Response: **404**.

The visit lookup correctly filters by the session's `practiceId`.
Cross-tenant export is impossible.

### C-002 — FHIR JSON export not implemented (INFO)

`GET /api/visits/{id}/export/fhir` → 404. The export route directory
contains only `pdf/`, `docx/`, `clipboard/`, `email/`. No `fhir/`
subdirectory.

The marketing site advertises "FHIR JSON" export (in feature list).
This is either:
1. Marketing aspiration / future feature
2. The "FHIR" output is part of a different surface (e.g., a future
   Phase 8 EHR-direct integration)

**Recommend:** confirm with Kasra whether FHIR export is on the
roadmap. If yes, file as a tracking item. If marketing copy is
inaccurate, update the marketing.

### C-003 — Clipboard endpoints are POST-only (INFO, not a bug)

`GET /api/visits/{id}/export/clipboard?format=epic` → **405 Method
Not Allowed**. Looking at the sign route source (`sign/route.ts`),
clipboard outputs are returned in the Sign & Send response payload,
not via direct GET. So the GET 405 is correct API design.

If a doctor wants to "Copy for Epic" without signing, there's no
direct endpoint — they have to use the Copy SOAP button + format
switcher in the visit detail UI, which calls the sign endpoint
in dry-run mode (or just renders client-side).

## What was NOT covered (deferred)

- C5 (bulk export — multiple visits at once): no bulk endpoint
  found in source; would require building one.
- C6 (export error on corrupt visit): would require inducing
  corruption (DELETE FROM visits WHERE soapFinal IS NULL) which
  is read-only-rule-violating.
- "Export unsigned visit" — C1/C2 actually exported a NEEDS-REVIEW
  (unsigned) visit successfully. The system permits it. Whether it
  SHOULD permit it is a HIPAA / compliance call (some practices
  prefer that only signed notes can be exported, to prevent
  premature distribution of draft content). **Recommend:**
  add a P3 nitpick for Kasra to evaluate whether
  `if (visit.status !== 'SIGNED') return 403` should be added.
