# UPLOAD-AND-CERTIFIED · S4 — the onboarding walk on QA

**Date:** 2026-09-14 · **Stack:** isolated `meddoc-qa` (`127.0.0.1:9020`, synthetic DB
`meddoc_qa_test`, `MOCK_AI_CALLS=true`, vendor-severed) · **Build under test:** QA
images rebuilt from `main` (`7ef0defa` = promoted S1/S2/S3 runtime `f00956ef` + the
S3 JUDGED doc), byte-identical-to-promoted by construction (same source, same
`Dockerfile`, same layer cache as the prod build minutes earlier).

This is the **capstone verification slice** of the arc — *"any form a doctor uploads
becomes a filled copy of itself with zero human steps beyond confirming what the
machine cannot decide."* S1/S2/S3 built the machinery and shipped it (each with its
own adversarial pass, §2.5 deploy, and judgement). S4 walks the whole thing on QA as
a **stranger** (not the owner) and records, honestly, what QA can and cannot prove.

S4 changed **no runtime code** — it is a walk against the promoted build plus the
programme's own sanctioned QA tools. There is therefore **no deploy and no §2.5
declaration**; this report is the deliverable.

## Environment readiness (all green before the walk)

- QA rebuilt from the promoted tree; app + worker **healthy** on the fresh `:qa` images.
- Schema at **prod parity**: 118/118 migrations applied (the QA DB was 8 behind and
  in a partial-migration state from another lane; reset with `down -v` and migrated
  from scratch — a quiet, unused stack at the time).
- Posture confirmed on the **live containers**: `check-qa-mock-posture.sh` (vendor-
  severed + flag manifest), `check-qa-tag-isolation.sh` (isolated by digest, not
  prod's `:latest`), `check-qa-worker-flag-universe.sh` (11/11 flags).
- Arc code present in the built bundle (`deriveProseTwin`, `pdfToProseDocx`,
  `transferCertifiedDispositionsOnReupload`, `planReuploadTransfer`).

## The stranger's form

The owner's form is `WM IOV Template.docx` (a venous-duplex form; its committed copy
`tests/e2e/fixtures/sample-form.docx` is **byte-identical** to it). S4 used a
**different, synthetic blank** — `riverbend-consult-blank.docx`, a general
internal-medicine *"RIVERBEND INTERNAL MEDICINE — NEW PATIENT CONSULTATION"* with 13
labelled blanks (`Chief Complaint: ______` … `Total Time Spent: ______`), **0 content
controls**, no patient data. It is authored, fixture-class, non-PHI, and clearly not
the owner's — the point being to prove nothing is special-cased to WM IOV.

## Part A — the onboarding UI walk (signup → upload → first visit → export)

Driven headless (bundled Chromium, `--no-sandbox`) against `:9020`. All states
captured as screenshots.

| step | result |
|---|---|
| **Signup** (stranger) | invite-gated (`E2E-PILOT-CODE`), `@test.dev` auto-confirms, **no email step** → one submit → logged in on `/board` as a new DOCTOR/OWNER of a fresh "Solo — …" practice. |
| **Upload** (My Note Format › "Bring a note") | the stranger's `riverbend` form uploads; the **confirm card previews the doctor's own form** (all 13 blanks) under "YOUR FORM"; "Looks right — use this format" activates it. |
| **My Note Format states** | entry → parsing → confirm-card → **home list** (format **Active · All my visits**, Standard-SOAP fallback below). |
| **First visit** | new synthetic patient (`ZZ Synthetic Walkpatient`) → specialty → Text-to-SOAP → generate. Pipeline ran **Captured → Transcribed → Drafted → Checked → Ready with zero human steps**. |
| **Export** | Sign & lock (attestation) → Sign & Deliver → DB **`status=SIGNED`**, DOCX artifact downloaded. |

**The honest fallback — the arc's safety design, seen live.** Because the twin cannot
certify under MOCK (see Part C), the visit page banner reads verbatim: *"This note
will export in the standard layout, not on your own form — the uploaded format could
not be certified for exact-form export,"* and the export is the QuillMD-styled note
(`[MOCK] GENERAL FOLLOW-UP`, 0 hits of the RIVERBEND form), **never a silent
pretend-fill**. The only human steps were the genuinely-required ones: the pre-sign
coding review and the attestation tick.

## Part B — the twin lifecycle on the real code path (the arc's core, on QA)

The twin/certify path is **not reachable through the QA UI**: the "Native template
(beta)" upload door is hidden under the promoted `SETTINGS_SIMPLE_ROW` flag, and the
"Bring a note" `.docx` door under MOCK saves a *mock-parsed* styled format and does
not compile a twin (the stubbed parser returns no claimed source artifact, so
`saveNoteTemplateAction`'s `isNewUpload && sourceRef` guard is false and the compile
is skipped — a **MOCK-parse artifact, not a prod gap**; in prod the real parser
claims the source and the twin compiles + auto-certifies).

So the twin lifecycle was exercised the sanctioned way — `scripts/qa/auto-certify-on-qa.ts`
(the programme's own QA twin walk), run **with the stranger form** inside the QA
worker (real `createTemplateTwinDraft` + `runAutoCertifyTwin`, real QA DB + MinIO).
**Result: ALL ARMS GREEN.**

- **S1 derivation on a stranger's form** — the prose form (0 controls) compiled to
  **13 fields, 0 blocking**; a fresh compile is `NEEDS_CONFIRMATION`, never certified
  by compiling alone.
- **The zero-human-confirm mechanism** — with concepts present (as a real model
  supplies), `planAutoConfirm` auto-confirmed **all 13 fields, 0 declined**. *That is
  "zero human steps."*
- **Auto-certify safety** — declines concept-less fields (12/13 under MOCK; only
  `Referring Physician` self-resolves via the deterministic override); never
  partial-certifies; the round-trip proof **refuses a corrupted source artifact**;
  audit rows mark `auto:true`, name the proposing model, and carry **no** false
  `manual` (human) provenance.

## Part C — the one thing QA cannot prove, named honestly

Under `MOCK_AI_CALLS=true` the note generator returns canned text that resolves no
fields, so the lifecycle fill-gate (`fillCoverage`: ≥10 filled fields) refuses and the
**CERTIFIED end-state is unreachable on QA** — the DB correctly stays
`NEEDS_CONFIRMATION`, nothing half-done. This is a documented property of the MOCK,
not of the feature (the sanctioned script names the same ceiling in its own comments).
The full **certified → native-filled-export payoff is a real-model behaviour**,
already exercised by S3's auto-certify path in production (the S3 deploy judged 6 twin
certifications, unchanged). Per production-verification law, it is recorded here as
**UNVERIFIED-on-QA**, not as a defect, and not bought with a real patient's record.

## Verdict

The onboarding path — a stranger's signup, their own form recognised and previewed,
the My Note Format states, a first visit generated with zero human steps, and a signed
export — **works end-to-end on the promoted build**, and degrades **honestly** when it
cannot fill the own-form. The twin machinery (S1 derivation, the zero-confirm plan, the
safety refusals) runs green on the real code path. The single unprovable step on QA —
CERTIFIED under MOCK — is the documented ceiling, proven in prod by S3.

**The "My Note Format settings states" are presented to the owner for acceptance
(the class-(c) eyeball) — screenshots delivered in-session.**

## Close-out

The walk created synthetic rows on the QA DB (a stranger account, a `ZZ SYNTHETIC`
patient, one signed synthetic visit, twin-walk templates) — reaped on the next QA
`down -v`. The downloaded DOCX is a filled clinical export and was **shredded** per
close-out hygiene (a filled export is PHI-class even when synthetic). Real records were
never touched.
