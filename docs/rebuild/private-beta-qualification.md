# Private beta qualification — 2026-09-17

This record extends the fresh application checkpoint using synthetic accounts,
notes and newly generated blank forms. The existing blank `WM IOV Template.docx`
is the previously accepted customer fixture. No old filled document was opened.
No external email or live Stripe payment is part of this exercise.

## Reproducible document matrix

Run from `rebuild/` using its existing Python environment:

```bash
python -m documents.qualification \
  --report .runtime/document-qualification.json \
  --wm-iov '../WM IOV Template.docx'
```

The first run matched **19 of 19 expected outcomes**. Four cases successfully
filled; fifteen explicitly refused unsupported or unsafe structures/answers.
Every original hash remained unchanged. The actual Landlock/seccomp adapter ran;
there were zero provider calls. Temporary generated forms and filled outputs
were removed. The JSON contains hashes, outcome codes and safe error messages.

| Exact form/answer shape | Observed result | Qualification boundary |
| --- | --- | --- |
| DOCX two-column question with empty answer cell | Filled successfully | Question retained; complete answer compared |
| DOCX placeholder split across styled runs, plus header/footer placeholders | Three fields filled | Established Word adapter, no rendered-pagination claim |
| DOCX answer of 19,000 characters | Complete answer retained | Expansion may change pagination |
| DOCX content control | `unsupported_structure` | Advanced content-control adapter needed |
| DOCX text box | `unsupported_structure` | Advanced Word layout adapter needed |
| DOCX tracked insertion | `unsupported_structure` | Review tracked changes before qualified processing |
| DOCX legacy Word field | `unsupported_structure` | Advanced field adapter needed |
| DOCX blank answer cell with exact fixed row height | `overflow_risk` | No potentially hidden answer exported |
| DOCX merged question/answer cells, no other fields | `no_fields` | No question boundary inferred |
| DOCX nested empty answer table, no other fields | `no_fields` | No question boundary inferred |
| PDF visible Helvetica 10pt multiline AcroForm text field | Filled successfully | Values, original question text and appearance stream checked |
| PDF 80pt-wide field with 40 `W` characters | `answer_overflow` | No output created; no truncation |
| PDF text answer containing Greek characters | `unsupported_characters` | Current PDF adapter is printable ASCII only |
| PDF checkbox | `unsupported_field` | Text fields only |
| PDF dropdown | `unsupported_field` | Text fields only |
| PDF printed text without interactive fields | `flat_pdf` | Field detection/manual mapping not integrated |
| PDF generated image resembling a scanned question | `flat_pdf` | OCR not integrated |
| PDF JavaScript action | `unsafe_upload` | Active document content refused |
| Accepted blank WM IOV form | `unsupported_structure` | Contains 28 Word content controls and 28 dropdown lists |

WM IOV original SHA-256:
`c1852a492221cfa0d144c9c0a60b700a7363a2cca7630aa988ee8b6329e1868b`.
The qualification script inspected and refused this original without altering it.
This establishes that the currently required real-world content-control form
does **not** work with the bounded Word adapter. Do not advertise support for it.

The previously evaluated [document SDK options](document-sdk-evaluation.md)
remain candidates. An advanced Word adapter is needed for the WM IOV controls;
PDF field detection and OCR are separately needed for printed/scanned forms.
No SDK has been licensed, purchased, integrated or qualified by these tests.
Keep the current explicit refusals until a chosen adapter passes the same
original-preservation, complete-answer and visual-review checks.

## Browser exercise

`rebuild/private-beta-browser.mjs` runs against explicit loopback doctor/admin
origins, synthetic seed accounts and a private credential file. Fixture runs use
their own database `quillmd_beta_browser` and ports 9140/9141. The live private
services remain 9130/9131 with their existing data preserved.

The script covers login/logout/relogin, exact server-side expiration of its own
test session, administrator MFA and token replay, Word/PDF uploads, mapping
versioning, missing/conflicting source handling, review/finalization, complete
exports, cross-department/organization file/API/export/result denial, individual
employee sharing, invitation reuse and the single personal welcome grant.
The new recovery flow additionally exercises password change, old-session
invalidation, token reuse and return to an authorized document after expiration.

Live mode is explicit. Each Generate/Transcribe action requires a displayed
signed quote and the run's sum of maximum reservations cannot exceed USD 1.
Actual receipts and exact 1.5× charges are checked separately. Live transcription
uses only a previously verified locally synthesized speech sample, then edits
the resulting notes through the browser. Fixture generation is zero-cost and
is never presented as live provider evidence.

Only sanitized JSON check reports are retained. Browser screenshots are not
taken. Downloaded exports and temporary forms are deleted after assertions;
new application records, originals, ledger and audit events remain intact.

Initial browser setup failures were repaired before accepting results: the test
worker command was corrected to `manage.py worker`; the invitation selector was
scoped to its own form; and the fixture database was brought through the new
payment-evidence migration after concurrent implementation advanced its schema.
Missing OTP, valid OTP and replay behavior were separately observed during that
diagnosis. Final results and exact code/runtime identity are recorded in the
sanitized reports, not inferred from a successful sign-in redirect.

### Recorded results before deployment

At 17:05:35 UTC, all **13 fixture browser checks passed** on the implementation
worktree, including the new recovery behavior. The source base was
`ddc923e873d20c6ec1c9f93a95878039ff323473` plus the current private-beta diff;
this is not a claim that the unmerged diff was running on the permanent services.
The report is `rebuild/.runtime/private-beta-browser-fixture.json` in that worktree.
A final rerun after migrations 0009/0010 and the invitation/recovery template
changes again passed all 13 checks at 17:17:05 UTC.

At 17:08:01 UTC, **five actual-service access checks passed** against 9130/9131:
doctor/admin exclusion, X-ray employee sharing, ultrasound isolation, other
organization isolation, required administrator MFA, replay refusal and logout.
The checks covered existing synthetic originals, provider results and exports
without modifying them. Three preceding actual-service checks also passed:
doctor login/logout/relogin, server-side expiration of that test session, and
upload/versioning of a new blank Word form. That broader attempt stopped before
generation when its quote parser rejected a trailing sentence period; the parser
was repaired. **No provider job or charge was created.** The reports are
`private-access-baseline.json` and `private-beta-browser-live.json` in the worktree's
private runtime. The latter deliberately records an incomplete attempt.

The permanent services had not yet been updated for the beta changes. Their
health responses did not contain a release identifier; their source tree was
the checkpoint's base commit. Post-deployment evidence must separately verify
the newly stamped release and the updated adapters. Provider calls are reserved
for that check: one synthetic transcription and one answer generation, subject
to a combined displayed reservation ceiling below USD 1.

The repeatable post-deployment command, only after that spending is authorized,
is:

```bash
QUILLMD_BETA_LIVE=1 node rebuild/verify-private-release.mjs \
  --expected-release <full-reviewed-deployment-commit>
```

It requires local `espeak-ng`, Playwright, the application's Python environment,
and its private synthetic seed credential file. Optional loopback origins,
credential path and Playwright module directory are explicit environment inputs
documented in the script. It first compares both health release identifiers with
the supplied commit. It then uploads a new blank Word form, versions its mapping,
creates a bounded local synthetic speech sample, transcribes once, saves a typed
correction, generates once, reviews/finalizes and compares the exported answers.
No live retries are automatic. The final ledger assertions require exactly two
jobs, correct provider IDs/pricing snapshots, no held reservations and total
charges at most USD 1. The same browser run checks private invitation acceptance,
the single welcome grant, password recovery, invalidated old sessions and admin
MFA. It leaves a sanitized `beta-deployed-browser-verification.json` in the
application's private runtime and removes its temporary forms, audio and export.

## Clinical-path refutation and independent retest

The final metadata/receipt diff was challenged against the claim that repeated
provider responses cannot create a second usage charge. Two counterexamples
were demonstrated in synthetic transactions and then rolled back:

1. Two jobs settled the same Anthropic request/resource IDs under two configured
   model names. Uniqueness included the model, allowing two usage rows and a
   **$0.30** total debit for one **$0.10** response instead of **$0.15**.
2. An earlier job created by the fresh application stored `msg_same` in its
   request-ID column. A new job stored `req_new` and resource ID `msg_same`.
   Separate column constraints again permitted two charges for one resource.

The defect was in the new `Usage` constraints and migration 0009. Migration 0010
now indexes canonical provider family and canonical resource identity. It does
not rewrite any earlier fresh-application receipt or import retired-system data.

The independent regression module
`core/tests/test_provider_dedup_refutation.py` passes **four tests** after the
repair: request identity across models, resource identity across models,
resource identity across earlier/current fresh-app metadata representations,
and the actual worker's repeated-response path. The worker test confirms two
durable provider receipts, one settled usage/debit, the second job held for
reconciliation, and no adoption into its encounter. A separate isolated test
database was created and dropped; no real provider was called.

Reviewed generation/worker bytes after that retest:

- `core/generation.py`: `5317a6481461d5e45c8059ad559095611daaff39e0a4046cf01e88c5b68bd2f5`
- `core/jobs.py`: `992d85a3e10b8149033e55645e5bbbe353148bf9e687d76e627cf88f964554e6`

No additional source-evidence/adoption regression was demonstrated in the
metadata changes. Word/PDF completeness and explicit refusals are bounded by
the matrix and browser cases above; they do not establish arbitrary-form or
rendered-pagination fidelity.
