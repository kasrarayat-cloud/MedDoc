# Retained Word role and choice CI failures

Exact7907 core2 CI retained two failures: RR1-10 expected a mother's signing
line qualified by DOB to be typed as a date, and a choice-mapping refusal
expected superseded dropdown copy. The current structural signing detector
types the first original as a signature. No application guard is changed.

The RR1-10 control retains its original form and attempted model DOB relabel.
It now also proves a typed date is invalid for the real signature kind and a
forged date mapping onto the same original physical signing area is refused.
The model proposal adopts no change, preserves the original signing field and
leaves the uploaded original bytes unchanged. The choice control retains its
400 status and unchanged mapping count, and checks the current actionable
printed-options/dropdown guidance.

The two original affected methods pass with actual child/outer exit0, no
timeout, no provider call and unchanged source diff. Outer duration is
17.303062885 seconds; direct read-only catalog evidence verifies both the
normal and test task database names absent before releasing the QA slot.

Original CI evidence remains in ci-7907ae5a-20261004/core2-failure-blocks.json.
Two intermediate assertion expectations reached earlier/different valid
refusal paths and remained red. A third test log completed but its system-
interpreter receipt collection failed; its child exit was unrecorded, and no
pass claim is based on that log. The final qualified-interpreter run writes
actual child exit before teardown inspection. All intermediate artifacts are
retained separately; no original failure was overwritten or regraded.

This affected regression result does not supply a full CI citation or Word
whole-document acceptance.

- Final receipt: `root-word-ci-assertions-fourth-qualified-20261004T054818Z/result.json`; SHA256 `1349aabe6c7a168f7889a9ee189165be6b874d6db1cf13b692786d18784a9a32`.
- Final actual test log SHA256: `30d21da3eb1d0107ea1d0e3fc078f225c47effc0e4653d06426c5e6a81c149d3`.

The last retained Word Core1 error is also reproduced separately: the original
720-order RF12 test's report cache rejected the actual mapping_review keyword.
Its cache now includes the mapping-review mode and forwards that same mode to
the real original-bound role reader. No production guard, order or expected
result changes. The original affected method passes all720 orders with actual
exit0, no timeout, provider call or changed source diff; own normal/test
databases are confirmed absent. The first reproduced TypeError is retained.

- Reproduced original: `root-word-core1-rf12-20261004T062206Z/result.json`.
- Corrected actual receipt: `root-word-core1-rf12-20261004T062327Z/result.json`.
- Corrected test log SHA256: `906b44373edfe686dff24c17ab6f65a135622d7b563a1d4228976c9b47c80459`.

This closes the affected selector, not the full required CI gate.
