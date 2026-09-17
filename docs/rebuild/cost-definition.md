# Billable usage definition for private testing

QuillMD usage is metered provider usage × the configured USD unit rate captured with each usage row, followed by an exact ×1.5 charge. This definition excludes VPS hosting, payment fees, taxes and licenses. No automatic payment or wallet refill exists. Promotional credit is personal and is consumed before the authorized paid payer. The payer is fixed when a reservation is authorized. Unused reservations release on known outcomes; uncertain provider outcomes hold for reconciliation and never retry automatically.

Text generation: returned input/output/cache token counts, priced by the configured model's published standard API rates. The live verified configuration is Anthropic claude-sonnet-4-6 at $3 input/$15 output/$0.30 cache-read per million tokens; cache writes are not requested. OpenAI adapter is implemented but its existing key returned 401. Source: https://platform.claude.com/docs/en/about-claude/pricing (verified 2026-09-17).

Voice: Deepgram nova-3-medical prerecorded audio, provider-returned seconds, $0.0043/minute public pay-as-you-go rate. Round the computed provider cost once to USD 0.0000000001 (half-even); multiply that defined cost by 1.5 exactly. This avoids rounding per-second repeating decimals. Source: https://deepgram.com/pricing (verified 2026-09-17). No optional billed add-ons requested.

Amounts retain twelve decimal places in the ledger; UI may show rounded dollars, but the ledger records exact amounts. Actual charges are never based on reservation estimates. Every simulated provider execution costs zero. Welcome credit is a unique append-only $10 grant after mailbox verification, including invitation acceptance. Stripe credits arrive only through validated, idempotent events; browser redirects do not grant funds.

Before real paid use, confirm account contract discounts and treatment of provider promotional credits against invoices, tax jurisdiction, refund policy, and accepted definition of included costs. Public list rates are verified; the account-specific provider invoices are not yet reconciled. Patient-data processing remains disabled. Stripe live mode is deliberately disabled; test keys and webhook secret are still needed.

Integration detail: the queued provider rate snapshot and user-approved maximum must remain fixed for the life of a job. Configuration changes must not silently change an already authorized job's rate. Reservation affordability and ledger writes are locked in PostgreSQL transactions; duplicate provider payment intent IDs and usage job IDs are unique.
