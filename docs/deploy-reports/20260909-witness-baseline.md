# PRE-DEPLOY WITNESS BASELINE — the mammoth round-trip

**Captured 2026-09-09, BEFORE the deploy of `2d33a226`, and committed so the
post-deploy comparison has one correct answer fixed while the evidence did not
yet exist.**

## THE MEASUREMENT

`docker exec meddoc-pro-transcribe-md-worker-1` → `compileTemplateDocx` over the
**blank tracked fixture** `WM IOV Template.docx`:

```json
{"ok":true,"fields":80,"tables":1,"unsupported":0,"structureSha256":"37813a6031d4ae56"}
```

## THE DECLARED EXPECTATION AFTER THE DEPLOY

**Byte-identical.** The fixture does not change and the compiler's inputs do not
change; only the dependencies underneath them do. So:

| field | must be |
|---|---|
| `ok` | `true` |
| `fields` | **80** |
| `tables` | **1** |
| `unsupported` | **0** |
| `structureSha256` | **`37813a6031d4ae56`** |

⚠️ **ANY MOVEMENT IS THE FINDING.** Eight of the HIGH advisories are in the
**docx path**, which is the path every other passenger in this deploy serves. A
version number moving proves a package changed; it does not prove the document
pipeline still works. `structureSha256` is the strongest of these rows because
it is a hash of the parsed structure — a silent change in how the new `xmldom`
walks the document moves it, where a field count might not.

## WHY THIS IS A CONTROL AND NOT DECORATION

It was run **before** the deploy and it PASSED, so the instrument is known to
work on this stack. A post-deploy failure therefore means the deploy, not a
broken witness. A witness first run after the change cannot tell those apart.

## ⚠️ THE FIXTURE IS BLANK, AND THAT IS NOT INCIDENTAL

`WM IOV Template.docx` is the customer's BLANK form — headings, dropdown content
controls, letterhead, **no patient data** — and a recorded, accepted tracked
fixture. **A real doctor's visit is never a smoke target**, not to confirm a
deploy and not once. The round-trip is compile-only: nothing is signed, adopted
or exported, and no visit row is read or written.
