# D30 separate question and answer boxes — bounded development repair

Status: **local candidate; independent finished-diff refutation pending**. No deployment,
provider call, qualification campaign or corpus result replacement occurred.

Worktree: `/opt/meddoc-pro/.worktrees/v1-word-d30`, branch `v1/word-d30`.
Base: `0b0395a0922f81f5a38526802136197a4bb74b28`.
Engine SHA256: `d4d82856ca066c07b537f3c3d28f9a10b1b3bcbf441d516e6ba636699ea8bc77`.
First frozen candidate: `75e545b2a6469b0d188c779f3c4ee9af02dfc7f5`;
its refuted evidence remains preserved.

## Independent expected areas and demonstrated failure

Custodian record `053-original-dev40-exact-rights-ledger.json` admits 33 original
development DOCX files for internal offline synthetic replay. D30 is among them:
the Ministry of Justice/HMPPS blank conditional discharge report, under the exact
publisher OGLv3 scope recorded by the custodian. Integral branding is preserved;
this is neither endorsement nor clinical use. The seven held development files,
holdout and qualification contents were not executed or opened for this task.

D30 original SHA256 is
`fdeafbee872f987325e544953ad930e8e8db8ed6bd30ccab0375f2b50ecbff2f`.
The existing independent expected map has 62 areas. Original XML confirms **32**
empty single-row, single-cell tables with independently annotated destinations.
Both the frozen first-pass map and preserved round-3 map omit every one of those
32 cell destinations. The current sandbox reproduced the omission before editing:
42 detected fields; A25's directly adjacent table box was absent. The service had
two generic warnings, with no warning identifying these omitted boxes.

The historical result remains unchanged: 28 correct, 33 missed, one wrong and
13 extra fields; document automatic success **false**. Its old `export_ok=true`
describes exports of the incomplete detected map, not a complete clinical workflow.
No percentage or corpus denominator was recomputed here. Original development40
and original60 denominators remain unchanged.

## Repair and its boundary

The new detector rule binds an entire printed question/request to the following
empty, unclaimed, unmerged one-cell body table. It permits at most two plain empty
spacers and requires explicit four-sided borders, including a simple referenced
table style. Direct cell/table `nil` borders override the style. It does not infer
conditional or missing style definitions. It retains explicit outer Part/Section,
the following role heading and the current subheading, and reuses the existing
cell writer. No generation, worker, billing, view, model or export writer changed.

An unassigned box is reported with its source location and available complete
question. Long questions above the existing 300-character mapping limit are not
shortened. Option tails, cross-question references, signing/consent wording,
ambiguous instructions and structural boundaries remain visible for review.
Manual correction remains assisted completion, never automatic recognition.
The D19 paragraph adjacency and protected signing/export gates remain intact.

A bounded self-refutation found an introduced omission before freezing:
`Patient name: __________. What symptoms changed?` followed by a box suppressed
the pre-existing inline name field. The new rule now refuses such a compound
paragraph, retains the old inline field and flags the separate box for review.
The before result and repaired control are retained.

The mandatory independent pass then found two introduced scope failures on that
first frozen candidate: a custom paragraph style based on Heading 1 discarded a
“Donor” heading, and a two-paragraph medication question kept only the second
request about doses/frequency. Root and author independently reproduced both.
The follow-up resolves paragraph style ancestry locally, holds unknown/cyclic
ancestry visibly, and refuses multi-paragraph question blocks while displaying
both complete source paragraphs. Page-break-before spacers and conditional table
borders inherited from ancestor styles also receive explicit review. These are
new-rule guards; the shared heading/detection rules are unchanged.

## Measured result and checks

- **26 new destinations**, each matching one independent expected area and its
  entire question wording. D30 now has 68 detected fields. All 42 old fields are
  unchanged except for keys assigned by fresh document-order enumeration; no
  stored mapping version was modified.
- **Six of the 32 boxes remain unassigned and visible**: A21 option-tail box,
  A23/A35 questions longer than 300 characters, A26 reference to another question,
  A40 line-manager instruction, and A44 where the conservative existing initials
  vocabulary also matches “initial report”. This is a known refusal, not coverage.
- 35 affected engine checks passed in 11.004 seconds on the first repaired rule.
  The final inline-answer guard's six focused checks passed in 1.242 seconds.
- Synthetic fixture and original D30 each passed missing, ordinary and long
  upload → mapping review/confirmation → mocked ordinary-source-unit worker →
  clinician correction → finalization/export: two test methods, 18.404 seconds.
  The tested D30 answer destination is A25 (`b/tbl[8]/tr[0]/tc[0]`). Provider unit
  selection is mocked; validation, worker, review, storage and export are real.
  An ordinary unlabelled source sentence was accepted and retained whole.
- The original hash, every unchanged package part and every other body block
  were checked. Recorded finalized export hashes equal actual output hashes.
  Missing answers remain blank; an ordinary correction and a 90-statement long
  clinician correction reach only the intended cell.
- Four pinned, networkless LibreOffice renders: original/missing/ordinary 12 pages,
  long 13 pages; zero detected character-overlap pairs in each. Original and missing
  page 5 PNGs are byte-identical. The ordinary answer is fully visible. All 90 long
  statements are visible across pages 5–6; the full long answer is not contiguous
  in extracted PDF text because a page footer intervenes. That raw false result
  remains recorded. Visual comparison of those affected pages found no clipping,
  lost neighbouring question or altered branding.
- The final guarded candidate produces exactly the same D30 fields, warnings,
  contract and original digest as the successful workflow/render candidate. Those
  unaffected results are reused. Native Microsoft Word checks were not performed.

The independent eight-artifact probe was replayed unchanged: both direct and
inherited Donor headings now retain Donor, the compound question refuses with both
source paragraphs visible, the ordinary positive remains mapped, and direct nil,
inherited conditional borders, page-break spacers and inline-answer ambiguity
remain refused. **40 final affected engine checks passed in 11.772 seconds**;
the complete output is retained separately.

This is **not full D30 success**: six boxes, pre-existing extras/options/type defects
and whole-document clinical acceptance remain unresolved. Only A25 received the
complete missing/ordinary/long rendered workflow here; the other new destinations
have independent map/structure checks. This does not qualify other documents or
the structural family, and does not close broad custom Word V1 acceptance.

## Evidence and instrument corrections

Private runtime, preserved:
`/opt/meddoc-pro/.worktrees/v1-word-d30/rebuild/.runtime/d30-repair-20260927/`.
Read-only diagnostic predecessor:
`/opt/meddoc-pro/.worktrees/v1-host-readiness/rebuild/.runtime/development-docx-diagnosis-20260927/`.

The runtime contains original and final maps; source-area comparisons; actual
DOCX exports and recorded workflow evidence; raw failures; renderer command,
logs/PDFs/PNGs; source and artifact hashes; and repeatable synthetic harnesses.
Relevant render PNGs are `render-output/original-05.png`, `missing-05.png`,
`ordinary-05.png`, `long-05.png` and `long-06.png`.

Preserved instrument corrections: two synthetic assertions originally included
trailing whitespace removed by the reader; the first D30 diagnostic queried
`notes` instead of the service's `warnings`; empty notes correctly queued no job
in the first missing-answer workflow; the release venv lacked pypdfium2, so the
existing tools venv was used without installation. Logs retain all these outcomes.

**Capture limitation:** the first failed missing-case run also produced successful
ordinary/long partial captures. The corrected retry overwrote those partial
captures in this new runtime. Their original bytes are unavailable; they are not
reconstructed or cited as retained first-pass artifacts. The failed run log
survives. Final captures are hash-pinned; the harness now requires a new exclusive
capture directory. No original corpus first-pass artifact or original file was
overwritten.

## Finite affected-development scope

At root's request, a passive XML/metadata prefilter examined only the 33 exact
eligible original DOCX files, verifying each original hash. It did not import or
execute the candidate engine. Eight originals have a root one-row/one-cell table:
D17, D21, D26, D27, D30, D31, D33 and D34. Seven contain nonempty prose/title/control
content in every such table, so they cannot enter this rule's empty-cell path.
The other 25 originals have no eligible table shape. **Only D30 is affected**.

Root accepted reuse of the existing D30 maps/workflow/render plus the 32 structural
exclusions. No unchanged-map rerun or new corpus campaign is needed for this rule.
This proves a narrow changed-code exposure set, not broad compatibility. The
prefilter, first over-inclusive shape result and classified result are retained
as `prepare_affected_scope.py`, `23-passive-affected-scope.json` and
`24-passive-affected-scope-classified.json` in the private runtime. The classified
proof and script are copied beside this report. All seven held files remain
unopened for this task, and the original development denominator is still 40.

## Next safe action

Refute this frozen finished diff independently, focusing on source/destination
ownership, multiple questions, section scope, border precedence and preservation
of existing fields. Integrate only after verified findings are repaired. Preserve
the candidate, failed evidence and pending V1 blockers. No paid authority was used;
the isolated PostgreSQL 55702 test database was removed normally. No task process
or deployment operation remains active.
