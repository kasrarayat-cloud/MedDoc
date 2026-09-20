# Real Stripe sandbox verification — 2026-09-20

## Result

The prepared bounded batch **passed against real Stripe sandbox events** in
owner-approved New business sandbox, `acct_1TJdCaRoIb7mTS9U`. No live payment,
purchase, AI, transcription or email request occurred.

| Demonstrated case | Measured result |
| --- | --- |
| Funding | Two $5 Checkout payments through the actual doctor interface; exactly two +$5 ledger entries |
| Decline | Real hosted-card decline; no funds or payment credit; unpaid session explicitly expired during cleanup and application status became expired |
| Refunds | Two authentic $2 operator refunds; exactly two −$2 application ledger entries |
| Duplicate | Original and duplicate completion both reached the application with HTTP200; no duplicate credit |
| Controlled retry | Same authentic event produced connection-refused/503 at the closed project loopback destination, then application200 after forwarding restoration; identical payload hash and unchanged ledger |
| Refund before completion | Both authentic refund events first received409 and persisted reconciliation/attempt1; later completion200 automatically processed both at attempt2 and debited once |
| Administration | Existing synthetic administrator authenticated with MFA and viewed genuine payment, refund and processed-event rows; no-factor attempt granted no access |

Final paid balance: **$6.000000000000**. Personal promotional balance remained
**$9.782275898950**, with exactly one **$10** welcome grant. Other wallets and
job/usage/provider-receipt counts were unchanged. All **seven** stored Stripe
events are processed; failed-delivery and reconciliation audit history remains.
Stripe API projections independently confirm both USD500 sessions paid and both
USD200 refunds succeeded. The separate expiration result supersedes the earlier
projection of the declined session as open/unpaid.

## Configuration and running identity

The transferred restricted sandbox key was atomically installed into the existing
fresh `.env`, preserving other entries, claude ownership and0600 mode. Its
protected handoff file and exact temporary owner SSH authorization were removed
after installation verification. Shared SSH policy and password state were not
changed. The paired operator CLI handles inspection/refunds/resend; the restricted
application credential handles Checkout. No secret value is recorded here.

The listener's own signing secret was installed securely. A declared configuration
reload restarted only the three private services at00:46:30UTC. Full database-row
fingerprints, private file inventories and unit policies were unchanged; fresh
startup proofs match each actual service identity. Doctor/admin/worker PIDs are
1625162/1625163/1625164. Served application remains
`dc4eb42ce021e436a3b717eb40edb10ace8e662c`. This was no application release deploy.
Primary tooling used merged `e9bb7965a14f73fa2de53c7dd53490f6bca0c2a7`, with passing
CI35479613280 and secrets35479613276; final tooling changes receive their own
citation in the private continuation checkpoint. No restart is needed for them.

## Failures preserved and repaired

The original dry-run503 correctly represented absent configuration; the configured
receiver now rejects unsigned requests with400. PR1228 repaired return-navigation
observation: the legitimate unauthenticated login redirect must be observed as an
HTTP request chain. It also added exclusive named attempt reports.

The first authentic Checkout was created successfully but its payment-field lookup
failed. Stripe confirmed open/unpaid/no PaymentIntent. Inspection demonstrated
Stripe's Card radio overlay and the disabled, already-selected USD button. The
same original Checkout was resumed after actual pointer/field-visibility proof;
no replacement successful Checkout was created. The failed report remains intact.
Private continuation and supplemental scripts supplied the actual batch evidence;
new permanent selector regressions are separately labelled isolated browser tests.

The continuation correctly returned2 for incomplete acceptance before supplemental
checks. The generic wrapper incorrectly asserted no action had occurred. That
assertion is withdrawn: payment/refund records prove otherwise. The focused wrapper
repair requires inspection of child semantics and evidence before any rerun.

## Evidence and cleanup

Private evidence root: `rebuild/.runtime/stripe-payment-20260920/`.
Read `acceptance.json`, `final-ledger.json`, `provider-final-projections.json`,
`declined-checkout-expired.json`, `forwarding-receipts.jsonl`, both redacted listener
logs, `supplemental-admin.json`, `config-reload-result.json` and `cleanup.json`.
Acceptance SHA256: `ae8cd797b4f8f91a2e80c4a80150b124034849711f638ca7a5853b112b8c1fab`.
The exclusive original and continuation reports are preserved; later acceptance
is additive. A manifest records artifact hashes and sizes.

Temporary CLI listeners and the receipt proxy are stopped;9149/9159 are closed.
Signing secrets were redacted from retained listener transcripts and their private
raw duplicates removed. Application credentials remain protected. Restart the
protected CLI forwarding workflow for later private sandbox tests; there is no
permanent public webhook endpoint. Public app/admin remain503, marketing/www200,
retired pro410. Reviewer access stays inactive and real patient data stays disabled.

## Limits and next milestone

This is authentic payment-object-to-ledger evidence. It does **not** establish
Anthropic/Deepgram cost reconciliation, Stripe fee/payout/invoice reconciliation,
Stripe's automatic retry timetable, or live concurrent AI spending against a
refund. The existing isolated concurrency evidence remains separate. Welcome-credit
rules and the1.5× usage policy were not changed. This is no public-launch approval.

No further Stripe owner credential is needed for this private sandbox milestone.
Next: complete controlled Resend invitation/recovery delivery using the authorized
owner-controlled inbox after secure identity/configuration verification. Offsite
destination/credentials and independent key custody, authentic provider billing
records, reviewer engagement, CPT rights and patient-data agreements/controls remain
deferred gates; do not reopen completed native Word or reviewer-host qualification.
