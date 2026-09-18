# The four checks that passed without exercising their conditions

Written 2026-09-18. Four checks reported success because of what was ABSENT from their inputs rather
than because the thing they watched was true. One reached production. This records each one, what it
was supposed to guarantee, what was missing, whether a release shipped on it, and what now makes the
same mistake visible.

## Why this is a class and not four accidents

Each assertion was correct. Each sat behind an input that never reached it. That failure is worse
than having no check, because a check that cannot fail does not merely miss the defect — it reports
that the defect is absent, and somebody acts on the green.

The repair is not "write better assertions". It is to make the PRECONDITION a declared, failing
assertion: `exercised.requires_input(condition, what)` raises `MissingCoverage` naming the input that
is missing and why its absence empties the check. The module has no imports and no dependency on
Django or unittest, so the same call works in the Django suite, the plain-unittest ops suite, and an
operational script.

## The four

### 1 · The migration proof — every fixture encounter was a DRAFT

| | |
| --- | --- |
| Check | `rebuild/core/tests/test_service_date_activation.py` `MigrationValidation`, and the migration's own test coverage |
| Intended guarantee | migration 0014 can add `service_date` and backfill every existing encounter |
| Missing input | **a finalized encounter.** `encounter_scope` refuses ANY update to a finalized document; every fixture was a draft, so the guard was never reached |
| Influenced a release? | **YES.** PR #1199 merged as `475a5925` with a full citation, and the declared activation then failed against the live database at `15:37:47Z` — six of the eleven production encounters are finalized. The migration rolled back whole and the services stayed stopped |
| Now | `TheBackfillMustReachAFinalizedDocument` declares both inputs it needs: a finalized encounter, and `encounter_scope` present and ENABLED. Remove either and the class reports MISSING COVERAGE instead of passing |

### 2 and 3 · Two versions of the code-evidence prefix check — neither could discriminate

| | |
| --- | --- |
| Check | `test_a_longer_code_is_still_not_read_as_the_shorter_one_inside_it`, then `test_each_code_quotes_its_own_line_when_one_code_is_a_prefix_of_another` |
| Intended guarantee | the evidence lookahead in `core/coding.py` must not attach the line documenting one code as evidence for a different, shorter code |
| Missing input, version 1 | **the shorter code was never a token.** `re.findall` does not overlap: `M25.532` consumes the text and `M25.53` is never extracted, so the lookahead under test never ran on it |
| Missing input, version 2 | **a digit follows the prefix.** With `M25.53` inside `M25.532`, `(?!\w)` already rejects the match because `2` is a word character — the broken and correct forms give the SAME answer |
| Influenced a release? | No release shipped on either. Both were caught by mutation testing before merge, replaced twice, and the surviving test was written only after the discriminating case was understood |
| Now | the surviving test declares that BOTH `M25` and `M25.532` are extracted as tokens and that both exist in the release being searched. `test_why_both_earlier_versions_of_the_prefix_check_were_empty` pins each dead end in terms of the code's own token regex, so the check cannot be rewritten back into either |

### 4 · The activator's surface-agreement check — a tautology

| | |
| --- | --- |
| Check | `scripts/activate-service-date.py`, the health-agreement predicate |
| Intended guarantee | refuse to act when one private surface is up and the other is down |
| Missing input | **a discriminating case.** It was written `any(answer is None) or all(answer is not None)`, which is TRUE FOR EVERY POSSIBLE INPUT, and it was only ever fed uniform inputs — both up, or both down |
| Influenced a release? | No. It was written and corrected within the same unmerged branch, before the activation that used it |
| Now | the predicate is a named function `surfaces_agree()` so the test exercises the REAL code rather than a copy that can drift, the test declares it is exercising inputs that actually differ, and it asserts the one-up-one-down case is refused |

## Each repair is proved twice

For every check: removing its required INPUT must report MISSING COVERAGE, and restoring the original
DEFECT must make it FAIL. Both were demonstrated by mutation — six demonstrations, each verified
applied, each producing the expected outcome, with no residue left behind.

## A fifth, found while repairing the others

`rebuild/core/tests/test_wm_workflow.py` skipped eight live document-workflow tests on a predicate
naming **two** of the **three** environment variables `documents/sdk_service.py` requires, and saying
nothing about ownership. With two of three set, those eight tests RAN and FAILED — reporting a defect
in the document workflow when the only thing wrong was the host. The predicate now names every
condition and reports which one is missing, so the suite either exercises that path or says exactly
why it cannot. On this host it cannot: the operator account owns the Word processor, and the service
refuses a processor it can modify.

## What this does not claim

These are the four this milestone was asked to resolve, plus the one found in passing. It is not a
statement that no other check in the suite is vacuous. The scan that found the fifth was targeted at
a handful of shapes — assertions over empty collections, `subTest` loops over empty lists, comparisons
of a value to itself, and `or` expressions that are tautologies — not at the whole corpus.
