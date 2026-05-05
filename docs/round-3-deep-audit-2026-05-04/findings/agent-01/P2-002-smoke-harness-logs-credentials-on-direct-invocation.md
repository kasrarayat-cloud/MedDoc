---
id: A01-P2-002
severity: P2
title: "smoke-harness.js logs URL/EMAIL/PASSWORD when invoked directly"
domain: Credential & secret hygiene
files:
  - smoke-harness.js:96
  - apps/meddoc-pro/scripts/seed-tenancy-fixtures.ts:223
---

## Issue
Two scripts log credentials to stdout. Each is bounded but worth flagging.

`/opt/meddoc-pro/smoke-harness.js:95-96` logs the test password whenever the file is run directly:
```js
if (require.main === module) {
  console.log({ URL, EMAIL, PASSWORD, TS });
}
```

`PASSWORD` is generated as `Smoke${TS}!Aa` (line 12) — i.e. a short prefix + a Unix-millisecond timestamp + suffix. So while it's ephemeral and tied to a smoke-test account that gets cleaned up, anyone reading the smoke run logs (e.g. a CI artifact, a `tee`'d file, a journald capture) sees the password.

`/opt/meddoc-pro/apps/meddoc-pro/scripts/seed-tenancy-fixtures.ts:223` logs the seeded test password:
```ts
console.log(`  Password for all test users: ${TEST_PASSWORD}`);
```

This script populates the dev DB with predictable test users. If `TEST_PASSWORD` ever defaults to a non-throwaway value or someone mistakenly runs the script against staging/prod, the log line ends up in journald and any operator's terminal scrollback.

## Evidence
`/opt/meddoc-pro/smoke-harness.js:8-13`:
```js
const URL = 'https://app.quillmd.com';
const MARKETING = 'https://quillmd.com';
const TS = process.env.SMOKE_TS || String(Date.now());
const EMAIL = `qa-smoke-${TS}@quillmd-test.local`;
const PASSWORD = `Smoke${TS}!Aa`;
const NAME = 'Dr. Smoke Tester';
```

`/opt/meddoc-pro/smoke-harness.js:94-97`:
```js
// Allow direct invocation for sanity check.
if (require.main === module) {
  console.log({ URL, EMAIL, PASSWORD, TS });
}
```

`/opt/meddoc-pro/apps/meddoc-pro/scripts/seed-tenancy-fixtures.ts:222-223`:
```ts
console.log('\n  Tenancy fixtures seeded.');
console.log(`  Password for all test users: ${TEST_PASSWORD}`);
```

## Risk
1. CI logs and journald capture credentials. Even ephemeral test creds joining a corpus of leaked QA data (e.g. via a misconfigured log shipper) hands attackers free QA-tenant access.
2. The smoke-harness pattern (`PASSWORD = Smoke${TS}!Aa`) is predictable: knowing the smoke-run timestamp lets an attacker reconstruct the password and re-use the QA account.
3. If a future hand of `seed-tenancy-fixtures.ts` swaps `TEST_PASSWORD` for an env-var that's accidentally pointed at a real password, the same `console.log` exposes it.

## Recommended fix
1. `smoke-harness.js`: in the direct-invocation branch, print only `{ URL, EMAIL, TS }` and either redact PASSWORD (`PASSWORD: '<sha256:' + sha256(PASSWORD).slice(0,8) + ...>'`) or omit it entirely.
2. `seed-tenancy-fixtures.ts`: replace the password log with `console.log('  Password for all test users: <see TEST_PASSWORD env var>')`. Force operators to read it from their own env, not the script's stdout.
3. Add a lint rule (eslint-plugin-no-secrets or a custom AST check) that fails CI on `console.log` statements that interpolate any identifier matching `/password|secret|key|token/i`.
