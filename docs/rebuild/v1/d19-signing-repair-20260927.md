# D19 development repair and containment — 2026-09-27

## Candidate and scope

Base: `e9e44e0837ca82ede0cc24a742917f70adc9a3b6`.
Branch/worktree: `v1/word-d19`, `/opt/meddoc-pro/.worktrees/v1-word-d19`.
This is a local, undeployed repair. It does not implement legacy `.doc` conversion,
qualify the floating-initials layout, or establish broad Word compatibility.

Only the known D19 development artifact and small synthetic controls were used.
No qualification document, original, annotation or output was opened. No provider
request, purchase, production mutation, deployment or corpus acquisition occurred.
Original manifests, denominators and first-pass results remain unchanged.

## Retained identity and prior findings

- Binary original: `/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus/dev/originals/D19-46f4c7cffa95.doc`;
  SHA256 `46f4c7cffa95fa64e34e51a6ced30857084b4f5b3baf3626c0be9c8a6dd8d84d`.
- Retained normalized DOCX: same corpus, `dev/converted/D19-46f4c7cffa95.docx`;
  SHA256 `394eaa6eb6fc4e33ab21eac78d635cb68c6d687baeb7827fef7d58ded5814219`.
- Independent expected areas: `dev/groundtruth/D19-46f4c7cffa95.json`, **17**.
- Historical frozen result remains **2 correct, 12 missed, 3 wrong**, automatic
  failure. It is not a score for the repaired candidate.
- The earlier current inspection remains at
  `/opt/meddoc-pro/.worktrees/v1-retention-readiness/rebuild/.runtime/legacy-doc-readiness-20260927/d19-current-inspection.json`:
  **8** fields, including a signature paragraph assigned to “Please initial box”
  and an empty separator assigned to the combined name/date/signature captions.

## Repair

The label-followed-by-blank rule filtered out intervening tables and incorrectly
joined nonadjacent paragraphs. It now stops at an intervening block. A prior
signing-structure pass recognizes underlined writing bands followed immediately
by tab-separated signing captions. Caption types remain text/date/signature;
names and dates are not relabelled as signatures. They receive explicit immutable
write protection and a review reason because their relationship to an actual
signing act is not established by ordinary identity/date notes.

The retained DOCX contains eight anchored rectangle shapes. Some XML anchors sit
in a different row from the visible question, and two shapes share a cell. The
repair exposes each rectangle as a **placement-unresolved** initials area. It
does not assign the host cell's statement as the visual question. Blank cells in
that affected table are not inferred as writable answers; inspection notes name
the ambiguity. Existing inline blanks in printed text remain detected.

The repaired inspection exposes **17 physical areas: 3 ordinary inline blanks,
8 unresolved floating initials boxes and 6 protected signing details**. This is
not 17 correctly resolved, automatically usable fields. D19 remains an automatic
failure. The information-sheet “dated” blank is typed as a date; “dated and
signed” remains a signature.

Generation excludes protected fields. Review/save rejects nonempty protected
values. Export rediscovers protection from the immutable source, independently
of mutable field labels, kinds or copied flags. It covers primary destinations,
paragraph continuations, copies, checkbox destinations, paragraph-options paths
and table-row destinations, including ancestor/descendant overlaps.

An independent root refutation demonstrated that the initial guard omitted
`paragraph_options` secondary paths: a forged ordinary field could insert a tick
in a protected name paragraph on a form with no floating boxes. The exact class
is now pinned by a negative control independent of the floating-form refusal.
The original root RED evidence remains in root's recovery runtime directory.

## Visual failure and final containment

The first local implementation allowed the three ordinary blanks through the
complete upload → mapping review/correction → clinical review → finalization →
export workflow. Missing, ordinary and long outputs were retained and rendered.
All protected signing XML and other package-part bytes remained unchanged.

That was **insufficient**. Visual inspection of all eight rendered pages found
the long export clips the initials rectangle for statement 3 at the top of page
2: only seven of eight boxes remain visible. The existing text-only heuristic
reported zero overlaps and no missing answer prefixes for all four PDFs. That
heuristic did not detect the lost visible shape.

Final containment therefore refuses **every nonempty export** for this detected,
unqualified floating-initials class before applying any writes. The mapping page
and doctor review show the limitation. Draft answers and the immutable original
remain available. An all-missing export preserves the original content; the final
missing DOCX is byte-identical to the retained rendered missing DOCX. The refusal
is independently derived from source structure, so deleting mappings or flags
does not authorize a filled export.

The ordinary pre-containment render also shows label/value concatenation
(`dated2026-09-27`, `version2.0`). This existing inline-spacing defect is retained
explicitly; this bounded repair does not change the general writer. Header/footer
appearance on ordinary page 2 differs despite unchanged package parts and section
XML. Without native Word acceptance, its cause and parity remain unverified.

These failures are not converted into passes by containment. A qualified layout
path and independent visual/native Word acceptance are still engineering gates.

## Finite checks, including failures

All local evidence is retained under
`rebuild/.runtime/d19-repair-20260927/` in this worktree; `artifact-hashes.json`
binds every retained local artifact.
The manifest, final focused logs, render-check metadata and containment summary
are also committed under `docs/rebuild/v1/evidence/d19-20260927/`. Full failed
outputs and local first-pass logs remain at their original runtime paths.

| Evidence | Result and interpretation |
|---|---|
| `01-red.log` | Original synthetic controls: 7 run, 5 failures, before repair. |
| `02-first-green.log` | First 7 focused engine controls passed. |
| `03-d19-inspection.json` | Repaired 17-area inspection; no automatic-success claim. |
| `04-workflow-first.log` | 5 run, 2 failures: unique-label protection notice absent; positive test incorrectly expected mixed-source input to pass existing conservative context rules. |
| `05-word-regressions.log` | 86 document checks passed; reused for unaffected paths. |
| `06-workflow-regressions.log` | 79 run: 74 existing and 4 new passed; one new notice-display failure. |
| `08-focused-workflow-final.log` | 5 new checks plus known-development D19 workflow passed before visual containment. Not proof of faithful layout. |
| `09-engine-final.log`, `11-engine-final-regions.log` | 8 focused controls passed after source-region strengthening. |
| `07-d19-workflow.json`, `original/missing/ordinary/long.docx` | Pre-containment actual workflow/export artifacts, preserved including failed long output. |
| `10-render.log`, `12-render-checks.json`, `render-output/` | Four PDFs and all eight PNG pages retained. Long visual failure described above. |
| `13-containment-engine.log` | Final 10 focused engine controls passed, including 12 primary writer kinds, the independent paragraph-options bypass, protected copies/descendants and nonempty floating-form refusal. |
| `14-containment-workflow.log` | 6 run, 5 passed; test assumed saved draft status was `draft`, while actual pre-finalization status was `review`. Assertion corrected to require unchanged prior status. |
| `16-containment-final.log`, `15-d19-containment.json` | Final 6 synthetic workflow controls plus D19 missing/refusal workflow passed (7 total, 13.666 seconds). Nonempty D19 attempts keep original, answers, prior status and no export. |

The renderer was the already-installed pinned image
`sha256:4bd4489d15b7326143e5575c789d93f675f77d85dc857900dd28ae1591d55a4b`
(LibreOffice 26.2.4.2). It ran with network disabled, read-only root, isolated
input/output mounts, no capabilities and bounded CPU/memory/process/time limits.
No image pull or binary-DOC conversion occurred. Permissions were changed only
on isolated render copies. Diagnostic import/path mistakes are recorded in
`render-checks-first-error.txt`; conversion was not repeated for those mistakes.

The new document test module is explicitly registered in
`scripts/ci/verify-fresh.sh`; ordinary core test discovery finds its core partner.
Full suites were not restarted. Synthetic database port **55702** was reserved
for this task, checked before each run, and each test database was destroyed by
the runner afterwards.

## Notice reference lock

The Refero design skill's small-change path was used; no live Refero tool was
available. References: existing form-inspection `notice warning` in
`template_detail.html`, existing review notice and original download link in
`encounter_detail.html`, and the skill's typography guidance for neutral work
tools. The locked decision is one existing warning component above review,
explaining the unavailable filled export and linking the unchanged form. No
new styling, palette, typography or layout system was added. Rendered HTML tests
assert that the warning and recovery link are present before editing/finalizing.

## Follow-up: refuse unusable generation before reserving or sending

Root found that the export warning did not prevent a billed generation. Before this
follow-up, the synthetic floating form could POST a valid quote and create a job,
direct enqueue did not refuse, and an existing queued job reached a mocked provider
and finished successfully. The synthetic receipt recorded cost **$0.01**, with
**$0.015** charged to a synthetic wallet, although any nonempty export was certain
to refuse. No real provider was called and no real funds were used.

The new generation-only guard runs before HTTP quote acceptance, inside locked
enqueue before job/reservation creation, and in worker dispatch before generation.
Stored warnings can refuse early; they are **not claimed immutable**, and missing
warnings cannot authorize. For v3 originals without that warning the existing
bounded, isolated document inspection runs again; its SHA-256 and v3 contract must
match the selected version's template. Source failure/integrity mismatch refuses
with a fixed message without document contents or paths. No cache or historical
metadata migration was added. Original download, mapping review and blank export
remain available. Worker replay raises the existing `NoProviderRequest`, recording
failure and releasing the existing hold atomically without a receipt or usage row.
Generation refusal does not block independent voice transcription/review.

New retained evidence (in the same runtime and committed evidence directories):

| Evidence | Result |
|---|---|
| `17-admission-red.log` | All 3 admission controls failed before repair: HTTP, direct enqueue, worker replay. |
| `18-admission-billing-red.log` | Exact worker proof: succeeded, one mocked provider call, one receipt, $0.01 cost / $0.015 synthetic charge. |
| `19-admission-focused.log` | All 13 checks passed in 21.457 seconds: prior 6 workflow checks plus 7 admission controls. |
| `admission-artifact-hashes.json` | Binds these three logs and the four changed source/test files; original 41-artifact manifest unchanged. |

The seven new controls assert HTTP refusal before quote/reserve, direct enqueue
refusal, old worker replay with warnings removed releasing a real synthetic hold,
missing historical warnings detected from source, source mismatch/parser failure
refusal without private details, supported nonfloating generation with mocked
settlement, and independent voice with its reviewed-transcript delivery path.
Network connection denial remains active. All tests used isolated DB55702; the
runner destroyed its test database. An initial test-file editing command used the
wrong relative path and made no edit; the first three-test RED still ran and is
retained. The one-test billing RED then added the explicit synthetic-cost evidence.

Only `core/jobs.py`, `core/v3_mapping.py`, `core/views.py` and the existing core
signing test module changed in this follow-up. Word engine and HTML are unchanged
from the first draft. Existing non-v3 paths bypass this new inspection. Old v3
synthetic fixtures with missing originals may now fail source verification; they
must supply a valid synthetic original rather than weaken this guard. No broad
suite was restarted. Root owns the combined release checks and final refutation.

This closes an avoidable billing path, **not D19 compatibility**. It does not
establish actual model behavior, native Word acceptance or a faithful filled
export for the refused class.

## Remaining limits / safe next action

The binary `.doc` exception remains. D19's converted document is not an automatic
success. No unseen cohort was tuned, replaced or rescored. Native Microsoft Word
acceptance and a faithful filled-export path for this floating layout remain
open. Captioned signing details remain protected; ordinary names/service dates
do not establish consent or attestations. Historical mappings, finalized files,
hashes, balances and receipts were not rewritten.

Next: independent finished-diff refutation, then root's local integration decision.
This commit is reviewed preparation in draft state; root's final independent
refutation is still pending at handoff, and committing does not integrate it.
No deployment or launch is authorized by this report. Preserve this worktree and
the complete runtime evidence if interrupted.

## Root integration and independent evidence

Locally integrated at `6e8ca616cb6608c58ee836ebcef4d6e75c5c5a2f` after 14 independent
export/protection controls and 14 separate admission controls returned no finding in their stated
claims. Root separately passed ten engine controls and six admission controls. The AST union
preserves both D19 generation definitions and all eleven other changed root definitions, with no
overlap. Root inspected the retained original/long images and confirmed eight visible original
initials boxes versus seven after long-answer reflow. D19 remains an automatic failure.

The combined signing and existing Word workflow run executed **87 tests: 86 passed, one failed**
in 115.180 seconds. The failed prior positive is the unique `Indication: synthetic knee review`
alongside ambiguous repeated Pain/Comments destinations. Root independently reproduced the same
parsed form with old and current generation source: old source supports Indication; the integrated
source holds it with all three lines as context. This shared ordinary-context regression stays open
for a bounded repair; it is not hidden by changing the test expectation. The original failed run
and source comparison are retained in the independent evidence directory. No full combined green
or compatibility claim follows from the bounded D19 protections.
