# Paragraph-list ownership: bounded counterexample repair

The first repair at `e47b41fcce8dcb239bf41fb0f06ad77b5f80a680` was refuted by five concrete outputs in four families. This continuation preserves that commit, its original source-only D30 correction, the reviewer's six-case probe and first results. The independent reviewer and root each reproduced the five failures before this repair. Nothing in this report promotes the earlier result to independent closure.

This isolated branch, `fix/v1-paragraph-list-boundaries`, starts at that exact commit. Only `rebuild/documents/word_v3.py` and its focused test module change product behavior. No root integration tree, original document, expected map, score, stored mapping, database, flag or scanner pin changes.

## Demonstrated failures and bounded repair

| Original input | Before | After |
| --- | --- | --- |
| Blank answer paragraph inherits a hidden style | Full-question mapping writes an invisible answer | No answer field is emitted; the existing visibility gate resolves paragraph, inherited and table styles |
| Same map, then styles.xml changes that destination from visible to hidden | Export accepts an invisible answer | Relation rederivation rejects with `mapping_mismatch` |
| Plain preceding instruction: “Tick one residence below. Use the box only to specify Other.” | Whole-question unrestricted text owns the Other-only box; instruction is absent from context | No whole-question list relation is emitted; applicable local instructions are retained in context and bound by full source anchors |
| Numbering level prints a checkbox glyph | List is incorrectly classified as plain descriptors | Effective numbering level and override are checked with the existing glyph/font reader; control markers refuse |
| Question refers to “the above question” without a bound question | Mapping and export accept incomplete source | The ordinary question-box reference gate is shared by the list rule; unresolved references refuse |

The visible positive remains mapped and exports visible text. Plain Courier `o` bullets, numbered/lettered descriptors, existing list-instance/page-break controls and D30 retain their meaning. The rule does not establish ownership for unresolved references or checkbox lists. Existing explicitly exclusive option rules are unchanged.

The destination check calls `tab_source_visible` for each answer paragraph. It does not rely on the destination element fingerprint to cover external style definitions. Export already rederives the complete source relation, so changing the applicable style invalidates this map without introducing a document-wide styles hash or rewriting legacy maps.

Plain instructions immediately preceding the question are retained back to the preceding heading/table. Competing questions, unresolved visibility, source references and unsafe blocks refuse. Selection and Other-only restrictions are applied to that complete bounded context. Nonempty instruction anchors are included in `source_questions.instructions`; export resolves each anchor and requires exact rederived relation equality. The benign instruction positive proves preservation and changed-source refusal, not arbitrary natural-language interpretation.

## Validation

Private, ignored evidence is at `rebuild/.runtime/paragraph-list-boundaries/`. [EVIDENCE.json](EVIDENCE.json) records file hashes, source identities and exact commands. Runtime originals remain unchanged.

- `11-reviewer-before.json`: unchanged six-case reviewer probe against frozen e47; one valid positive and five bad acceptances reproduced. Only its single hardcoded worktree path is adapted by a retained wrapper.
- `17-reviewer-final.json`: the same six cases on the final source; one visible positive, four no-field refusals and one changed-style export refusal. Before/after source hashes agree.
- `14-boundary-tests-before.log`: seven new test methods against the frozen e47 module produce19 failing assertions. The plain Courier marker positive passes. No expected failures hide the before-state.
- `13-focused-tests-initial.log`: **70 methods pass**, including seven new methods and all existing paragraph-list, document-relation and question-box controls; no skips or expected failures. Product source was unchanged after this run.
- `15-original-export.json`: actual D30 inspection → shared normalization/answer validation → `landlock+seccomp` export. Explicit synthetic clinician entries are blank, Care Home, own flat with partner, and5,400 characters of the same explicit residence statement. Complete input text is retained. Every body node outside the answer cell and every other package part is unchanged. The old61-field mapping remains an unchanged input and exports correctly.
- `16-admission.json`: D30 has61 fields and only `v3_20` differs from the retained original mapping; the source-bound field digest equals the first repair's digest. Layout pending remains0 with the existing fixed-link warning. The batch flag stays off and a missing qualified constraint manifest still refuses; no manifest is synthesized.

Commands use the candidate Python interpreter, scrubbed managed synthetic settings, an unusable database port and socket-connect refusal. Scratch stays under `/tmp/claude-1000/v1-paragraph-list-boundaries-20260928`. No database, provider, token-count, model or installed operation occurred. No filled document is retained in Git.

The original D30 expected maps, appended correction v2 and historical61/62 metric are unchanged. The full-question mapping supports the demonstrated accommodation answer area; neither61 fields nor the correction establishes whole-form qualification. These are component and isolated-export checks, not a new authenticated HTTP/finalization, native Microsoft Word, clinical-generation or launch claim. Root's integrated original-form missing/ordinary/long replay remains a separate final-union responsibility.

Finished source is frozen for the bounded unchanged-probe independent closure. No further broad review campaign or integration is performed in this branch.
