# Word engine round-three recovery, 2026-09-27

Status: recovered repairs complete; final affected checks pass and the
independent paired-side refutation is closed. Local branch only, no deployment
or provider calls. Broad compatibility remains unqualified.

Worktree: `/opt/meddoc-pro/.worktrees/v1-word`, branch `v1/word-engine`.
Recovered HEAD: `71733ae54a49f85dc0d23b43726694acbf518a72`, with the interrupted
P2 repair in `rebuild/documents/word_v3.py`. No active Word writer/test was found.
The previous session stopped at its usage limit at 15:55 UTC; it had committed
F1 and P1, then written P2 without committing. Its work and scratch were retained.

Recovery commits so far:

- `5508bfdc`: preserve and finish P2, four focused tests pass.
- `017f5f2a`: reproduce F2/F3/F4 and missing-reference F5 defects before repair.

Evidence directory: `rebuild/.runtime/word-recovery-20260927/` in this worktree.
`recovered.patch` and `recovered.sha256` preserve the received changes.
Original scratch: `/tmp/claude-1000/-opt-meddoc-pro/64d93580-8414-4553-b17d-ed04b0550ae1/scratchpad/v1/word-repair3/`.
Original execution transcript:
`/home/claude/.claude/projects/-opt-meddoc-pro/64d93580-8414-4553-b17d-ed04b0550ae1/subagents/agent-a1a71bb165abeaa6d.jsonl`.

## Repair boundary

F1 (nested controls) and P1 (wrapped cells/rows) were already committed. Their
code is reused, with targeted mutation proofs. The recovered P2 repair attributes
block-wrapped paragraphs to their cell and refuses an isolated option that would
otherwise inherit an entire row's question. Existing DEV captures show D28 loses
52 such fields and gains 52 explicit manual-mapping notes; the other 39 forms are
unchanged in those captures. These refusals are not automatic successes.

The current repair qualifies newly detected questions with their printed side
from another row cell, a side-bearing column heading, or a governing Word/plain
colon heading. Existing mappings, finalized exports and hashes are not rewritten.
It replaces internal paths in duplicate context with printed text and line/row
numbers, draws text fields as `[text field]`, and checks control/legacy/cell
references as well as glyph references before mapping confirmation.

The first complete v3 workflow run found a P2 regression: two independent Yes/No
groups under Right knee / Left knee column headings were refused as incomplete
row options. The repair recognizes a complete Yes/No group under its own
non-option column heading and retains that heading in the question identity.
The failing run is retained in `core-v3-first-green.log` despite its historical
filename: it is a **failed** run (73 passed, one failed), not green evidence.
Likewise `documents-first-green.log` failed with two option-label regressions;
these were repaired by excluding actual answer options from governing side labels.

## Corpus provenance audit — metadata only

The sealed full-manifest hash matches the committed manifest. There are 60
distinct frozen file hashes and 26 source groups (40 development, 20 holdout).
Source groups and lineage identifiers are disjoint across development, holdout
and qualification sets. All 80 metadata records carry an authorization basis;
this audit did not independently re-adjudicate those legal/source claims.

There are **44 distinct lineages** in the frozen 60 (30 development, 14 holdout),
with at most two files per lineage. Metadata therefore does not by itself prove
60 independently authored templates. The stored `coverage_declared_60` values
count lineages, while the file-level family denominators are larger:

| Family | Tagged files in 60 | Distinct lineages |
|---|---:|---:|
| F1 | 27 | 19 |
| F2 | 40 | 30 |
| F3 | 25 | 20 |
| F4 | 35 | 26 |
| F5 | 52 | 39 |
| F6 | 36 | 29 |
| F7 | 15 | 11 |
| F8 | 8 | 7 |
| F9 | 23 | 19 |
| F10 | 40 | 29 |

Legacy originals D19, H03, H20 and qualification Q07 have no family tags. The
manifest, failed files and first-pass results remain unchanged. No holdout or
qualification document file was opened in this recovery (a cached historical
holdout excerpt was exposed during metadata schema inspection, disclosed below). The prior 18/20
export-harness result is limited historical evidence; known control-reading
false greens mean it does not establish complete workflow or native Word
acceptance. No compatibility percentage has been rescored here.

Legacy D19 was already converted by LibreOffice during the original development
run. Its original `.doc` remains at the manifest hash
`46f4c7cffa95fa64e34e51a6ced30857084b4f5b3baf3626c0be9c8a6dd8d84d`;
the preserved converted `.docx` hashes to
`394eaa6eb6fc4e33ab21eac78d635cb68c6d687baeb7827fef7d58ded5814219`.
The old frozen development result recorded 17 expected areas, two correct,
12 missed, three wrong and three extras: automatic success was false.
Ordinary/long renders retained two pages with no machine-reported overlap or
missing text. This limited render result does not establish semantic/control
fidelity or native Word acceptance. The application still refuses binary `.doc`
at upload and asks for an unprotected `.docx`; it has no production conversion
path. A historical converted-file experiment must not be called `.doc` support.

## Bounded supplemental provenance proposal

Metadata filtering of the existing 321-row candidate pool finds 103 records
marked strong-authority/blank across 56 unused lineage identifiers, after
excluding all original 80 hashes and lineages and all holdout/qualification
source groups. Their local paths exist. All 56 are NIH/NINDS CDE modules from
one existing development source. The metadata is evidence of available
candidates, not independent verification of authorship or licence authority.

`supplemental-corpus-proposal.json` in the evidence directory records a proposed
16-file supplement and all eligible metadata. The selection is deterministic
(one DOCX-preferred, SHA-sorted representative per new lineage, iterated by
source group), uses no parser output, and is **not frozen or scored**. Original
60-file membership and every first-pass result remain unchanged. An expanded
76-file record would contain 60 distinct lineage IDs, subject to independent
authorship review; it cannot replace the original denominator or erase its
failures. Original per-source/NIH caps cannot be claimed for this expanded set.

Before freezing a supplement: independently reject cosmetic/disease variants
mistakenly split into different lineage IDs, adjudicate each recorded authority,
establish original answer areas/render ground truth without candidate mappings,
and predeclare the supplemental scoring and its relationship to the unchanged
60-file and unseen qualification requirements. This bounded preparation is
available offline; acquiring 16 new external forms is not yet demonstrated
necessary. No supplemental document contents were opened or mapped here.

Provenance limit: the first candidate-pool schema inspection printed its first
record, including a cached CMS ABN text excerpt from historical holdout H19.
That holdout had already been used in the prior campaign; the excerpt did not
inform a repair. No qualification content was viewed. Subsequent analysis
projected metadata fields only.

## Safe continuation

The required document modules and `core.tests` completed on the candidate before
the final paired-side refinement. The final affected Word module/workflow run
passed **152 tests** in 125.333 seconds; unchanged checks are reused. The lead
independently verified the final paired labels and actual export destinations:
Right and Left answers reach their own cells without overwriting a neighbour.
No other concrete defect was found in that bounded finished-diff inspection.
The dedicated Word test environment is sourced from
`.../scratchpad/v1/env/word-testenv.sh` (never print it); its PostgreSQL port is
55704. Run one Word database test process at a time. Retain all logs, scratch and
failed outputs. No push, merge, deployment, paid provider validation, corpus
qualification campaign or lock removal is authorized by this handoff.

After integration, retain this source-bound evidence and run only required
integration/changed checks. Broad custom Word
qualification, native Word checks, model verification and real-data release
gates remain open; this document does not claim V1 or Word compatibility ready.

## Verification retained during final refutation

The frozen candidate before the paired-cell refinement passed all 177 required
document tests and all 1,218 core tests (nine skips). Logs are
`documents-final.log` and `core-final.log`; this evidence is reused for unchanged
paths. The earlier interrupted core run is explicitly incomplete even though
Django printed `OK` after SIGINT (`core-superseded-interrupted.log`).

The independent lead refuter then supplied a concrete paired-cell counterexample:
`Right | Effusion: ____ | Left | Effusion: ____` gave both questions the label
`Right — Left — Effusion`. The received reproduction and failing tracked test
are retained as `paired-sides-red.json` and `paired-side-test-red.log`. It is a
clinical identity defect; the earlier suite pass did not discharge it. A bounded
DEV diff of the first narrower implementation found six D29 shared-row questions
losing their printed side; that intermediate result is also retained. Final
scope uses the closest preceding printed side in a row, with trailing scope
bounded by another answer area. It does not combine opposing row sides.

Twelve source mutation proofs were killed before this final refinement, with
source bytes restored/unchanged. A separate confirmation mutation refused all
five non-glyph reference kinds. A final closest-side ordering mutant is also
killed by the paired-cell regression. These are targeted mechanism checks, not
corpus or clinical-answer qualification.

## Independent payment refutation (separate stream)

A bounded read-only source review of the payment admission checker found that
unexpected statement triggers escaped its unexpected-row-trigger check. A
transactional synthetic fixture proved the checker returned no failures while
a privileged AFTER INSERT statement trigger changed an input `livemode=false`
to stored `true`. The fixture used Word's dedicated PostgreSQL port 55704,
database `postgres`, and always rolled back; no production table was accessed.

The payment agent repaired that catalog gap. Re-running the exact original
probe showed the clean baseline still passes, while the hostile catalog returns
`unexpected_statement_triggers:core_payment` both before and after insertion.
The privileged mutation remains possible if an operator deliberately ignores
the refusal; this check does not constrain an arbitrary database owner. The
finding is closed in that limited, accurate admission-checker threat model.
Probe and before/after logs are retained in the evidence directory. Payment
stream source/commit ownership remains with `v1/blockers`.

## Final DEV comparison and limits

This was a bounded, unscored detect/outline comparison of the existing 40 DEV
files, including the previously converted D19. No generation calls, export
campaign, holdout opening, first-pass rewrite or corpus requalification occurred.
Every intermediate capture/diff remains in the evidence directory.

Against the recovered baseline: 29 forms have changes, 52 fields are explicitly
refused on D28, zero fields are newly added, 868 fields change identity/context
metadata, and 1,320 outline rows change preview/reference metadata. The final
closest-side refinement is identical on this DEV snapshot to the candidate
before the paired-side counterexample (`closest-only-dev-diff.log`: `TOTAL {}`).
That establishes the narrow regression comparison only. It is not a measured
success rate or rendered/export/native Word acceptance result.

The final product source fingerprints are:

- `documents/word_v3.py`: `7987013353275805e4fcb2a2c0e7d6bc5e0bd7928772fcd4d13ff1370be0bc9f`
- `core/v3_mapping.py`: `25547aeb0e1bb8ad82d6ffb882e707d708b27a611e4b7b0d5ba60fad41c26376`

Selected synthetic reproductions, final checks, mutation proof and an index of
every retained runtime evidence file are committed under
`docs/rebuild/v1/word-round3-evidence-20260927/`. Full runtime logs and all prior
scratch remain in place. No active Word test or provider process remains.

The remaining Word launch work is measured broad compatibility on an adequately
independent corpus, complete original/export render and native Word/control
acceptance, and any defects that those checks demonstrate. Safe ordinary-note
clinical generation and the selected model are separate release-stream gates.
No stronger model, these unit checks, or explicit refusals establish those gates.
