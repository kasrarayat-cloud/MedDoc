# Native checkbox history cardinality

D31's “Community leave taken” maps nine native checkboxes as a single-choice question. An explicit record containing both compassionate day leave and compassionate overnight leave therefore fails both shared answer validation and export. The cause is `choice_kind`'s fallback, not a limitation of the controls. This bounded continuation qualifies independent completed-event lists without changing that global fallback.

Base: `fba37e2f` on isolated branch `fix/v1-checkbox-cardinality-union`. The separate paragraph-list source remains frozen on its own branch. No integration, push, original-file mutation, provider call or installed operation is performed here.

## Original-only expectation

The original source was inspected before reading the expected-map entry. Original SHA-256 is `f730aa53671ab367eb5e89376d653ef0d51f096962ae616480711a292eeed36d`. The original-only cached LibreOffice page3 and OOXML agree: “Community leave taken” owns nine separate legacy FORMCHECKBOX controls at body paragraphs27,29,31,33 and35. The printed options distinguish compassionate, medical, escorted and unescorted day/overnight leave, plus long-term escorted leave. Nothing in this block says choose one.

The governing conditional-discharge section describes an evidence period. The following separate “Report on leave” question requests amount, frequency, duration, destination and purpose. Those historical events can include both day and overnight leave. The earlier “Type of discharge applied for” table explicitly says “please tick one” and is a separate question; its instruction does not govern the leave history. No clinical event is inferred or supplied by the parser.

The original reviewer map, read afterward and retained unchanged, identifies A15 as `multi_choice` with these exact nine controls and options. Its SHA-256 is `e86962a18fea61c1718f0086ce75d4af318082766a60e2c47f9e073cdd18387a`. This repair aligns the one demonstrated cardinality behavior; it neither changes an oracle nor computes a new whole-form score.

## Reusable, bounded contract

Only complete body-paragraph groups of at least two independent native FF/SDT checkboxes participate. The full owner must end in one of the completed-event words `taken`, `received`, `completed`, `attended` or `undergone`. Both “Treatments received” and “Courses attended” are tested with native FF and SDT controls. No document ID, source hash, leave option or template exception appears in the rule.

The complete owner and literal options cannot be truncated or duplicate. Applicable immediately preceding plain instructions and resolved governing headings remain in the context. Their source paragraphs, the group paragraphs and intervening spacing are fingerprinted. Hidden/unresolved source, unsafe boundaries, signing/consent context, source references, instructions embedded ambiguously in options and unresolved limits refuse the new relation.

Explicit one-only instructions, known exclusive/binary option words and single/current/latest-event wording retain one-choice behavior. A mixed independent-plus-Yes/No/None list therefore does not become multi-choice. Conflicting instructions and unrepresented limits stay unmapped. A prior unrelated tick-one table remains outside the local instruction scope. Dropdowns, glyph choices, table grids and unrelated checkbox questions keep their existing behavior.

The new `native_checkbox_history` source relation records the complete owner, context, options, cardinality and source anchors. Export resolves those anchors and rederives the same source relation, field kind, options, label and context at the same physical controls. Changed source, governing context or mapping identity refuses. Old stored maps are consumed as recorded and are never rewritten.

This is a deliberately limited event-list recognition rule, not a universal semantic proof that arbitrary labels are independent. Unrecognized syntax keeps the prior behavior. Governing context here is the resolved heading and immediately preceding plain instructions: the earlier separate one-cell conditional-section guidance table remains outside this local cardinality relation. This change does not interpret its full clinical applicability/evidence-period requirements or close whole-form clinical qualification.

### Remaining D31 clinical-source blocker

The original section instruction at `word/document.xml#b/tbl[13]/tr[0]/tc[0]/p[0]` reads:

> Please complete this section if you wish to apply for the conditional discharge of the patient from hospital. The evidence period is since the last Tribunal decision; a previous refusal by the Secretary of State; or, if applicable, since recall to hospital where this was primarily for assessment. There is no need to attach any further documentary evidence with this application, but MHCS case managers may request further information from the RC or Multi-Disciplinary Team (MDT).

Its preceding section heading is `b/p[19]`, “Conditional Discharge Proposal”. A15's controls at `b/p[27]` through `b/p[35]` occur within that section, before the next “Absolute Discharge Proposal” heading at `b/p[43]`. The instruction therefore provides applicable conditional-section source context, separate from the local selection cardinality. It must not be replaced by an invented date, event, unconditional time window or inferred clinical history.

The new A15 field still contains the heading alone as its context and does not carry this paragraph in `source_instructions` or its local source relation. This is an explicit remaining clinical-source omission. The cardinality repair and synthetic manual export do not discharge it; a fixture-driven HTTP pass would not establish that omitted form constraints are safe either. Reusable ownership of such section instruction blocks, their complete preservation in the model catalogue, and downstream clinical-source enforcement require a separate bounded repair and proof.

## Evidence and checks

Ignored runtime: `rebuild/.runtime/checkbox-cardinality/`. [EVIDENCE.json](EVIDENCE.json) records source/evidence hashes and commands.

- `01-original-paragraphs.json` and `read_original.py` retain the original-only extraction. The initial read-only extraction tree, `v1-checkbox-cardinality`, remains untouched; actual source work uses the requested fba union baseline.
- `root-d31-a15-first.json` preserves root's first invalid-answer result. `02-before.json` independently reproduces both shared validation and export refusal on the requested base.
- `06-before-tests.log` retains **10 failing assertions across8 new methods** against the frozen base. This includes the independent non-leave positives, source binding, limits and unrelated-table scope. No expected failures suppress these results.
- `05-focused-tests.log`: **79 methods pass**, including8 new methods, all document-relation/question-box controls, and option-reader, native-control, box-cell and legacy-dropdown regressions. No skips or expected failures. The first new-test transcript is also retained: two assertions wrongly required checkbox display glyphs to stay unchanged when ticking; the corrected assertion restores only the addressed controls and compares all other XML.
- `07-original-export.json`: actual D31 inspection → shared `normalize`/`fill_answers` → `landlock+seccomp` export. Blank leaves all nine controls false; one explicit option sets only its control; the explicit two-option input sets exactly the first two. Every other body node and every other package part is unchanged.
- The original discharge-type question still accepts one option and rejects two. The exact old61-field mapping remains an unchanged input, exports one leave option and retains its recorded one-choice validation. New inspection also has61 fields; only `v3_17` differs.

All scripts use scrubbed managed synthetic settings, a refused DB port, socket-connect denial and this session's `/tmp/claude-1000/v1-checkbox-cardinality-20260928` scratch. Source and module hashes agree before/after export. No filled document is tracked. No model, token-count, database or authenticated HTTP/finalization call is claimed. Cached LibreOffice inspection is not native Microsoft Word qualification. Feature gates, constraint manifests, financial scanner pins and historical records are unchanged.

Finished source is frozen for the mandatory independent bounded refutation before integration. Root owns the final union and original D31 two-option/one-choice replay.
