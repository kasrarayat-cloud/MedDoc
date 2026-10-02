# Independent cost scanner refutation — 2026-09-28

Reviewed finished commit `2023b9c212bab9d94471a670a10d556e036a7836`
in a detached review worktree. Author/application sources were not edited.
**REFUTED: one control-flow class, two retained concrete mutations.** This is
an acceptance defect in the new scanner exception; the unchanged application
still includes its history charge.

## Demonstrated false green

`rebuild/ops/test_production_deploy.py:1070` searches every descendant AST
node for the canonical history guard. At1076 it returns the inner addition,
which1096 exempts from ordinary rate-term checks. No execution position is
proved. At1109 an additional `return bound` is also accepted.

For a synthetic `Chief complaint` v3 field and source
`Patient presents with a cough.`, the exact live Sonnet5/history configuration
has an unchanged maximum cost **$0.10956**. Either of these source mutations
leaves the complete accepted canonical subtree intact:

1. Wrap that whole guard in `if False:`.
2. Insert `return bound` immediately before that guard.

Both return **$0.10502**, omitting the **$0.00454** additional history charge.
The finished scanner accepts both, returning its normal
`(12000, ('profile', frozenset({6000, 8000, 16000})))`.
The parent scanner refuses both with `rate term outside a bounded assignment`;
it also refuses the genuine unchanged history charge, the original CI blocker.
This repair therefore newly admits the two broken pricing implementations.

[Exact inputs, output costs and parent comparison](cost-scanner-independent-refutation-20260928/results.json),
[reproduction](cost-scanner-independent-refutation-20260928/probe.py),
[source hashes](cost-scanner-independent-refutation-20260928/source-sha256.json).
The probe runs the actual extracted `maximum_cost` function with unchanged
module globals. Network connections are refused, no provider/DB is invoked,
and all mutations are separate private files. No corpus or expected maps were used.

A bounded repair needs to prove that the accepted guard executes on the priced
general path, after its base assignment and before its terminal adjustment and
return. Matching one nested subtree is insufficient. Preserve the two original
outputs and replay them against the finished structural repair.

## Partition and scope

The single partition assertion adds `documents.test_composite_kind` to the
already-declared document module list; the prior modules and ops discovery stay
present. Four partition tests PASS. **NOTHING FOUND** in that bounded partition
delta. No full suite, release admission or live price verification was performed.

Runtime:
`/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus/custodian-20260927/cost-scanner-2023-review-20260928/`.

## Closure — frozen06fae1c6

Independently replayed the same unchanged input and two byte-identical mutated
source files against `06fae1c66a3fb327871e90106410209bcc924274`. Both previous
false greens now refuse with `history charge is not on the final priced execution
path`; the unchanged positive remains accepted at $0.10956. The deliberately
broken source still computes $0.10502, proving the scanner now rejects that loss
rather than changing the witness. **NOTHING FURTHER FOUND** in this bounded
closure. First outputs remain unchanged.

Scanner SHA256 `15e346a4836a34d3bec526885ae911f11dde6390f483c9eedd24798241fe77ee`.
[Closure results](cost-scanner-independent-refutation-20260928/closure-06fa/results.json).
