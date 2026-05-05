---
id: A09-P2-002
title: No idempotency keys on outbound Resend / Anthropic / Deepgram calls — duplicate sends on retry
severity: P2
domain: external-integration / idempotency
---

## Issue
None of the outbound API integrations carry idempotency keys:

- **Resend** (`apps/transcribe-md/src/lib/email.ts:190-240`):
  `client.emails.send({...})` without an idempotency key. Resend supports
  the `Idempotency-Key` header (it's documented). On a transient 5xx + retry
  the same email goes out twice.
- **Anthropic** (`packages/ai/src/anthropic.ts`): no `Idempotency-Key`
  header. Anthropic's API supports it as of late 2024 — `anthropic-beta`
  header `messages-2024-…` etc. A retry-after-timeout (e.g. our worker's
  T-M11 15-min cap, or BullMQ retry) re-runs the same prompt, charges
  twice.
- **Deepgram batch** (`packages/ai/src/deepgram-batch.ts`): no
  idempotency. The pipeline's L1 retry path
  (`apps/transcribe-md/src/worker/layers/01-transcribe.ts:71-83`) on
  network blip does a second `attempt()` — if the first request actually
  succeeded server-side but the response was lost, we charge for two
  transcripts.

## Evidence
`grep -rn "anthropic-beta\|Idempotency-Key\|idempotency-key\|x-idempotency"
packages/ai/ apps/transcribe-md/src/lib/`: zero hits.

`apps/transcribe-md/src/lib/email.ts:196-203`:
```ts
const result = await client.emails.send({
  from: resendFrom(),
  to: args.to,
  subject: args.subject,
  html: args.html,
  text: args.text,
});
```
No `idempotencyKey` field. The Resend Node SDK accepts one as
`{ idempotencyKey: string }` in the request options.

`packages/ai/src/anthropic.ts` — uses `anthropic.messages.create()` without
the `Idempotency-Key` header. The SDK exposes a `headers` option per
request.

## Risk
P2 — cost overruns + occasional duplicate-email spam. Severity:
- A 4-attempt BullMQ chain on a flaky upstream burns 4× the API cost. Real
  cost impact at pilot scale.
- Duplicate emails to doctors are annoying but not safety-critical.
- Resend is the same path used for password reset and email verification.
  A retry there sends the user two confirmation emails — confusing but
  bounded.
- For Anthropic specifically: a retried L4 SOAP draft → two different
  SOAP drafts (sampling temp 0.2 means non-deterministic). The second
  one wins — but the first one's tokens are already paid for and the
  AiCall row is in the DB, double-counting `processingCostCents`.

## Recommended fix
1. **Anthropic** — add a stable idempotency key to every messages.create
   call. Build it as `<visitId>:<layer>:<attempt>` so a BullMQ retry
   reuses the same key and Anthropic dedupes:
   ```ts
   const idempKey = `${visitId}:${purpose}:${attemptNumber}`;
   await anthropic.messages.create({ ... }, {
     headers: { 'Idempotency-Key': idempKey },
   });
   ```
   Anthropic's window is 24 hours, plenty for our retry semantics.

2. **Resend** — pass an idempotency key derived from the visit + delivery
   channel: `tx-md-{visitId}-{channel}-{attempt}`. Resend dedupes within
   2 minutes per their docs (verify before shipping).

3. **Deepgram** — Deepgram doesn't currently expose idempotency keys (as
   of last I checked their docs). The mitigation here is application-side:
   T-M13's resume logic should already short-circuit if `transcriptRaw`
   is populated; verify that the L1 retry path in
   `apps/transcribe-md/src/worker/layers/01-transcribe.ts` consults the
   layer-skip state before issuing the second `attempt()`. (Looking at
   the current code, the inner retry is BEFORE any DB write — so this
   case is the "first request succeeded server-side but we lost the
   response" edge, which is rare.)

Also: log the idempotency key into AiCall metadata so duplicate-detection
can be done at audit-review time.
