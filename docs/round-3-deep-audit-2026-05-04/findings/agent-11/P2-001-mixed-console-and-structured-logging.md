---
id: A11-P2-001
severity: P2
domain: error-handling-observability
title: 100+ raw console.log/error/warn calls coexist with the structured log wrapper — log aggregation will be lopsided
---

# A11-P2-001 — Inconsistent logging: 49 raw `console.error`/`warn` sites vs. 57 `log.*` structured sites

## Issue

`apps/transcribe-md/src/lib/log.ts` introduces a tiny structured-log
wrapper that emits one JSON line per call (`ts`, `level`, `scope`,
`message`, `…data`). It correctly routes `error`/`warn` to stderr and
`info`/`debug` to stdout — perfect for a Docker stdout/stderr pipeline
or a future Loki/Vector ingest. The doc-comment even says "covers the
high-volume lifecycle + milestone logs that a future log pipeline
would want indexed."

But the migration is half-done. Counts in `apps/transcribe-md/src` (excluding
tests):

- **49** raw `console.error` / `console.warn` call sites
- **57** structured `log.info` / `log.warn` / `log.error` call sites

A future Loki query for "all warnings on the upload path in the last 4 h"
will get a clean answer for the half that uses `log.warn(...)` and a
ragged grep-against-prefix-strings for the half that uses
`console.warn('[api:visits:upload] foo')`. Every console.* line is
unstructured: no automatic parser will index `scope`, `errorId`, `userId`
from `console.error('[api:visits:upload] queue enqueue failed:', err)`.

Worse: the worker's two main happy-path lines use `log.info`, but the
critical failure path
(`apps/transcribe-md/src/worker.ts:691-693, 738-742, 798-803, 826-832`)
uses raw `console.error`. Exactly the lines on-call needs are the ones
that *won't* be indexed.

The **marketing app has neither** — no structured logger, no console
discipline.

## Evidence

```
$ grep -rln "console\." apps/transcribe-md/src 2>/dev/null \
   | grep -v ".next" | grep -v ".test." | wc -l
14   # files using console

$ grep -rn "console\.error\|console\.warn" apps/transcribe-md/src \
   2>/dev/null | grep -v ".next" | grep -v ".test." | wc -l
49

$ grep -rn "log\.info\|log\.warn\|log\.error\|log\.debug" \
   apps/transcribe-md/src 2>/dev/null | grep -v ".test." | wc -l
57
```

`apps/transcribe-md/src/lib/log.ts:5-19` (existence of the wrapper):
```ts
// Tiny structured-log wrapper (T-M16.4 M9)
// Writes one JSON object per line to stdout. ...
// Scope is reserved for forward migration — NOT a full pino-style
// replacement. Most existing console.* calls stay as-is; this helper
// covers the high-volume lifecycle + milestone logs that a future log
// pipeline would want indexed.
```
Acknowledges the half-migration.

Sample failure-path inconsistency in `apps/transcribe-md/src/worker.ts`:
- Line 1058: `log.info('transcribe-md-worker', 'visit completed', {...})`
- Line 1064: `console.error('[transcribe-md-worker] job …  FAILED:', err)`

## Risk

Pre-pilot, this is cosmetic. But once a Loki / Datadog / Vector pipeline is
configured and dashboards/alerts are written against the JSON shape, every
remaining `console.error` is invisible to those queries. The 2-AM debugging
flow becomes: "your dashboard says 0 errors, but `docker logs transcribe-md
| grep -i fail` shows 12 in the last hour" — the kind of mismatch that
erodes trust in the observability stack.

Also: PHI redaction is more reliable when funneled through one wrapper.
Today every console.error site has its own `redactPhi(err.message)` call
— some sites have it (`worker.ts:741`), some don't (`api-error.ts:100`
DOES, `command-palette.tsx:67` does NOT — though that one is browser-side
where PHI shouldn't appear). One missed `redactPhi` and an error message
quoting `patientName` lands in stdout unscrubbed.

## Recommended fix

1. Pick one logger surface and migrate. The existing `log` wrapper is
   fine; tighten it by:
   - Add `redactPhi()` inside the wrapper (default-on for `data` values
     that are strings) so call sites don't have to remember.
   - Add a `requestId` and `userId` field convention.
2. Mechanical migration: replace every `console.error('[x:y:z] msg:', err)`
   with `log.error('x:y:z', 'msg', { error: redactPhi(err) })`. ESLint
   rule `no-console` (off in `error`/`warn` today; turn on after migration).
3. Mirror `lib/log.ts` to `apps/marketing/src/lib/log.ts`.
4. Document the convention in CLAUDE.md and the contributor guide so
   new code doesn't drift back.

This is P2 not P1 because the existing pattern works; the cost is
operational friction once observability tooling lands. Worth fixing
in a single mechanical sweep before pilot expansion.
