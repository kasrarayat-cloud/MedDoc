# Clinical CI cost repair — 2026-10-03

Run `37158506012` tested PR merge `1f04d51a493aedb9cea2ebe386ff6f830739893e`.
Its tree is identical to head `15f87bb2e7a487225711fa52c8092e279767ad01`;
`git diff --exit-code` returned 0 with no output. The failures apply to that
head, not to a distinct merge-base source. Official shards retain their original
results: core-1 ran 1,712 methods with 47 failures and 10 errors; core-2 ran
1,711 methods with 35 failures and 3 errors. All 95 failure/subtest entries stay
in the raw record. No full-suite rerun or replacement denominator is claimed.

## Concrete implementation failure and repair

`FloorCost.test_statements_that_cannot_oppose_are_never_compared` retained a
faithful supported answer for 40 positive medication sentences and allowed the
same answer at finalization, but made **14,196** predicate comparisons instead
of zero. `source_scope.owned_oppositions` bypassed the earlier unit candidate
index while reading separately owned patient content clauses. Local baseline
`ee9b0bc53dbc5dbb31e7efe961768254b6493f3c` reproduced the exact count: one
method failed in 7.278 seconds, exit 1.

The repair filters only predicate pairs that cannot oppose: equal effective
polarity or disjoint normalized predicate heads. The effective record is built
**after** outer negative operators are applied. Eligible pairs still use the
unchanged `v3_opposed_predicates` decision for object, tense and coordination.
Filtering by the outer unit's original polarity would erase patient claims
inside a foreign speaker's denial, so the unit index is not substituted here.

Six affected methods passed in 34.625 seconds, exit 0: all three FloorCost
methods (including the new outer-denial control), nested clinical argument
scope, negative-operator argument/property refutations, and existing
negative-operator grammar controls. The old all-positive control now makes
zero comparisons. The indexed-versus-every-unit equivalence control and the
negative warfarin assertion remain unchanged. The new test holds the explicit
patient content of `Her father denies that the patient takes warfarin.` while
keeping foreign content actors, another medication and possession independent.

## Foreign medication-event failures are separate

Both model routes' old `RoundTwo.test_m1_to_m5...` expect a hold for the exact
source `The patient takes warfarin 5 mg daily. Her husband switched to apixaban.`
and its reversed order (four original failed subcases). The second sentence's
sole explicit actor is the husband; it does not end the patient's medication.
The retained source-scoping rule reads that complete foreign clause separately.
This is an obsolete blanket-hold expectation, not demonstrated adoption of a
stopped patient medication. The expectation has **not** been changed here.

A separate finite replay covers seven exact statements, both orders, and both
`claude-sonnet-5` and `claude-sonnet-5-5`: 28 controls. Husband's own active/passive
switches keep eight faithful patient answers supported on wire, page and
finalization. Patient switches, unresolved pronoun switches, named patient-drug
switches, a husband switching **the patient**, and a named drug's passive
switch all hold (20 controls). Forced stored supported copies of those 20 are
held on the page and refused at finalization. All 28 meet their source-based
expectations. These offline synthetic results use no provider or database.

Before updating the older tuple, retain its original four failures and separate
that complete foreign-event survivor from its unchanged patient, agent and
ambiguous-pronoun hold controls. Do not replace the original record.

## Other CI clusters and limits

The earlier metadata/conditional-Plan `ee9b0bc5` chain does not repair the old
profile, provenance, original-bound mapping, or cost assertions in this run.
The reported SQL provenance refusals, unreviewed coverage refusals and protected
original refusal have concrete guard evidence. HTTP confirmation 400s and
worker-no-job failures need their actual response/redirect and persisted job
state captured before fixture correction. Stripe's `SimpleTestCase` now calls
a persisted integration-status query: its first forbidden DB query leaves the
test's `payments` variable unassigned; the second error is not proof that the
application page raises that exception. Doctor/admin fixture diagnosis belongs
to the operations writer. No safety expectation is relaxed by this report.

Exact-byte official logs, derived failure blocks, commands, local first failure,
focused result and all replay outputs are protected in:

`/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/storage-resume-20261003T215613Z/clinical/ci-run-37158506012/`

Manifest `clinical-readonly-and-cost-diagnosis.json` SHA-256:
`58a89711433db7290f82f5748ea0d830ffa6f0a1fc1ae084952c26499dd646d0`.
Official core-1 log: 840,234 bytes,
`fc1ec4ff56c91a369acbf74c7eb59b8d54a2e7f4b6b8ddc680941871c5dc3e44`.
Official core-2 log: 846,285 bytes,
`b8395426884f0f9bc601c9b1f6332843af03732e36d266925a878b3e34702b49`.
Finished source still requires independent refutation before integration.
