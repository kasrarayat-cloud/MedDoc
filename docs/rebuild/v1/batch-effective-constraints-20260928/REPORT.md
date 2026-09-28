# Effective exported option constraints — 2026-09-28

Prepared/default off. Baseb1c3b95cca1a807f31eb5e3244258e8373bf9751. No providers/token-count calls, spending, corpus/holdout qualification, deployment or activation. No migration or historical record rewrite.

## Reproduced failures

The reviewer/root counterexample has103 mapped fields. Group A is printed Active; its answer is blank and reviewed. Group B is answered Active. The max-one-active rule previously accepted this and the actual Word export contained **two** active groups. Author reproduced the same class in01 and retained original/export/hash/result artifacts. A separate reviewer multi-choice case selected `Active\nReviewed` in two groups; whole-string equality failed to count either Active selection.

## Repair

Rules now evaluate the effective constrained option selections. The parent uses the existing document service bounds (10MiB original,2MiB request,20s subprocess deadline, isolated parser resource controls). One sandbox call receives the exact constrained control mapping and existing `fill_answers`/`normalize` output, verifies every original anchor including copied anchors, applies the existing Word writer in memory and reads the resulting controls. It writes no persisted export and never changes the original. The returned original SHA must match the selected template; the exact complete state set is required.

- A blank choice/multi-choice keeps its original selections and those selections count.
- A reviewed blank checkbox passes False through the existing writer and clears a printed check; an unreviewed checkbox preserves its printed state.
- Explicit option changes follow the actual writer/read-back, including resets. Multi-choice predicates use membership, not newline-string equality.
- Unknown/malformed states, invalid locators/source hashes and unreadable preserved states refuse visibly. Only controls referenced by the rule are read; an unrelated unanswered area does not acquire a new rule hold.
- Merged header dropdown copies must agree. Explicit writes resolving all copies can pass; differing preserved copies remain unknown. Unsupported absolute checkbox-copy relationships remain refused rather than inferred.
- Rule predicates must be exact valid mapped option/canonical checkbox values. Unique-priority rules require a scalar field/value and count a preserved original priority too.

The shared reader is used for complete worker adoption, explicit local recovery and existing page/save/finalization checks. Existing mappings without a constraints manifest are unaffected. Manifest/original qualification remains a separate dependency; this operation does not recognize global rules automatically or infer clinical meaning. D28 remains unqualified.

## Finite proofs and limits

|Evidence|Result|
|---|---|
|01 exact original class|Validator accepted; actual export showed two Active groups. Preserved.|
|02 first8 focused checks|7 passed; one fixture KeyError assumed single checkbox labels became Group A/B. Actual labels remain Active; fixture now selects its independently authored physical rows. No production parser change for this instrument correction.|
|03 batch+constraint affected run|29 passed;1 existing opposite-side clinical expected failure,84.332s.|
|04 final focused reader/workflow checks|9 passed,29.245s, including copied header controls.|
|05 exact retained103-field original replay|Bad answers refused at maxcount; explicit AInactive/BActive accepted and actual Word shows one Active. Original bytes/hash unchanged.|

The authenticated path rejects the bad save, shows the constraint warning on a forced historical supported draft, and refuses its finalization. After explicit correction it finalizes and downloads a hash-matching Word document with one Active group; no provider/Usage/Job is created by that manual workflow. The mocked worker path records its two bounded simulated responses, refuses whole adoption, closes the failed batch and leaves no partial answers. Existing batch financial behavior and `run_one` AST are unchanged.

These are synthetic component proofs, not live Sonnet5 or broad Word compatibility. The original ordinary opposite-side expected failure, global-rule producer, source/destination/choice semantics and real-model qualification remain open.

[Source and retained evidence manifest](evidence/manifest.json). Private runtime: `rebuild/.runtime/batch-effective-constraints-20260928/`; original and filled synthetic documents remain there with hashes recorded, not new production fixtures. Source is frozen; independent finished-diff refutation is required before integration.
