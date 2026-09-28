# Word table destination ownership — bounded continuation

**Prepared local source; independent refutation pending. Neither D30 nor D31 is a
qualified document success.** Source `649f65c2bd32b5b994611de91f9cb24cd6522034`,
base `4caa34431a60e6ce3409ecadbbb6989b50659d7b`, branch `v1-word-workflows`,
worktree `/opt/meddoc-pro/.worktrees/v1-word-workflows`.
Engine SHA256: `c82ef298b59780238c4f995c6da4056d87ca939282b62c15e74ef185f362cad8`.

Root's preflight `20260927T232730Z` permitted work with a disk warning and no
automatic fixes. Recovery found no active Word writer or test. Historical zero-byte
publication locks were preserved. The installed application remains the separate
synthetic-only `dedac162` release; this branch was not installed or pushed.

## Demonstrated shared defect and repair

A two-column form already maps its right answer cell. Empty spacing paragraphs
after the left printed label were then independently mapped as another answer.
For D30's date of birth this produced both:

- Correct physical cell: `b/tbl[0]/tr[5]/tc[1]`.
- Spurious second destination: `b/tbl[0]/tr[5]/tc[0]/p[2]`, inside the printed label.

D31's “Report on leave” had the same defect with an explicitly overwritable blue
guidance cell on the right, at `b/tbl[19]/tr[0]/tc[1]`, and an extra writable
left spacer at `b/tbl[19]/tr[0]/tc[0]/p[1]`. The original instructions expressly
allow replacing that blue guidance; this is not permission to erase other wording.

The repair suppresses only **unmarked spacing after a sole plain label whose
directly adjacent answer cell is already mapped**. It requires the same physical
row/column relation and label association. An empty neighbour alone is insufficient.
It does not borrow an outer table's destination for nested content or a text box.
Drawn blanks, controls, borders, unknown styles, independent below-label areas and
paragraph/table/default inherited answer markers retain their previous treatment.
The shared signing rules, export writer, generation logic and accounting are unchanged.

Self-refutation found an omission in the first helper: a paragraph border defined
by a conditional table style or document defaults was not considered. Both failures
are retained in `18-inherited-answer-marker-self-red.log`. The final helper treats
these inherited markers, or unknown table style ancestry, as non-plain. No source
keyword list or D30-specific rule was added.

Independent root refutation then found four omissions on the frozen `ebd52f50`
candidate: direct/inherited character-style underline, an unknown character style,
and implicit default table underline were incorrectly suppressed. Exact original
artifacts and results are retained under `23-root-style-refutation/`. The new
12-case regression had nine actual failures before repair, retained in log 24.
The final helper resolves character, paragraph and table style ancestry, including
unique implicit defaults. Unknown, cyclic or duplicate ancestry retains the answer
area. An explicit table style uses its own ancestry instead of an unrelated default;
direct overrides of inherited answer markers remain conservatively retained.
The exact five root artifacts now retain all four marked/unknown answer areas and
suppress only the plain-spacing control. This closes the demonstrated omissions;
it is not a general Word style-rendering certification.

The independent notes reviewer then found five visible-marker omissions in the
`a921dfc3` candidate: direct and inherited shading, run highlighting, numbered and
bulleted empty paragraphs. Root independently confirmed all five. Exact seven
artifacts remain under `30-notes-visible-marker-refutation/`, including desired
plain-spacing and retained underline controls. The final narrow repair adds those
markers, run borders, strike/double-strike and tabs to the conservative marker set.
Nine new marker controls failed before repair; all are retained in log 31. Final
22-test module passes in 5.604 seconds. Exact root five plus reviewer seven artifacts
now keep all marked areas; only plain-spacing controls are suppressed. D30/D31
maps and warnings again equal the successful workflow candidate in full (record 35).

Existing stored mappings and finalized exports are not rewritten. Old versions
containing spurious destinations need explicit review and a corrected mapping
version before clinical use; this new-detection repair does not certify them.

## Concrete D30 destination trace: 62 expected areas versus the current map

The existing independent 62-area map was checked against the original XML before
the retained candidate output was read. Original hash:
`fdeafbee872f987325e544953ad930e8e8db8ed6bd30ccab0375f2b50ecbff2f`.
The complete per-area expected/source/actual trace is retained, not replaced by a
field count. The previous 71-field map contained 58 expected physical destinations
and 13 extras. This repair removes eight extras, leaving **63 fields: 58 expected
destination matches and five extras**. A destination match is not semantic or
whole-workflow acceptance.

| Independent expected area / source | Concrete present defect or disposition |
|---|---|
| A20, accommodation choices, body paragraphs 73–80 | No mapped selection group. Eight printed list options use two numbering IDs; a plain bullet is not a checkbox. Cardinality and a faithful printed selection must be established, without removing unchosen original wording. |
| A21, “other (please specify)”, table 4 | No mapped answer. This box follows the preceding option list and three spacers. Merely increasing adjacency distance would guess its parent question. It remains visibly unresolved. |
| A26, table 9 | No mapped answer. Its text explicitly refers to the above relationship question and “this condition”. Complete linked source context must survive generation and stored review; the reference guard remains. |
| A40, table 21 | No mapped answer. The source explicitly assigns the section to the social supervisor's line manager. An app admin role does not confer that authorship. It remains visibly unresolved. |
| A6/A7/A37/A39/A41/A43/A56/A58 | Correct right-hand cells remain. Eight spurious left label-paragraph destinations are removed. Signature cells remain protected signing kinds and are not filled. |
| A10, table 0 row 9 | Full composite label asks for order date **and** restrictions/safeguards, but metadata says `date`, not narrative. Date values currently remain unrestricted text, so this is not evidence of an observed date-only truncation. Complete clinical answering is still unverified. |
| A9/A11/A15/A60/A61/A62 | Text/long-text metadata differs from the independent expected map. Both currently use text answers. Do not call the physical match a complete semantic check, or infer clinical corruption from the kind name alone. |
| A14, A16 and other composite table labels | Source wording and original instructions need full answer coverage. A16 has an explicitly guided answer cell; no complete multi-part clinical-answer test was performed here. |
| A37–A43/A56–A58 | Existing contexts often name only “Further Comments”, “Line Manager Comments” or “Request a reduction in reporting frequency”, rather than the complete report-author hierarchy. This repair preserves those fields; it does not establish role-aware generation. |
| A59–A62, patient annex and supervisor confirmation | Physical cells are mapped. Patient-authored statements and confirmation cannot be invented. The original author/confirmation instructions must govern the clinical workflow; whole-annex acceptance is unverified. |

Five concrete extra fields remain after this repair:

| Current source destination | Why this is not an independently expected answer area |
|---|---|
| Body paragraph 12, `after_label` | Fixed general-enquiries contact instruction mistaken for a field. |
| Body paragraphs 242–244, `paragraph_options` | A guidance list of application routes is treated as a selectable question. |
| Body paragraph 246, `after_label` | Fixed instruction referring to guidance/application forms mistaken for a field. |
| Body paragraph 252, `hint` | The printed submission email address is interpreted as replacement guidance; writing here can replace a fixed contact destination. |
| Body paragraph 269, `after_label` | The patient-annex heading is interpreted as an additional narrative answer. |

These remaining wrong/omitted destinations keep D30 **FAIL**, independently of
any percentage. The earlier “three unresolved boxes” description concerned that
one detector rule and was never complete document qualification.

## Reused development evidence and current pipeline limits

Only D30 and D31 were replayed for this repair, under the exact rights ledger's
internal offline synthetic scope. D31 is an independently authored discharge
application with different question/guidance structure. Its mapping goes from
76 to 67 fields, removing nine independently unannotated label spacers. No other
field metadata changes apart from fresh enumeration keys, and no field is added.
Both originals and all pre-repair maps remain intact.

The retained historical results for the 33 rights-supported development originals
were classified by pipeline stage without a new engine run or score. The private
`16-retained-dev-pipeline.json` records each original, source/lineage, expected kind
distribution, frozen mapping size, reported detection/render failures and missing
app acceptance. It does not turn a historical render result into current proof.

Distinct shared causes remain:

- Question ownership around nested tables and control groups: D03/D10 need a
  separate guarded relation, not this adjacent-cell rule applied indiscriminately.
- Printed options, repeated labels and controls: independently establish every
  option/answer location; recognized files or generated field counts do not prove
  full mapping. Custodian's new original-first D03/D04 maps are sealed independently.
- Static authoring instructions and templates: D33/D34/D37 historical extras require
  distinguishing fixed guidance from answer areas, without deleting source text.
- Long-answer fidelity: retained D26/D27/D28/D29/D31/D35 render failures require
  source-specific current reproduction before any claim that they are fixed.
- Request admission: the app currently refuses more than 100 answerable mapped
  fields. D10/D11/D28/D29 independent maps contain 198/559/227/125 areas before
  signing-kind exclusions. Some other historical maps exceed 100 because of
  detection extras. These are different problems. Do not merge independent
  questions or raise the cap to hide them. A bounded chunk/section workflow needs
  identity, source-context, complete-coverage and reservation design first.

The seven held development originals, holdout and qualification contents were not
replayed. Original 40/60 denominators and all first-pass results remain unchanged.

## Authenticated application and export evidence

Both original forms failed before repair through the actual authenticated upload
route, exactly because the spurious left spacer appeared in the returned mapping.
The repaired originals each passed **missing, ordinary and long** scenarios through
upload → mapping review/confirmation → mocked provider selection with actual source
validation → worker → clinician correction → finalization → authorized download.

Ordinary source examples were unlabelled sentences:

- D30 date of birth: “The patient was born on January 1, 1980.”
- D31 leave report: “The patient reports supervised leave every Monday.”

Both were supported before correction. This is deterministic source-contract and
workflow evidence; it is not live Sonnet quality evidence. Other questions were
explicitly reviewed blank. The long answers are conspicuous synthetic stress text,
not proposed clinical content. Clinician corrections do not count as automatic
recognition or document success.

Original download equals the uploaded bytes. Export download equals the stored
export hash. Every indexed source slot outside the selected target subtree is
unchanged, including the neighbouring label. Every other package part is identical.
For both missing exports, **all ZIP member bytes** equal the original; only ZIP
container metadata differs. No original or recorded export was overwritten.

| Check | Retained outcome |
|---|---|
| Four structural shapes, before repair | All four fail with duplicate destinations: ordinary, merged, multicolumn, nested. |
| Two original authenticated uploads, before repair | Both fail on the exact spurious label spacer; no provider request occurs. |
| Synthetic paired-cell full workflow | One test passes in 7.265 seconds, covering missing/ordinary/long. |
| Original D30 and D31 full workflows | Two tests pass in 27.470 seconds; isolated synthetic PostgreSQL 55702. |
| Affected engine modules | 98 tests: 97 passed; one newly written test used the wrong target name `dropdown` instead of the actual `sdt_choice`. Its failed output is retained; the corrected assertion passes separately. No app change was made for that error. |
| Inherited-border self-refutation | Two concrete failures retained, then repaired. |
| Final changed question-box module | 20 tests pass in 4.405 seconds, including controls/text boxes, original checked-state preservation, inherited borders and unknown-style retention. |
| Independent root style refutation | Four counterexamples retained; 12 added style controls include nine pre-repair failures. Final exact artifact replay passes. |
| Final changed module after root repair | 21 tests pass in 4.784 seconds; no provider or database used. |
| Final visible-marker repair | Nine pre-repair regression failures retained; final 22 tests pass in 5.604 seconds, with all 12 exact independent artifacts replayed. |
| Final original map binding | Entire D30 and D31 fields, warnings, contract, source hash and sandbox metadata equal their successful workflow candidates, again after both independent repairs (logs 26/33 and records 28/35). Unchanged workflow/render evidence is reused. |

## Rendered comparisons

The four changed ordinary/long exports were rendered using the pinned, network-denied,
resource-limited Gotenberg/LibreOffice image used in prior evidence. Original PDFs
were reused, and missing results are bound by all-member byte identity.

D30 original/ordinary have 12 pages; long has 15. D31 original/ordinary have nine;
long has 12. Nine affected comparison images were inspected. No measured text
overlap or visually observed target clipping/overwritten neighbour occurred.
Branding, untouched check states and surrounding questions remain. Long answers
flow across page boundaries; unchanged source XML supports reuse of unaffected checks.

The initial full-page extractor reports noncontiguous long text: it interleaves
header/footer text at page boundaries. D30 initially finds 73 answer prefixes;
D31 finds 90. These raw results remain. A separate comparison uses explicit body
bounds justified by measured glyph positions and the inspected continuation pages:
D30 bottom 70/top margin 100 points; D31 bottom 40/top margin 50. It finds the full
answers and **75/75** and **90/90** complete statements. This is a bounded explanation,
not a new general scorer. **Native Microsoft Word acceptance remains unperformed.**

## Evidence, ownership and next action

Private runtime:
`/opt/meddoc-pro/.worktrees/v1-word-workflows/rebuild/.runtime/word-workflows-20260927/`.
Text evidence is copied under `word-table-ownership-evidence-20260927/` beside this
report. Filled DOCX/PDF/PNG artifacts remain private, outside Git.

- `01-D30-independent-source.json`, `02-D30-destination-trace.json`: full source and
  62-area trace against the retained pre-repair 71-field map.
- `21-D30-final-destination-trace.json`: all 62 expected areas against the final
  63-field map, with explicit per-area workflow and native-Word evidence limits.
- `D30-*.json`, `D31-*.json`: baseline, paired and final maps plus exact removed fields.
- `D30-workflow-red/`, `D31-workflow-red/`: original first failed upload artifacts.
- `D30-workflow-after/`, `D31-workflow-after/`: originals, missing/ordinary/long
  exports, mapping and workflow/hash records.
- `render-output/D30-{original,ordinary,long}-02.png`, D30 long pages 03/04;
  D31 original/ordinary page 03 and long pages 04/05.
- Logs 03/09/13/18 retain the structural, authenticated, test-instrument and
  inherited-marker failures. Logs 04/07/10/14/19/20 record their exact dispositions.
- Render logs 15/17 preserve first text extraction and separate body-bound analysis.
- `23-root-style-refutation/`, logs 24/25 and records 27/28 retain independent
  failure artifacts, new regression failures, repairs and exact map equivalence.
- `22-source-identity.json` records the refuted candidate; `29-source-identity-final.json`
  records the first style repair; `36-source-identity-final.json` records the final marker repair. Earlier trace 21 is reused only by exact map equivalence.
- `30-notes-visible-marker-refutation/`, logs 31/32 and records 34/35 preserve the second independent finding and final repairs.
- `evidence-manifest.json` records hashes for the retained runtime, including private
  binary artifacts. Text-only copies accompany this report; binaries remain private.

Source is frozen for mandatory independent refutation. Root owns release/CI and
integration. Notes owns A35 and broader source-completeness work; this branch does
not change generation. Root's retention stream owns its separate model/view/job
changes. No providers, paid operations, purchases, deployment, existing lock removal,
corpus campaign or new compatibility denominator occurred.

After this coherent fix is reviewed, continue the distinct nested/control ownership
diagnosis using authorized, independently mapped development originals and prepare
the measured large-form admission proposal. Broad editable DOCX compatibility
remains required V1 engineering; maintenance and synthetic-only admission must remain.
