# Private billing-policy activation — 2026-09-17

The owner directs: charge exactly 1.5 × the attributable metered provider cost
after applicable discounts and allocated provider credits; track fixed overhead
separately; absorb the provider cost of platform-failure retries; keep exactly
one $10 welcome credit per eligible new user; keep promotional and paid
balances, reservations, charges and refunds separate; distinguish configured
estimates from reconciled actual costs; apply reconciliation only through
auditable, appended ledger entries; never rewrite history.

Current running release is 8f8a6763b80d345e432074df64b907c2db50be2a,
synthetic-only, three dedicated-identity services, public maintenance. The
fresh live Word run (encounter 066488ba, job 8d43fadb, one Anthropic request,
zero clinician corrections) is complete and its encrypted backup
20260917T234313Z-56be2efa was restored and validated before this act.

This deploy ships a TREE, not one change. The range from the running release to
the target contains: PR #1186 (documentation, the tracked live runner, the
reviewer tunnel script), PR #1187 if merged (credential-gated verification
runners and a runbook; scripts only, never executed), and the billing-policy
change: configured discount fraction in the versioned pricing fingerprint;
CostReconciliation and PlatformCost models; appended ledger kinds
'reconciliation' and 'absorbed'; automatic absorption of settled provider cost
whose output was not adopted; administrator console actions for reconciliation,
fixed overhead and uncertain-job resolution; updated billing pages; extended
read-only audit. No provider, payment or email integration changes.

Expected delta, declared before the act: exactly two new empty tables
(core_costreconciliation, core_platformcost) and one django_migrations row
(core.0012_billing_policy). All 33 existing tables keep identical rows and
columns, including every usage, ledger, wallet, reservation, receipt, audit and
encounter row. Private originals, exports, receipts and mail bytes unchanged.
Installed units, the pinned Word runtime, static asset policy and the six
protected shared containers unchanged. Only the release line of the protected
environment changes; no new keys, no discount value (default remains 0). Zero
provider calls. Public statuses remain www 200, app/admin 503, pro 410.

Consequence recorded: every job queued after activation carries a new
configured-v1 pricing fingerprint because the price dictionary gains the
discount key at its default of zero; earlier rows are not rewritten. The
private one-job verifier's fingerprint recomputation must be updated before it
is used on later jobs.

Before this act: the finished diff passes independent refutation, branch CI and
exact merge CI; scripts/activate-billing-policy.py runs read-only from
permanent main and passes. Then it runs once through run-ruled-mutation.sh with
this committed declaration: stop the three private services, record full
schema and row fingerprints, fast-forward main, apply only the validated
migration through the migrator role, verify the two empty tables and identical
existing rows, run Django checks and collectstatic, replace only the release
line, start the same units, verify same-PID identity proofs, interfaces,
health at the exact target, fingerprints, files, units and co-tenants. Any
failure stops the services and retains the lock and evidence; never rerun
blindly. Afterwards: read-only billing audit, an administrator console check
of the new sections, and a new encrypted backup with isolated restore proof.
No claim of invoice reconciliation, Stripe, Resend delivery, offsite
restoration or independent testing follows from this activation.
