# Billing provenance and payment lifecycle — 2026-09-17

## Scope and evidence limits

This continuation inspected only the fresh application's synthetic records. It did not import old application data, create another provider request, send email, or charge a Stripe payment. Names-only inspection found no Stripe configuration variables in either the preserved root environment or the fresh application environment. Actual Stripe sandbox checkout and webhook delivery therefore remain unverified; signed local event tests are not a completed Stripe integration.

The cost evidence is **provider-metered units multiplied by configured USD rates**. It is not an account invoice. Reservations are estimates of the maximum authorized charge. The configured pricing fingerprint added here identifies a set of application settings; it is **not** a provider contract rate version, tariff attestation, account discount, or invoice reconciliation.

The published-rate references were reviewed on **2026-09-17**: Anthropic input/output/cache-read rates of $3/$15/$0.30 per million tokens for the configured Sonnet model, and Deepgram prerecorded nova-3-medical at $0.0043 per minute. The record uses one half-even rounding of voice cost to $0.0000000001, then exactly 1.5×. Account invoice exports, discounts, provider promotional credits and the final commercial cost definition remain external dependencies. [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing), [Deepgram pricing](https://deepgram.com/pricing).

## Existing real synthetic executions

Read-only audit: **6 executions**, **10 wallets**, all recomputed defined costs, exact multipliers, ledger debits and wallet/reservation sums matched. Total defined cost **$0.009454150100**; total user charge **$0.014181225150**, all consumed from the synthetic doctor's personal promotional balance.

| Job ID | Provider | Recorded units | Defined cost USD | Charge USD | Durable receipt / enqueue config |
| --- | --- | --- | --- | --- | --- |
| `a711bf3b-7b79-4129-9e77-22c6368fb398` | Anthropic | 535 input / 79 output / 0 cached | 0.002790000000 | 0.004185000000 | Absent / absent |
| `31edf744-8bc8-4451-9f59-309f4e7aaf77` | Deepgram | 1.0 seconds | 0.000071666700 | 0.000107500050 | Absent / absent |
| `fbdb7c97-472c-40f2-8d1b-1be35db4094b` | Anthropic | 535 input / 79 output / 0 cached | 0.002790000000 | 0.004185000000 | Present / present |
| `1e976bb7-96c3-4baa-b4da-da308c4520aa` | Deepgram | 1.0 seconds | 0.000071666700 | 0.000107500050 | Present / present |
| `808b18f5-83d9-4d9d-a9ad-005dce4cd9f9` | Deepgram | 6.43 seconds | 0.000460816700 | 0.000691225050 | Present / present |
| `3a7843ce-445f-4ad2-a20c-77dc52bb0564` | Anthropic | 565 input / 105 output / 0 cached | 0.003270000000 | 0.004905000000 | Present / present |

The first two runs predate the durable receipt and enqueue snapshot implementation. All six retain settlement units/rates; none originally recorded the new configured-pricing fingerprint. No historical row was rewritten to manufacture missing evidence.

Anthropic's older `msg_…` values are **message resource IDs**, not HTTP request IDs. Historical HTTP request IDs were not captured and cannot be reconstructed from these rows. New executions store the SDK's public `_request_id` separately from `response.id`; Deepgram retains `metadata.request_id`. The administrator and billing screens distinguish both identifiers. [Claude SDKs](https://platform.claude.com/docs/en/api/client-sdks), [OpenAI Python SDK](https://developers.openai.com/api/reference/python).

Full exact identifiers and financial assertions from the initial audit are in the private worktree artifact `rebuild/.runtime/provider-provenance-audit.json` (0600). No clinical source text or credentials were exported.

## Repeatable audit

Run from the activated application directory after schema updates:

```sh
.venv/bin/python manage.py audit_billing --output .runtime/billing-audit.json
```

This command makes no provider calls or database writes. It recomputes provider unit costs, checks exact 1.5× charges, reconciles ledger debits and all wallet reservations, verifies attribution, compares durable receipts, and hashes stored provider result files without exporting their contents. It separately lists missing historical receipts, unsettled provider receipts, and unresolved jobs. Any arithmetic, receipt or stored-file mismatch exits nonzero. Missing historical evidence is explicitly named, not filled in. No invoice is labeled reconciled.

## Repairs and checks

- Signed Stripe events now retain an immutable, sanitized billing envelope and processing status even when settlement fails. No raw body, customer email or private metadata is stored. Admin shows attempts and reconciliation failures.
- Refund currency must be USD; identity and amount cannot change under an existing refund ID. Failed/pending refunds do not debit. Successful refunds cannot regress. Paid funds held for usage are not silently removed.
- Refunds arriving before payment confirmation remain auditable and are retried after the matching payment settles. Duplicate and concurrent events settle once; aggregate refunds cannot exceed the payment. Stripe explicitly does not guarantee delivery order and documents duplicate delivery. [Stripe webhooks](https://docs.stripe.com/webhooks), [Stripe refunds](https://docs.stripe.com/refunds).
- Failed and expired checkout sessions are visible. An early signed session event can bind its server-created local payment before the checkout response returns. A late failure cannot undo a paid event.
- A signed one-time submission token binds a repeated checkout to the original amount and wallet. Repeated clicks reuse the same session; uncertain creation is not automatically retried.
- Organization owners can explicitly select their organization's paid balance for funding. Other employees and revoked owners cannot. Personal promotional credit remains separate and is consumed first, with the organization recorded as the authorized paid payer.
- Database guards protect an authorized job's pricing snapshot and chosen payer. Exact provider HTTP/resource identifiers cannot settle twice, even if a model label changes.

The focused suite passed **50 tests** after the canonical-ID repair, including existing clinical, quote, payment and receipt-loss regressions. A subsequent check also tests the repeatable audit's response to deliberate synthetic result-file corruption. All provider HTTP adapters in these tests are mocked; payment events are locally signed synthetic fixtures on isolated PostgreSQL databases.

### Independent refutation and repair

An independent reviewer demonstrated two actual double-charge counterexamples against the first uniqueness constraints: changing `anthropic:model-a` to `anthropic:model-b`, and replaying an older message ID from the historical request column through the new resource column. Each could produce two usage/debit rows for one provider result.

Schema migration `0010` replaces model-qualified indexes with canonical provider-family and resource-ID expressions, preserving historical rows. The reviewer retested four independent regressions, including the normal worker: one execution succeeds; the duplicate retains its receipt, enters reconciliation, and does not adopt clinical output or debit again. The root agent independently verified all four tests pass on `0010`, then reversed **only its isolated test database** to `0009` and observed all four fail. That disposable database was dropped. No rollback or data rewrite occurred in the running fresh application.

## Remaining dependencies

- Stripe test secret key and a matching webhook signing secret; then actual sandbox checkout, failure, refund and webhook delivery verification. Live Stripe charging remains disabled.
- Provider account invoice/usage exports or equivalent authenticated account evidence, including discounts and promotional credits. Configured-rate calculations are not represented as invoice-settled costs.
- Confirmation of the commercial cost definition, tax treatment, refunds and payment disclosures before paid public use.
- One bounded postdeployment synthetic text request, coordinated by the root/UI agents, to confirm the new HTTP/resource IDs and pricing fingerprint in the real deployed queue. This report does not claim that future verification has already happened.
