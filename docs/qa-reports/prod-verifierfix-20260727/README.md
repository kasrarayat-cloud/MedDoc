# Prod deploy — verifier classification + Word-preview parity (2026-07-27)

Deployed `main` @ `943a1b6f` (merge of PR #415). Rollback tags
`meddoc-pro-transcribe-md{,-worker}:pre-verifierfix-20260727`
(app `4f106bebfa64`, worker `3d15de5ddbf7`).

Images: app `f37e51e93f57`, worker `be2cc0de04a4`. Code-only — every migration on
`main` was already applied, so nothing touched the schema.

> **Commit SHA rewritten 2026-07-27.** This line originally read `889f3748`; the
> `git filter-repo` purge of the filled clinical export re-hashed every commit
> after 2026-07-26, and that object no longer exists in any ref. `943a1b6f` is the
> same commit — the merge of PR #415 — post-rewrite. Image digests are unaffected.

## Structural verification (runbook law)

| Check | Result |
|---|---|
| Container health | 10/10 healthy, RestartCount 0 |
| Image digests | running == newly built, both services |
| Preview fix in artifact | built CSS carries `.qm-npv-docx{overflow-x:hidden}` + `.qm-docxp-wrapper{transform-origin:0 0;padding-left:0;padding-right:0}` |
| Verifier fix in artifact | worker `04b-anchor-verify.ts` 1130 lines, `provenance`×4, `facts_only`×3 (was 891 / 0 / 0) |
| Flags inlined | 0 surviving `NEXT_PUBLIC_*` literals across the shipped chunks |
| Co-tenants | app 307 · pro 200 · quillmd 200 · admin 404 (adminApi 404-gate) |
| DOM presence | `/visits` 307 unauth; `/api/health` healthy |

### On marker choice

The preview fix was verified through the built **CSS**, not the JS. The obvious
marker — the `fitDocxToWidth` identifier — is useless: client bundles are
minified and the name is mangled, so it reads as "absent" after a perfectly good
deploy. CSS class names survive minification. Prod before the deploy carried
only `.qm-npv-docx{padding:8px 0}`; the two rules above are new, confirmed by
contrast against a freshly built image before anything was recreated.

## Clinical smoke — synthetic account only

Full walk on `smoke-doctor@smoke.quillmd.invalid` (own practice, `.invalid` TLD
so no mail can ever leave), patient `ZZ Smoke Fixture (synthetic — not a
patient)`. No real record was opened, signed or exported at any point.

Ultrasound visit, text-mode input (`POST /api/visits/[id]/text` → the real
L3→L6 pipeline on the deployed worker, live models, no audio). Pipeline:
EXTRACTING → DRAFTING → AUTOMATING → READY in ~60s.

**The suggestion wall is gone.** The same case that produced a banner plus 22
cards, nine of them the patient-summary section's own headings:

- `suggestedClaims` = **0**
- set-aside placeholders in the note = **0** (the bug evacuated TECHNIQUE and
  PROCEDURES / E&M)
- DOM: `review-doc-suggestion` 0, `suggestion-item` 0, `suggestions-lane` 0
- all six ultrasound sections intact, including `Technique`
  (`provenance: 'template'` — the scan protocol, never this layer's to judge)
- every measurement landed with correct laterality (R 7.0/2.4, 6.4/2.1, 5.1/1.6;
  L 8.0/3.1, 6.9/2.8, 5.6/1.2)

Signed at 17:52:00Z (`signedSoap` 1765 chars), PDF exported.

## Preview parity — measured, not eyeballed

Page width of the PDF canvas vs the Word page, same viewport:

| Viewport | PDF | Word | Δ |
|---|---|---|---|
| 1440 | 1082 px | 1080 px | 2 px (0.18%) |
| 1024 | 666 px | 664 px | 2 px (0.30%) |

Neither format scrolls sideways. The wrapper carries a live `scale(1.36)`
transform — the "never scaled" defect fixed. Before the fix the Word page landed
~20% narrower than the PDF beside it.

Screenshots: `prod-previewfit-{pdf,word}-{1024,1440}.png`,
`prod-verifierfix-review-surface.png`.

## Cleaned to baseline

`scripts/prod-smoke/clean.ts` → visits 0 / patients 0 / templates 0.
User, practice and **audit_logs preserved** (14 rows: LOGIN_SUCCESS,
TM_PATIENT_CREATED, VISIT_CREATED, VIEWED_VISIT ×5, VISIT_SIGNED,
EXPORT_PDF_DOWNLOADED, …). The downloaded signed PDF was removed from the box.

## Observations, not blockers

- The template declares `mandatedLines: ['Clinical correlation with the above
  findings is required.']` on Impression, and L4 did not emit that line in this
  run. Not a verifier regression — a demoted line would have surfaced as a claim
  or a set-aside placeholder, and there were none of either. It is a
  note-generation observation, left unfixed and named here rather than papered
  over.
- `needsReview=true` with zero claims and no `reviewReason`. Harmless in this
  run, but the pairing is odd enough to be worth a look.
- One audit row `CODING_COACH_REJECTED_INVALID_ICD` — the ICD guard doing its
  job on a code the coder proposed.
