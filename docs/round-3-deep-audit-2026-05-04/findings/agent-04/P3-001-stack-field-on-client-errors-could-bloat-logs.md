---
id: A04-P3-001
title: client-errors `stack` field 10 KB cap is reasonable; `userAgent` cap could be tighter
severity: P3
domain: Input validation / log hygiene
status: open
---

## Summary

`apps/transcribe-md/src/app/api/client-errors/route.ts:37-45` already has bounded inputs (good — this is the unauth public sink). One nit:

- `userAgent: z.string().max(500).optional()` — real-world User-Agent strings rarely exceed 250 chars; capping at 500 is fine, but the `url` field is `.max(2_000)` which is realistic for a deep-linked URL with query params. If telemetry tightens, drop these to 256 / 1024 respectively.

The 10 KB `stack` cap is appropriate — React stack traces with hydration mismatches can run long.

## Evidence

`apps/transcribe-md/src/app/api/client-errors/route.ts:37-45`:
```ts
const BodySchema = z.object({
  errorId: z.string().min(1).max(100),
  scope: z.string().min(1).max(60),
  message: z.string().max(1_000).optional(),
  stack: z.string().max(10_000).optional(),
  digest: z.string().max(200).optional(),
  url: z.string().max(2_000).optional(),
  userAgent: z.string().max(500).optional(),
});
```

## Recommended fix

Optional polish: consider adding `.url()` on the `url` field. A strict URL validator would reject pathological values without breaking legitimate next-app paths. The route is unauth, so the bot-spam guard at line 51 (`RATE_LIMITS.CLIENT_ERRORS`) is the real defence.

## Files

- `/opt/meddoc-pro/apps/transcribe-md/src/app/api/client-errors/route.ts`
