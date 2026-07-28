# Template Twin — absorb plan (keep / retire / integrate)

**2026-07-28. Plan only; no deletions this pass.** Built from a hand-driven QA
run, not from reading. The drive changed two of the audit's conclusions, so the
lists below rest on observed behaviour where behaviour was observable.

Decision rule applied as directed: **capabilities the shipped custom-template
pipeline already proves are RETIRED from twin, not integrated. Only what the drive
showed working AND non-redundant earns integration work.**

## The drive, stage by stage

QA stack, separately tagged image (`:twin-drive`, `SETTINGS_SIMPLE_ROW=false`),
prod's `:latest` never touched. Driven by hand as `qa-auditor@quillmd.test`
(DOCTOR) with `WM IOV Template.docx` — the accepted blank fixture.

| # | Stage | Result | Evidence |
|---|---|---|---|
| 1 | UI renders once unfolded | ✅ | "Native template (beta) · Upload .docx to certify", `input#native-template-file` |
| 2 | Upload | ✅ | `TEMPLATE_TWIN_SOURCE_UPLOADED` sha256 `c1852a49…`, 52884 bytes; `source_artifacts` 44→45 |
| 3 | Compile to IR | ✅ | `TEMPLATE_TWIN_COMPILED` `fieldCount: 80, tableCount: 1`, `template-docx-compiler/1.0.0`; `compiled_versions` 42→43 |
| 4 | Review lane renders | ✅ | "80 fields · 28 dropdowns · 1 table", "1 RECOGNIZED / 79 NEEDS CONFIRMATION" |
| 5 | **Certify** | ❌ **THE BROKEN STAGE** | "Certification failed. Please try again." — no new certification row, **no audit row, no log line** |
| 6 | Per-visit fill manifest | ✅ | **first ever observed at rest in any environment**: `cms4x7bx1004r01s14clhsi96`, `status=VERIFIED`, `filledCount=6`, `conflictCount=0`, `roundTripVerified=TRUE`, 49312 bytes |
| 7 | Native DOCX export | ✅ | `EXPORT_DOCX_DOWNLOADED` `nativeTemplate=true`, 49312 bytes, + `TEMPLATE_TWIN_RENDER_VERIFIED` `fieldCount: 6` |

### Naming stage 5 precisely

`"Certification failed. Please try again."` is the **generic catch-all** at
`actions/template-twin-certify.ts:220`. It is reached only when the thrown error is
NOT a `TemplateTwinLifecycleError` — the two known refusals (`CONFLICT`,
`CERTIFICATION_BLOCKED`) each have their own message. So this is an **unhandled
exception whose identity is discarded**, and neither `audit_logs` nor the container
log recorded anything.

That is the defect to fix first, and it is not the gate: **you cannot yet tell
whether the gate refused or the code threw.** Everything else about the certify
stage is unknowable until the error is surfaced.

Secondary, independent of the exception: the mapping resolver recognised **1 of
80** fields (`[template-twin:mappings] 4/80 proposals were off-registry or
unconcepted`). Even with certification fixed, a doctor faces 79 confirmations.

### Two audit conclusions the drive overturned

- **"`fill_manifests` = 0, never produced anywhere → never proven."** Wrong. One
  export produced a `VERIFIED` manifest with `roundTripVerified=true`. The table
  read empty because `template_twin_fill_manifests.visitId` has an FK to
  `transcribe_visits`, and re-seeding the fixture cascades the manifests away.
  Absence at rest was a fixture artifact, not a capability gap.
- **"Native DOCX export: 0 rows ever with `nativeTemplate=true` → dead by data."**
  Prod-scoped. QA holds 10 such rows, and the drive added another.

## KEEP — load-bearing today, or proven by the drive

| Piece | One line of evidence |
|---|---|
| OOXML ingest + fail-closed security fork | `note-template-parse/docx-to-text.ts:39` dynamically imports `template-twin/ingest-docx-source` on **every** `.docx` upload with the flag on; the flag is on in prod |
| Twin artifact storage | `pdf-native/store.ts:9` imports `resolveTemplateTwinBucket` — the shipped PDF-native feature depends on it |
| DOCX compiler → IR | drive stage 3: 80 fields, 1 table, from a real customer form |
| Native renderer + round-trip proof | drive stage 6: `roundTripVerified=TRUE` on a `VERIFIED` manifest |
| Per-visit fill engine + manifest | drive stage 6: `filledCount=6`, `conflictCount=0`, idempotent compute-once record |
| Native DOCX export branch | drive stage 7: `nativeTemplate=true`, 49312 bytes |

## RETIRE — redundant with the shipped pipeline, or dead

| Piece | One line of evidence |
|---|---|
| `assessTemplateTwinSigning` (`signing-gate.ts:460`) | 702 lines, **10 tests inside a required CI gate, zero production callers** — only its own test imports it |
| `request-security.ts` | 791 lines, **no importer anywhere** |
| `contracts.ts` | no importer |
| `template_twin_review_decisions` | table exists, **no code touches it**; 0 rows in prod and QA |
| Twin's parallel certification *lifecycle* as a separate surface | the shipped `note_templates` already owns upload→parse→activate; two lifecycles over one concept is the duplication being absorbed |
| Twin's own WM_IOV content-control fill claim | **redundant by rule**: the shipped pipeline is already fixture-proven on `WM IOV Template.docx` (28 dropdowns, `docx-content-controls.ts`), so this capability is retired from twin rather than integrated |
| `getNativeTemplateWorkspaceAction` | zero callers |

## INTEGRATE — non-redundant and shown working

| Piece | Why it earns work |
|---|---|
| Compile→certify hung off the shipped `note_templates` upload/replace flow | the twin's only genuinely unique capability is returning **the doctor's original document bytes** with values written into `<w:sdt>` content controls; the shipped path only *reads* dropdown options to constrain a prompt (`docx-content-controls.ts:48`) and `formOnlyExport` re-creates the form rather than filling it |
| The fill manifest as the per-visit pin | drive stage 6 proved it works and is idempotent; it is the record that makes "what was filled, and verified how" auditable |
| Surfacing the certify error | prerequisite for everything above — see stage 5 |

## Proposed first step (unchanged in shape, now aimed)

**Surface the certification error before touching anything else.** Replace the
catch-all at `template-twin-certify.ts:220` with a logged, audited failure that
names the thrown error, and add a `TEMPLATE_TWIN_CERTIFICATION_FAILED` audit
action. Re-run this same drive.

Success is falsifiable: the drive fails again, but the log and an audit row say
**why**. That single line decides whether stage 5 is a gate refusal (in which case
the 79-of-80 mapping wall is the real work) or a bug (in which case certification
may already be one fix from working).

Everything else in the INTEGRATE column is blocked behind knowing that.

## What is still unknown

- **Why certification throws.** The identity of the exception is discarded at the
  catch-all; no log, no audit row.
- Whether the gate is satisfiable at all with un-pinned live models, or on any form
  other than `c1852a49…` — every certification in QA used pins.
- Whether the 79-of-80 confirmation wall is inherent to the mapping registry or a
  gap in the concept registry for imaging vocabulary.
- Whether `65798574` hid the UI deliberately — ruled moot by direction; recorded
  here only because its stated reason is verifiably false.

## Drive residue (deliberately retained as evidence)

QA now holds `source=45 compiled=43 certs=10 manifests=1` (from 44/42/10/0). The
new source artifact and compiled version are the drive's own record; the manifest
is the first ever observed at rest. QA is back on `:latest`
(`sha256:8f5298100141`), the `:twin-drive` image is deleted, prod untouched.
