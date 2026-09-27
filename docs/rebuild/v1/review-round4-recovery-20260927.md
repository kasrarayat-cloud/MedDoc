# Review guards: interrupted round 4 recovered

Recovered from `v1/review-guards` at `2a67a6061bed46145e5866446e66b97dbd9e4e3f`.
All R4 implementation repairs were committed before the interruption. The remaining 115 lines of tests in `core/tests/test_review_guards.py` were preserved and completed without changing application behavior.

## Verified outcomes

- Original mutation execution completed: 25/25 killed, application asserted; every source restored. Independently compared all four source SHA256 values to `review-repair4/pre-mutation.sha`; exact matches. Reused, not repeated.
- Missing final `manage.py test core.tests --noinput` run completed against the isolated review database: **1224 tests, 1213 passed, 11 skipped**, 484.765 seconds, exit0. No skipped check is claimed as Word acceptance. Raw log retained at `/opt/meddoc-pro/rebuild/.runtime/v1-astra-recovery-20260927/review-core-tests.log`.
- Finalized records reject both coding writers. Finalize does not increment the revision: receipt/review bindings reference that revision; status is the write barrier. Accepting an already accepted code refuses and preserves the original clinician.
- Suggestion computation occurs outside the document lock, followed by status/revision/notes/membership rechecks; at most100 suggestions are stored, with excess count visibly reported and audited. Original timing proof and Unicode equivalence checks are retained.
- Notes-save warnings use the same disjoint counts as the audit, including accepted suggestions and left-blank decisions.

## Evidence and next action

Original execution: `/tmp/claude-1000/-opt-meddoc-pro/64d93580-8414-4553-b17d-ed04b0550ae1/scratchpad/v1/review-repair4/` (`mutation.log`, `mutation-results.json`, `pre-mutation.sha`, individual before/after reports). Initial dirty patch was preserved in `.runtime/v1-astra-recovery-20260927/v1-review-initial.patch`. No source reset, process termination, provider call, activation, deployment, payment or lock deletion.

Run the finished-diff adversarial pass before integration. This is local branch evidence, not installed proof or a V1 readiness claim. Shared deployed tree remains on dedac162 with maintenance and synthetic-only enforcement.

## Independent finished-diff refutation and wording repair

The notes recovery agent independently refuted `b15c44c6` against merge-base `f77c3d35`: no demonstrated
finalized-write, revision-identity, raced coding-writer or cap integrity defect. It reproduced a LOW
message provenance issue: a never-existent code UUID at a genuinely stale notes revision was called a
deleted suggestion. Root reproduced it before fixing only the wording to state unavailability and the
observed notes change. No control flow or locking changed. The new regression and four updated message
assertions passed with the existing review-guard suite: 79 tests in 64.638 seconds, zero failures. The
independent refuter re-read that final diff and confirmed its demonstrated concern closed.

Logs: root `.runtime/v1-astra-recovery-20260927/review-warning-{before,after}.log`. The earlier 1,224-test
core result remains attributed to the earlier code; the final wording change uses these focused checks.
