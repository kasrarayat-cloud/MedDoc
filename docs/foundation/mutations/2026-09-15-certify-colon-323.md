# RULED MUTATION DECLARATION — RULING C: re-derive + certify + activate the owner's colon operative note (#323/#324)

**Committed before the act.** Runs INSIDE `transcribe-md-worker` on the deployed
`0deef5d6` image (the runner asserts container revision == this tree's HEAD via the
docs-only carry-forward). Invocation, from the worktree root:

```
bash /opt/meddoc-pro/scripts/run-ruled-mutation.sh \
  --declaration docs/foundation/mutations/2026-09-15-certify-colon-323.md \
  --in transcribe-md-worker -- \
  npx tsx scripts/certify-colon-323.ts \
    cmo5ye2nm000c01s3ofudqzi6 kasra.rayat@gmail.com cmo5ye2nf000b01s3q0xlkaxb cmu1tpvsj000501o5dd4yrh4b [inspect]
```

## The act (RULING C, 2026-09-15)

Re-derive the owner's `Colonoscopy_Operative_Template.pdf` under REGISTRY-3 (#323) and
the #324 affordance amendment, AUTO-CERTIFY through the real path, ACTIVATE it as the
operative note (superseding the prior active, KEPT).

- doctor `cmo5ye2nm000c01s3ofudqzi6` (kasra.rayat@gmail.com), practice `cmo5ye2nf000b01s3q0xlkaxb`
- source of the PDF + structure / prior active: `cmu1tpvsj000501o5dd4yrh4b` ("Colonoscopy Operative Note", active, twin NEEDS_CONFIRMATION / 0 certs, pdfNativeCertified=true)

## ⚠️ SUPERSEDE-TARGET DISCREPANCY — recorded, not surfaced (standing autonomy)

RULING C names **8e22a23d** as the supersede target. That is the world as of the
ruling; the world moved. 8e22a23d is **already inactive** (since 2026-09-12); the
current active operative note is **cmu1tpvsj** (a re-upload activated 2026-09-14 whose
twin was never certified — the auto-certify DECLINE that REGISTRY-3 fixes). The
ruling's INTENT — the owner's colon form as the active, CERTIFIED operative note — is
served by superseding whatever is active (cmu1tpvsj); 8e22a23d stays inactive/kept.
Factual drift, not a new product decision.

## Two runs, one declaration

1. **INSPECT** (arg `inspect`): mint a draft, re-derive under the deployed code, LOG the
   model's REGISTRY-3 proposal + auto-confirm plan, then ROLL BACK (delete the draft).
   **NET-ZERO** on note_templates / certs / activation. (Leaves one orphaned twin
   source-artifact row + its MinIO object — a blank-form prose-DOCX derivative, no PHI;
   noted, not reconciled.)
2. **REAL** (no `inspect`): mint → re-derive → carry the PDF-native canvas forward →
   auto-confirm the model's clinical proposals + confirm the record-derived headers
   (the #247 human confirm, authorised by this ruling as #319 did) → synthetic
   round-trip → certify + activate.

## Expected deltas — REAL run (baseline captured before deploy: templates=21, twin_certs=6, pdfNativeCertified=7, owner-active=1)

MUST change:
- `note_templates`: **21 → 22** — a new template, status `active`, "Colonoscopy Operative Note".
- `cmu1tpvsj` status: `active` → **`inactive`** (superseded, KEPT — not deleted).
- `template_twin_certifications`: **6 → 7** — the new twin's certificate.
- `note_templates` with `pdfNativeCertified=true`: **7 → 8** (carried onto the mint).
- owner active templates: stays **1** (mint active; cmu1tpvsj inactive).
- the new template's compiled version: `certificationStatus` = `CERTIFIED`.

MUST NOT change:
- `transcribe_visits` = **70**, signed = **41**, `patients` = **0** — no visit/patient/signature touched.
- `8e22a23d` — stays `inactive` (untouched).
- the owner's OTHER templates (GI consult, etc.) — unchanged.
- no template DELETED (INSPECT deletes only its own throwaway mint).

## Fail-safe

certify+activate runs ONLY at the final atomic `certifyAndActivateTemplateTwin`, after
mint + re-derive + carry-forward + auto-confirm + synthetic proof all pass. Any earlier
failure throws, leaving `cmu1tpvsj` active and a harmless leftover draft. The script
ABORTS if a non-record-derived field is declined (REGISTRY-3 incomplete) or the
PDF-native carry-forward does not carry.
