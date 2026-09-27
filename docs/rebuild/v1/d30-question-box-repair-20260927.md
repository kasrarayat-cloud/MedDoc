# D30 separate question and answer boxes — bounded development repair

Status: **local candidate; independent finished-diff refutation pending**. No deployment,
provider call, qualification campaign or corpus result replacement occurred.

Worktree: `/opt/meddoc-pro/.worktrees/v1-word-d30`, branch `v1/word-d30`.
Base: `0b0395a0922f81f5a38526802136197a4bb74b28`.
Engine SHA256: `326a4baf7d3331add09f36f78e05d66a8fb75acd4e10bd1c2c952447835efbd1`.

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

## Next safe action

Refute this frozen finished diff independently, focusing on source/destination
ownership, multiple questions, section scope, border precedence and preservation
of existing fields. Integrate only after verified findings are repaired. Preserve
the candidate, failed evidence and pending V1 blockers. No paid authority was used;
the isolated PostgreSQL 55702 test database was removed normally. No task process
or deployment operation remains active.
