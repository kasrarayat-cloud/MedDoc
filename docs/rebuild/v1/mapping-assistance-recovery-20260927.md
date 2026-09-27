# Blank Word mapping assistance — local implementation, 2026-09-27

**Prepared and verified offline; disabled by default. Not deployed, model-qualified,
or evidence of broad Word compatibility.** No provider requests, patient data,
purchases, clinical records, production migrations or activation were involved.

Worktree: `/opt/meddoc-pro/.worktrees/v1-mapping-assistance`; branch
`v1/mapping-assistance`; base `0d90fa48104cf820743f000d6d47a59f8f6daa81`.
The parent release has subsequent Word/notes changes; integrate their unions
after independent finished-diff refutation. This branch does not replace them.

## Implemented path

An ordinary v3 Word upload can request a blank-only mapping proposal, see every
source-area verdict and unresolved area, correct fields on the existing mapping
page, resolve areas explicitly, confirm a new immutable mapping, then use the
normal encounter review/finalization/export workflow. Both
`QUILLMD_MAPPING_ASSISTANCE` and `QUILLMD_MAPPING_ASSISTANCE_LIVE` default off.
Fixture mode is visibly labelled and makes no semantic recognition claim.

- The isolated parser supplies full source strings, slot identities, controls,
  heading/row context and options. The compiler refuses oversized requests
  rather than shortening text. Template text is untrusted data.
- Strict proposal envelopes require exactly one verdict for every original
  field and source slot. Deterministic source binding refuses invented slots,
  unsupported kinds/options and overlapping destinations. Rejected replacements
  preserve original fields and become visible unresolved review items.
- Original versions, source hashes and prior exports remain intact. Unresolved
  areas block confirmation; manual resolution/correction is recorded as assisted.
- A nullable mapping-version scope extends the existing Job and financial
  lifecycle. A database constraint requires exactly one scope. Append-only
  migration 0022 binds tenant/source/version/config and prevents scope changes;
  its reverse refuses to erase mapping operations. No fake patient, encounter
  or separate ledger is introduced.
- Quotes bind user, version, configuration and request hash. The worker rechecks
  profile, access, source and latest version. It has one native submission with
  retries disabled. Proven local failures release holds; uncertain submission
  outcomes keep the operation and hold for reconciliation.
- Real response identity/stop/schema are checked before adoption. Receipts precede
  parsing, settlement and adoption; known invalid output uses existing platform
  absorption. Admin/billing/audit/drain paths understand the mapping scope.

## Finite verification and retained failures

All attempts are retained in the [evidence directory](mapping-assistance-recovery-20260927-evidence/).
`manifest-sha256.json` hashes the artifacts (DOCX/PDF binaries remain local, as explained in `LOCAL-BINARIES.md`); `source-sha256.json` identifies the
source under review. Logs include the synthetic Django staticfiles warning;
that is not a production static asset check.

| Attempt | Actual outcome |
|---|---|
| focused-first | 11 errors: invalid test inference-region value; no provider submission |
| focused-second | 11 passed, 17.011 seconds |
| focused-third | Interrupted after 8 of 16, 16.581 seconds; **not a completed pass**, regardless of unittest's printed OK |
| focused-fourth | 16 total, 4 errors: stale fixture configurations in live-mocked methods; refused before provider construction |
| focused-fifth | 16 total, 1 error: mapping financial view needed `Job.department_id`; repaired |
| focused-sixth | 20 passed, 42.102 seconds |
| affected-regressions | 380 passed, 189.939 seconds; one finite run of mapping, v3 workflow, billing lifecycle/policy/boundary/dedup/R5, security, admin, Sonnet profile/settlement modules |
| final-mapping | 21 passed, 47.431 seconds after UI-only changes; schema dry-run: no changes detected |
| constructor-before | Independent root counterexample reproduced: client construction failed before submission, but operation held funds in reconciliation |
| constructor-after | 4 passed, 10.786 seconds: exact root probe, persistent regression, real submission-timeout control, successful mocked-response control |

The interruption was deliberate before the then-unmocked helper path could run.
The helper now always compiles a fixture response and every test denies
unmocked Anthropic client construction. Individual native transport tests replace
that denial with explicit mocks. These are request/accounting proofs, **not
actual Sonnet 5 behavior**. The constructor repair uses shared NoProviderRequest
only before the transport boundary; exceptions from `messages.create` still
retain an unknown outcome. The 380 checks were not needlessly repeated after
the UI and this focused repair.

The synthetic positive workflow adds an intentionally omitted Plan field, reviews
and confirms its mapping, saves clinician corrections, finalizes, downloads, and
checks the recorded Word export hash and intended table cell. Missing and long
answers are separately checked against that destination and preserved neighbors.

## Rendering

The existing local `gotenberg/gotenberg:8` image
`sha256:4bd4489d15b7326143e5575c789d93f675f77d85dc857900dd28ae1591d55a4b`
rendered the retained synthetic original, ordinary export, missing answer and
long answer using `--network none`, user 1001, a read-only synthetic input bind
and an isolated output directory. No pull or host changes. Permissions were
changed only on those isolated render directories/copies.

- Pages: original 1, ordinary 1, missing 1, long 2.
- Every original word remains in source order; entire ordinary and long answers
  are in the rendered text layer. All 80 repeated long-answer phrases survive.
- The existing rendered-character check reports zero overlap pairs for each.
- All five rendered pages were visually inspected: ordinary answer in the Plan
  cell, missing output unchanged, long row reflows onto the next page; History,
  instructions and the blank signature remain visible. No clipping or overlap
  observed in this synthetic case. This is **not native Microsoft Word evidence**.

The captured review page was rendered with all browser network requests denied at
1440px and 390px. Both have seven visible unresolved areas, zero unlabeled
controls, no body overflow, and resolution controls 760px/348px wide. Full-width
sections replace the initially cramped table. Both final screenshots were
inspected. Captured durable HTML has synthetic quote/CSRF values redacted and HTML/rendered-text trailing whitespace normalized; original
local captures remain in scratch. The first renderer attempt's wrong CSS path
error is retained alongside repaired and final results.

## Limits and next safe action

Source binding cannot establish semantic correctness of a model's destination or
`not_answer` judgment. All verdicts remain visible for clinician review, but
actual automatic recognition requires the authorized independent corpus and live
model qualification. This implementation does not increment that denominator,
tune a holdout, establish native Word behavior, or qualify the full V1 product.
It adds no new document writer or legacy `.doc` conversion. Existing v3 writer
limits remain; legacy/qualified WM backends are outside this operation.

The request budget uses a conservative serialized-byte bound, **not a native
Sonnet tokenizer count**. Live account support, exact-model behavior, agreements,
budget admission and independent qualification remain gates before enablement.
No prior campaign ticket or spending authority is reused.

Parent next action: independently refute the finished diff, union with current
Word/WM release work (especially Job dispatch and mapping review hooks), run only
missing integration checks, and retain flags off. No push, merge, service restart
or deployment has occurred. Local scratch and all attempts remain under
`rebuild/.runtime/mapping-assistance-20260927/`; the fixture test environment is
the previously authorized PostgreSQL 55702, with no currently running test
process at report preparation.

The clinical-document commit hook rejected the synthetic DOCX/PDF evidence path.
No override was used; those binaries remain in both local evidence and runtime
copies, while hashes, generators, extracted text and screenshots are committed.
