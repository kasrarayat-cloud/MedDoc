---
id: A01-P2-001
severity: P2
title: "AUTH_SECRET dev fallback `'dev_secret_change_in_production_min_32_chars_xyz'` is a hardcoded literal in shipped source"
domain: Credential & secret hygiene
files:
  - packages/auth/src/index.ts:115
---

## Issue
`packages/auth/src/index.ts:115` defines a fallback for `process.env.AUTH_SECRET`:

```ts
secret:
    process.env.NODE_ENV === 'production' &&
    process.env.NEXT_PHASE !== 'phase-production-build' &&
    !process.env.AUTH_SECRET
      ? (() => { throw new Error('AUTH_SECRET is required in production. ...'); })()
      : process.env.AUTH_SECRET || 'dev_secret_change_in_production_min_32_chars_xyz',
```

The author has correctly hard-failed in production when AUTH_SECRET is unset (T-M16.3 fix). However, the literal string `'dev_secret_change_in_production_min_32_chars_xyz'` is now permanently in the public source tree as a fallback for non-production environments — including E2E tests, dev environments, and anyone running `next dev` locally.

Since NextAuth's JWT signing secret == this literal in dev, **every dev / test instance globally uses the same JWT signing key**. Anyone who reads the source can mint forgeable JWTs against any unhardened deployment of QuillMD that runs in non-production mode (e.g. a contractor's clone, a staging that forgot to set NODE_ENV, an attacker's instance posing as a phishing target).

## Evidence

`packages/auth/src/index.ts:106-115`:
```ts
secret:
    process.env.NODE_ENV === 'production' &&
    process.env.NEXT_PHASE !== 'phase-production-build' &&
    !process.env.AUTH_SECRET
      ? (() => {
          throw new Error(
            'AUTH_SECRET is required in production. Set it in /opt/meddoc-pro/.env (openssl rand -base64 32) and recreate the app containers.'
          );
        })()
      : process.env.AUTH_SECRET || 'dev_secret_change_in_production_min_32_chars_xyz',
```

The same package will be published / consumed by both apps (transcribe-md and meddoc-pro). The literal travels with the code in `node_modules/@meddoc/auth`.

## Risk
1. Dev cookies signed with a globally-known string — phishing demos, contractor environments, staging mistakes all become identical-key attack vectors.
2. If `NODE_ENV` ever gets unset by a startup script bug (e.g. missing env file), the prod-throw branch is bypassed and the literal becomes the prod signing key silently.
3. Compliance auditors flag any committed signing-key default — even one labelled "dev" — as a P2 issue under HIPAA's "no shared cryptographic material across environments" guidance.

## Recommended fix
Two cleaner alternatives:

(a) Use a per-process random in dev too:
```ts
const DEV_AUTH_SECRET = process.env.AUTH_SECRET || crypto.randomBytes(32).toString('base64');
```
This signs every dev session with an ephemeral key — anyone who restarts dev invalidates their old session, but no shared key exists.

(b) Hard-fail in dev as well, with a friendlier message that prints `openssl rand -base64 32` for copy-paste:
```ts
secret:
  process.env.AUTH_SECRET ||
  (() => { throw new Error('AUTH_SECRET unset. Run: openssl rand -base64 32, set it, retry.'); })(),
```

Either option removes the fixed literal from the binary.
