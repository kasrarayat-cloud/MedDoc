# Question/list/blank-box ownership — 2026-09-28

The parser assigned D30's single accommodation answer box to the final “other (please specify)” bullet. It now maps that box to the complete question and retains all eight printed residence descriptors. This is a reusable structural relation, with no document name/hash exception and no invented selection cardinality.

Base: `966e372b383b392b8651e934011f260ecedd935f`. Isolated branch `fix/v1-paragraph-list-ownership`. Product change is confined to `rebuild/documents/word_v3.py`; existing stored mappings, original files, corpus maps/scores, feature flags, financial scanner pins, provider admission and database history are unchanged.

## Source expectation and denominator correction

The independent original-only investigation preceded reading either expected map or implementing this change. Its immutable source evidence is retained privately under `rebuild/.runtime/paragraph-list-ownership/original-only-audit/`. Original SHA-256: `fdeafbee872f987325e544953ad930e8e8db8ed6bd30ccab0375f2b50ecbff2f`. Only the original DOCX and original-only pages 4/5 were used. The render is cached network-off LibreOffice evidence, not native Microsoft Word qualification.

The question is engine slot `word/document.xml#b/p[72]`; eight numbered bullet paragraphs occupy `b/p[73]` through `b/p[80]`. Three harmless spacing paragraphs precede the one empty bordered box at `b/tbl[4]/tr[0]/tc[0]`. XPath `w:tbl[5]` in the original investigation is the same table using 1-based XML indices. The next suitability question has its own separate box, engine `b/tbl[5]`.

No tick/select/choose/one-only/all-that-apply rule is printed in this accommodation block or its applicable Part B instructions. Residence type and co-residence can both be relevant. This does not establish an unlimited multi-select rule: the parser preserves the complete explicit text in the available answer box without asserting selections in the printed list.

The retained reviewer map has62 areas: A20 `multi_choice` over the eight list paragraphs, and A21 `text` in the single box. Its annotation invents a bold/highlight/delete marking convention. The retained annotator map calls A20 `choice` while acknowledging non-exclusivity. Both originals are preserved byte-for-byte. [The versioned correction](D30-ACCOMMODATION-CORRECTION-v2.json) records the original-only basis for treating A20/A21 as one full-question text destination; it is an appended correction, not an overwritten expected map or a new score. The prior 61/62 metric stays historical. Neither61 fields nor a revised denominator proves whole-form coverage.

## Bounded implementation

A body question followed by at least two contiguous same-level numbered descriptors, harmless spacing and one empty bordered unmerged cell can own that cell. The question must be an explicit question/request; a final Other item is optional. Actual controls, explicit selection instructions, source ambiguity, hidden/unresolved source, signing context, section boundaries, competing answer marks and oversized complete context refuse this relation. Plain bold descriptors, a page break inside the continuing list and different numbering-instance IDs do not create new questions. A list is claimed before the older lettered-options rule can turn its descriptors into another answer destination.

The new `source_questions` relation `paragraph_list_answer` carries the complete question/context, literal descriptors, their fingerprints and numbering identities, and numbering/relationship part hashes. Cardinality is explicitly `unspecified`. Export resolves these source anchors and rederives the whole relation at the same cell before writing. Changed source text, governing context, numbering, hyperlink target, relation metadata or physical ownership refuse. Writes still use the existing blank-cell writer. Numbered list paragraphs and their formats/relationships remain unchanged.

Old stored mappings are consumed as recorded. No migration rewrites old labels, kinds, locators or option targets. The retained actual61-field pre-fix D30 map was replayed through the sandbox and remained byte-for-byte identical as an input mapping.

## Validation and retained failures

Run from this isolated tree with the candidate interpreter:

```sh
/opt/meddoc-pro/.worktrees/v1-workflow-candidate/rebuild/.venv/bin/python -B rebuild/.runtime/paragraph-list-ownership/run_tests.py documents.test_paragraph_list_boxes documents.test_document_relations documents.test_question_boxes
/opt/meddoc-pro/.worktrees/v1-workflow-candidate/rebuild/.venv/bin/python -B rebuild/.runtime/paragraph-list-ownership/export_probe.py
/opt/meddoc-pro/.worktrees/v1-workflow-candidate/rebuild/.venv/bin/python -B rebuild/.runtime/paragraph-list-ownership/admission_probe.py
```

The scripts scrub the environment, use managed synthetic settings and a refused DB port, deny socket connects, and use only this session's `/tmp/claude-1000/v1-paragraph-list-ownership-20260928`. Actual document calls run under the existing `landlock+seccomp` worker. No database, model/provider call, token count or installed operation occurred.

- **63 focused methods passed**, including9 new methods and existing relation, question-box, nested-checkbox and tab-ownership controls. No skips or expected failures. The earlier retained63-method run exposed a bold-descriptor false refusal, repaired before the final run.
- The actual original before-state, `01-before.json`, shows A20's physical box mapped as label `other (please specify)`. `03-before-tests.log` and `08-before-behavior-tests.log` retain the new common regressions failing against the frozen base module (two methods, four failing cases). The second transcript asserts the wrong label or absent destination directly.
- `07-original-export.json` records actual inspection → shared `normalize` → `fill_answers` → isolated `fill_template`, using explicit synthetic clinician-entered text, not a fabricated model response. Blank, Care Home, own-flat-plus-partner and 5,400-character long inputs retain exactly their input text. Only the designated cell changes; every other body node and package part is unchanged. The full map still has61 fields and only `v3_20` changes on new inspection. The source and product module hashes are unchanged during replay.
- This is component validation and actual isolated document export, not authenticated HTTP/finalization, live generation, whole-form clinical or pagination qualification. Root's integrated original-form missing/ordinary/long replay must use the final union.

## Pending, constraints and integration boundaries

D30 direct inspection has `layout_pending=0`; the existing fixed-hyperlink warning remains. A structural answer mapping is not a form-wide constraint admission. The batch gate remains off; absent qualified `generation_constraints` still refuses. No manifest is synthesized. The changed complete-field digest prevents reusing a source-bound manifest for the old mapping as authority for the new mapping. `09-admission.json` records these observations.

`generation_batch`, `batch_jobs`, `v3_field_relations` and their scanner pins are untouched. Root's later `destination_temporal_scopes` recognizes one closed `immediate_previous_question` shape solely to remove that relation's generated display marker. This new relation has no such marker and creates no exception to temporal validation; its original context remains ordinary full text. Root's header/guidance fixes are a separate union and remain outside this branch.

Finished source awaits the mandatory bounded independent refutation before integration. No universal parser, clinical, corpus, Word or launch claim follows from these checks.
