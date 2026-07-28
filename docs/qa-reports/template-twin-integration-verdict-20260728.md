# Template Twin — integration verdict

> **FINAL STATUS: PARKED (2026-07-28).** The verdict below stands — absorb, not
> retire — but the integrate column is **post-pilot roadmap**, not current work.
>
> **Trigger to un-park early:** a pilot doctor explicitly needs their native form
> bytes back. Nothing else. Not tidiness, not "while we're in here".
>
> **`MAPPINGS_NOT_READY` stays strict, by decision.** The certify gate refuses
> until every field has a physician-confirmed mapping, and the wall is 79 of 80
> on a real customer form. **Never weaken the gate to shrink the wall** — the
> gate is what makes a certified twin mean "a physician confirmed what each field
> means". Shrinking the wall by lowering the bar produces a certified twin nobody
> confirmed, which is worse than no twin. The work, when it comes, is the concept
> registry and the confirmation flow — not the threshold.
>
> Steady state is recorded in `AGENTS.md` → "Template Twin — the parked steady
> state". Read that before concluding anything about Twin.


**2026-07-28. Read-only audit; zero code changes.** 7 evidence lenses, 173 facts,
24 load-bearing claims adversarially challenged — **17 corrected**. A 71%
correction rate on the claims that decide the verdict is the headline finding
about this subsystem's legibility: almost nothing about Twin's status was
accurately recalled, including by the audit's own first pass.

Verified independently by the lead where the verdict turns on it.

## What it is

Takes a doctor's uploaded `.docx`, compiles it to a field-level IR, maps clinical
facts onto its Word content controls, and — past a certification gate requiring a
byte-identical round-trip proof — fills and returns **the doctor's original
document bytes**. ~15.1k lines of TS across ~50 files, 7 Prisma models, 4 applied
migrations. Persistence is entirely separate from the shipped `note_templates`
pipeline.

## State of each piece

| Piece | Exists | Reachable in prod | Tested | Real data | Status |
|---|---|---|---|---|---|
| OOXML ingest + fail-closed security fork (`note-template-parse/docx-to-text.ts:39,67`) | yes | **yes — runs on every `.docx` upload** | yes | no rows either way | **live, load-bearing** |
| DOCX compiler + native renderer (`note-template-docx/`) | yes | yes (called by ingest) | strongest coverage; real `WM IOV Template.docx` fixture | no | **the unique asset** |
| Certification gate (`template-twin/certification-lifecycle.ts`) | yes | yes | source-grep tests only, no behavioural import | prod 0 / QA 10 CERTIFIED | **unwired** |
| Certify/upload server actions (`actions/template-twin-certify.ts`) | yes | action boundary open | no test imports | no | **orphaned** |
| Certify UI (`native-template-manager.tsx`) | yes | **NO** — folded to `null` | none | no | **the blocker** |
| Worker fill step (`worker/template-twin-fill-step.ts`) | yes | invoked every visit, always declines | manifest writer mocked | `fill_manifests` = **0 in prod AND QA** | **never proven** |
| Native DOCX export branch (`export/docx/route.ts`) | yes | yes, declines | yes | 0 `EXPORT_DOCX_DOWNLOADED` with `nativeTemplate=true`, ever | **dead by data** |
| Preview action (`actions/preview-native-document.ts`) | yes | yes — no flag gate | no | no | **reachable, fails closed** |
| Sign-time gate (`template-twin/signing-gate.ts:460`) | yes | **no** — zero production importers | 10 tests in a required gate | no | **dead code** |
| Review-decision lane (`template_twin_review_decisions`) | table only | no | no | 0 everywhere | **schema-only** |

### Lead's corrections to the audit's own verdict

- **`previewNativeDocumentAction` is not caller-less.** `note-format-manager.tsx:748`
  calls it — the *shipped* manager, not the folded-out `NativeTemplateManager`. So
  a twin code path is reachable from a live production surface today. It is
  `requireSession()`-authed and returns `fail('no_native_template')` because prod
  holds zero twin rows, so it is **inert and fails closed** — but it is reachable,
  which is sharper than "orphaned", and it carries no `templateNativeDocxEnabled()`
  check.
- **The "absorption runs automatically" comment is unbacked.**
  `config/settings-simple-row.ts:19` states it; no absorption implementation
  exists anywhere in `src`. Absorption was intended and never built.

## The recollection conflict, resolved

Both remembered claims are stale, and both were half-wrong.

**"Twin native-WORD GA on 2026-07-26"** — the FLAG went on, not the capability.
`NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX=true` (`.env:96`, overriding compose's
`:-false`) and inlined in the shipped bundle. Prod's `audit_logs` holds **11**
`TEMPLATE_TWIN_*` rows across 7 distinct actions, 03:13:48 → 03:21:06 on
2026-07-26 — and they record **two lifecycle chains, not one**: a first attempt
that failed, then a second reaching `CERTIFIED → RENDER_VERIFIED → ACTIVATED`.
One actor: `smoke-doctor@smoke.quillmd.invalid`, driven by
`scripts/prod-smoke/twin-ga-proof.ts`, then cleaned to baseline. **No real
clinician's form has ever been through it.**

**"Gate blocked by isVerifiedSyntheticProof, flag OFF, do not loosen"** — stale as
fact, still correct as instruction. The gate was *tightened*, not loosened: PR
#414 fixed the **producer** (the renderer emitted no proof for legitimately blank
fields) and added a positive blank-verification requirement. The "28 proof entries
vs 80 IR fields" framing does exist in the repo — under `apps/`, which the first
grep missed.

**The fact neither recollection contained:** commit `65798574` (2026-07-26 07:14
UTC, ~4h after the GA smoke) retired the only twin-creation UI, and every running
image post-dates it. `NEXT_PUBLIC_SETTINGS_SIMPLE_ROW=true` makes
`settings/page.tsx:214` evaluate `templateNativeDocxEnabled() && !isSettingsSimpleRow()`
to false, so `NativeTemplateManager` renders as `null`. **That is why prod has zero
certifications despite the flag being on** — not a gate failure. There is no door in.

## Overlap with the shipped pipeline

Shared front door, two separate back-ends — and **already fused in two places**,
both verified by the lead:

- `docx-to-text.ts:39` → `:67` dynamically imports
  `@/lib/template-twin/ingest-docx-source` when the flag is on. Every `.docx`
  template upload in production executes twin ingest code today.
- `pdf-native/store.ts:9` imports `resolveTemplateTwinBucket` from twin storage.

**Unique to Twin:** writing values into `<w:sdt>` content controls and returning
the original file's bytes. The shipped path only *reads* dropdown options to
constrain a prompt (`docx-content-controls.ts:48`); `formOnlyExport` re-creates the
form rather than filling it; `pdf-native` covers flat PDFs only.

**Duplicated:** upload, extraction, parse, and a second certification/activation
lifecycle over 7 tables parallel to `note_templates` (6 rows, 3 doctors, 5 visits).

## VERDICT: absorb into the shipped pipeline

Not a retire: the compiler/renderer is a capability nothing else in the repo has,
and two shipped features already execute twin code, so deleting it breaks working
paths.

Not keep-and-integrate-as-is either: the product has already repudiated Twin's own
surface. The only certify UI is folded out of the bundle, `assessTemplateTwinSigning`
(702 lines, 10 tests in a *required* CI gate) has zero production callers,
`template_twin_review_decisions` has no code at all, and `fill_manifests` — the
terminal artifact, an actual filled form joined to a visit — is **0 in every
environment**. Maintaining a parallel lifecycle no doctor can enter, and that CI
cannot cover end to end, costs more than it returns.

Absorb means: twin compile+certify hangs off the shipped `note_templates`
upload/replace flow, and the parallel workspace, review lane and sign gate stop
being maintained as live surfaces.

## Concrete gaps

- **No UI entry point** — `settings/page.tsx:214`, `!isSettingsSimpleRow()` false in prod.
- **Ungated server action** — `actions/preview-native-document.ts` has no `templateNativeDocxEnabled()` check (inert today only because prod has no twin rows).
- **No behavioural test on the gate** — `certification-lifecycle.ts` (874 lines) is only source-grepped.
- **Terminal artifact unproven** — `template_twin_fill_manifests` = 0 in prod and QA; the sole writer is `fill-engine.ts:605`, and its only test mocks it.
- **One-form proof** — every twin unit and E2E test uses sha `c1852a49…`.
- **Dead** — `signing-gate.ts:460`, `contracts.ts`, `request-security.ts` (791 lines, no importer), `template_twin_review_decisions`.
- **A false comment** — `settings-simple-row.ts:19` claims absorption is automatic; it does not exist.

## Proposed first step

**QA stack only** (`meddoc-qa`, `127.0.0.1:9020`, synthetic DB, MOCK_AI): set
`NEXT_PUBLIC_SETTINGS_SIMPLE_ROW=false`, rebuild the QA image on a **separate
tag** with a compose override (never prod's `:latest`), and drive one `.docx`
through `NativeTemplateManager` by hand — the one thing no evidence shows has
ever happened.

**Success is falsifiable:** a new `template_twin_certifications` row whose
`certifiedById` is the QA doctor rather than the seeder; the **first non-zero
`template_twin_fill_manifests` row in any environment**; and an
`EXPORT_DOCX_DOWNLOADED` audit row with `nativeTemplate=true`. Any of those three
missing tells you which stage is actually broken, which no amount of reading will.

Reversible by reverting one QA env line. No prod flag, schema, or code change.

## What could not be determined

- **Whether `65798574` hid the twin UI intentionally.** Its message ("Replace on
  the row does the whole job") is verifiably false — `certify-pdf-template.ts` has
  no twin reference. **This needs a human ruling; it decides absorb vs restore.**
- Whether `fill-engine.ts` ever persists a manifest (0 rows everywhere; only test mocks the writer).
- Provenance of QA's 10 CERTIFIED rows — seeder or UI. `certifiedById` not inspected.
- Whether the gate is satisfiable with **un-pinned** live models, or on any form other than `c1852a49…`. Both the QA rows and the prod chain used pins.
- Whether the twin actions are invokable by a direct authed POST in prod — that is a mutation, deliberately out of scope.
- Whether the live OOXML security fork has ever fired in prod: it writes no rows and there is no template-upload audit action, so there is no trace either way.
