# Stripe sandbox readiness — 2026-09-19

## Decision

Real Stripe sandbox verification is **blocked on sandbox access**. No Stripe
payment, decline, event, refund or provider-cost reconciliation was executed in
this milestone. Native Word acceptance and reviewer-host qualification remain
complete; external reviewer access remains inactive.

## Actual host evidence

- Repository inspected at `e42c3c46007d973bb85ebd7ccec3dc3df20e0bfe` (PR1226).
  Both private surfaces independently report served release
  `dc4eb42ce021e436a3b717eb40edb10ace8e662c`, HTTP200, synthetic-only.
- Protected fresh `.env` has no Stripe test key or webhook signing secret.
  The preserved environment has no reusable Stripe key. CLI1.51.0 is installed;
  its regular operator-owned0600 config has no paired test credentials.
  No secret values were logged or copied.
- Ran the **existing unchanged runner** from the permanent rebuild against the
  actual served release with `--dry-run`. Both loopback doctor names passed.
  The unsigned webhook probe received503 because its signing secret is absent;
  runner exited1 before login/checkout. Exactly0 checkout submissions,0 Stripe
  CLI invocations and0 Stripe hosts contacted. This is a correct refusal.
- Evidence: `.runtime/stripe-sandbox-verification-dc4eb42ce021-dry-run.json`,
  2663bytes, SHA256
  `e99ec0096015c757ea33fb2d88ea26c89f4247bef0ca6ba6a921e94b12f1f721`.
  Preserve this failed readiness attempt. Do not overwrite it on a later run.

## Demonstrated reporting defect and bounded repair

Executing the original final reporting block with synthetic in-memory outcomes
reproduced two false passes: skipped duplicate/refund checks with no CLI; and an
unconfirmed duplicate arrival with retry/out-of-order still manual. Both emitted
`passed:true` and “Stripe sandbox verification passed.” These are offline reporting
counterexamples, not Stripe transactions or application ledger tests.

The runner now requires the operator CLI before execution, records attempted
checkout submission immediately, and marks unconfirmed duplicate arrival explicitly.
An incomplete required case prevents full acceptance and returns exit2. Dry-run
readiness is separately labelled “not attempted.” A failure after submission can
no longer look like nothing was attempted. Decline checks now also require the
promotional wallet to remain unchanged. No signature, ledger, welcome-credit,
reservation, 1.5× usage policy or provider integration implementation changed.

Focused local checks:8 outcome tests,5 existing credential gates,0 failures/skips,
plus JavaScript syntax. The credential tests use no database or provider. The
actual repaired final block independently produced `passed:false`, exit2 and the
three outstanding receipt/retry/order cases. Independent refutation found no
reachable regression. CI includes the outcome checks; these tests are simulated
classification/credential evidence, not real Stripe sandbox verification.

Raw evidence under `.runtime/stripe-readiness-20260919/`: original counterexamples,
repaired final-block result, test logs and `readiness.json` (SHA256
`b54b006953017189b30982ab5e865c162faea8a5b9133a3cb38edaad3b39c7bb`).
The append-only private checkpoint records final repository/CI revision separately.

## Next execution milestone

The [runbook](external-verification-runbook.md) retains local CLI forwarding.
[Stripe documents local resend support](https://docs.stripe.com/cli/events/resend)
and [stable listener secrets across restarts](https://docs.stripe.com/cli/listen).
No new public endpoint, purchase or routine app restart is required by those facts.

After the [single secure owner setup](owner-actions.md), engineering loads the
configuration through private activation rules and inspects existing attempt files.
Use one bounded$5 successful checkout, a$2 refund and a declined second checkout;
correlate authentic Stripe event IDs with application receiver attempts, payment
rows and ledger/wallet deltas. A separate bounded order-control exercise must prove
early-refund handling and retry without stopping the application. That procedure
remains unexecuted; do not mistake the current runner for an automated order test.
Supplemental receipt evidence belongs in a new additive report, never a rewritten
attempt. Funding/refund evidence does not reconcile Anthropic/Deepgram usage costs.

## Preservation and limits

Public app/admin503, marketing/www200, retired pro410. Doctor/admin/worker PIDs
412838/412839/412840 and start timestamps remained unchanged during preparation.
No deploy, application config change, cleanup, reviewer activation or data reset.
Protected originals, exports, failed attempts and audit history are retained.
Preflight was FIX-AND-GO at85% disk,46GiB free; no auto-fix, cleanup or restart.
The other external inputs are one deferred checklist in owner-actions.md.
