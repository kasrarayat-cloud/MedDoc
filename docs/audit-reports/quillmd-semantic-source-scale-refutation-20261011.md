# QuillMD semantic source-scale finished-diff refutation — 2026-10-11

**Result: NOTHING FOUND within the permitted offline scope.** The refutation
looked for concrete false acceptance/rejection, schema or description alias
leaks, loss of source scale bounds, and loss of documented history connectors.
It did not call a provider, mutate a database, or exercise a native/public flow.
No public success is asserted.

## Frozen diff

- Worktree: `/opt/meddoc-pro/.worktrees/quillmd-semantic-source-scale-20261011`.
- Base: `425818e4967c313c3f885aad34d1cf625cf5f2fd`.
- `rebuild/core/semantic_generation.py` SHA-256:
  `fabeb5e697a4d4a81b2c646685f607fe6f8206fe0df660600f8c8dda4c5ddcf7`.
- `rebuild/core/tests/test_semantic_generation.py` SHA-256:
  `0adb5931de0dc73d8e496409ecf611bac449c93a92f6850f55bd39755f012d85`.

## Independent controls and counterexamples

The managed fixture environment was loaded in-process without printing its
contents. Provider keys were removed; the database port was overridden to `1`.
Only `SimpleTestCase` fixture tests and pure semantic calls were exercised.

- The six `SemanticSourceScaleContractTests` and seven
  `SemanticSourceReferenceTests` passed: **13 tests, 0.343 seconds**.
- Positive control: a numeric `3` with explicit source `0 to 10` produced a
  supported value of `3`; its stored answer validated.
- Negative control: explicit source `1 to 10` was held against an approved
  `0 to 10` scale, retaining no supported value.
- Four additional adversarial source-scale proposals were refused: borrowing
  another measurement's maximum, borrowing an unrelated zero from the same
  statement, erasing an explicit source minimum, and changing the denominator.
- The focused contract tests also confirm rejection of invented zero before
  assignment, supported `3` for a documented denominator with null minimum,
  holding a missing source scale, and exact retention of the fixture's causal
  and timing phrases.

## Change boundaries

AST comparison against the base found all **29 function/class ASTs unchanged**.
Removing `description` properties from the new API schema yielded the exact
base API schema. `FACT_SCHEMA`, `SOURCE_REFERENCE`, assignment/checker schemas,
and assignment/checker instructions were unchanged. The new value and scale
reference descriptions did not appear on subject-name, timing, or unit
references; their separately copied objects did not alias each other.

## Limits

This establishes the offline fixture behavior and unchanged deterministic
implementation, not provider obedience to the revised instructions. The
connector tests start with supplied exact facts; they do not establish that a
live extractor will always select those phrases. No paid extraction, public
operator qualification, native document action, or production verification was
performed by this refutation pass.

## Independent code-only operator refutation

The separate finished private operator
`6421160910dca535b2edf32106470f46b74f2c03f079c734e293e09b6ab2c3e1`
was independently refuted after freezing. **NOTHING FOUND within pure/read-only
scope.** The refuter replayed 17 positive and 197 refusal controls through the
actual functions before the qualifier's receipt-writing tail; the original
qualification receipt remained unchanged. It verified the operator, qualifier,
receipt and static-contract hashes recorded in the prospective declaration.

Additional namespace checks bound the input/operator validator, candidate
worktree, base revision, four-path manifest, restore output and inherited
drain/post-resume closures to the new runtime. Inspection confirmed twelve
exact-once main-function adaptations, full 41-table equality, semantic file
references, backup-before-restore-before-publication, no migration or static
mutation call, and the unchanged original recovery-handler AST. No native
database query, service action, provider call, sudo or operator edit occurred.
This is offline operator evidence, not installation or public clinical success.
