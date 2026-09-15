# RULED MUTATION DECLARATION — RULING C (post-#325): certify + activate the owner's colon operative note

**Committed before the act.** Runs INSIDE `transcribe-md-worker` on the deployed
`8a16f50c` image (guard 3: container revision == this tree's HEAD via the docs-only
carry-forward). Invocation, from the worktree root:

```
bash /opt/meddoc-pro/scripts/run-ruled-mutation.sh \
  --declaration docs/foundation/mutations/2026-09-15-certify-colon-325.md \
  --in transcribe-md-worker -- \
  npx tsx scripts/certify-colon-323.ts \
    cmo5ye2nm000c01s3ofudqzi6 kasra.rayat@gmail.com cmo5ye2nf000b01s3q0xlkaxb cmu1tpvsj000501o5dd4yrh4b [inspect]
```

## The act (RULING C, 2026-09-15) — now UNBLOCKED by #325

The RULING C inspect rehearsal proved #323/#324 fixed the colon-section mis-mappings
but three S2 gaps blocked auto-certify. The owner directed the #325 slice, now deployed:
the numbered findings/recommendations slots carry `procedure.findings`/`.recommendations`
via the `pdfsec:` tag (and distribute), PREOPERATIVE DIAGNOSIS is fielded to
`procedure.preop_diagnosis`, and DD/DT map to the dictation/transcription dates. So the
auto path now concepts EVERY field; only the record-derived headers decline (the #247
human-confirm the ruled act performs, as #319 did), and the form certifies + activates.

- doctor `cmo5ye2nm000c01s3ofudqzi6` (kasra.rayat@gmail.com), practice `cmo5ye2nf000b01s3q0xlkaxb`
- source / prior active: `cmu1tpvsj000501o5dd4yrh4b` ("Colonoscopy Operative Note", active, twin uncertified, pdfNativeCertified=true)

## Supersede-target discrepancy — recorded (standing autonomy)

RULING C names 8e22a23d; it is already inactive. The current active operative note is
cmu1tpvsj, which this act supersedes (kept). Factual drift, not a new decision.

## Two runs, one declaration

1. **INSPECT** — mint, re-derive under the deployed #325 code, LOG the proposal + plan,
   roll back. NET-ZERO. Confirms the auto path declines ONLY record-derived headers.
2. **REAL** — mint → re-derive → carry the PDF-native canvas forward → auto-confirm the
   clinical proposals + confirm the record-derived headers → synthetic round-trip →
   certify + activate.

## Expected deltas — REAL run (baseline pre-act: note_templates=21, twin_certs=6, pdfNativeCertified=7, owner-active=1)

MUST change:
- `note_templates`: **21 → 22** — a new active "Colonoscopy Operative Note".
- `cmu1tpvsj` status: `active` → **`inactive`** (superseded, KEPT).
- `template_twin_certifications`: **6 → 7**.
- `pdfNativeCertified` templates: **7 → 8** (carried onto the mint).
- new template's compiled version: `certificationStatus` = **CERTIFIED**.
- owner active templates: stays **1**.

MUST NOT change:
- `transcribe_visits` = **70**, signed = **41** — no visit/signature touched.
- `patients` = 0.
- `8e22a23d` stays `inactive`.
- the owner's OTHER templates unchanged; no template DELETED (inspect deletes only its own mint).

## Fail-safe

certify+activate runs ONLY at the final atomic `certifyAndActivateTemplateTwin`, after
mint + re-derive + carry-forward + auto-confirm + synthetic proof pass. Any earlier
failure throws, leaving cmu1tpvsj active + a harmless draft. It ABORTS if a
non-record-derived field is declined (a regression) or the carry-forward does not carry.
