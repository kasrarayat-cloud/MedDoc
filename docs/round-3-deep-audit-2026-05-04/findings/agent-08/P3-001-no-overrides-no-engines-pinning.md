---
id: A08-P3-001
title: Root package.json lacks `overrides`, `engines`, and `packageManager` pinning
severity: P3
domain: dependency-hygiene-supply-chain
status: open
---

## Issue

`/opt/meddoc-pro/package.json` declares 3 scripts and 3 dev-deps. It is missing three
fields that are cheap-to-add and meaningfully tighten the supply-chain story for an npm
workspaces monorepo:

1. `engines` — no Node / npm version constraint.
2. `packageManager` — no pinned `npm@X.Y.Z` (Corepack support).
3. `overrides` — no explicit transitive-dep pinning hooks (would be useful for the
   audit-clearing tactics in A08-P2-002, e.g., forcing `postcss@>=8.5.10` until next ships).

## Evidence

```bash
$ python3 -c "import json; d=json.load(open('/opt/meddoc-pro/package.json')); \
              print('overrides:', d.get('overrides')); \
              print('engines:', d.get('engines')); \
              print('packageManager:', d.get('packageManager'))"
overrides: None
engines: None
packageManager: None
```

The three Dockerfiles all use `node:22-alpine`, but a developer working on a laptop with
Node 20 or Node 24 won't be warned. CI doesn't currently fail on a Node-version mismatch.

## Risk

- **Low** — this is hygiene/polish.
- The most concrete failure mode: a clinician or contractor runs `npm install` on Node 18
  (still LTS as of audit date), hits a subtle TypeScript / Prisma incompatibility that
  doesn't reproduce in CI, and loses a day. With `engines.node: ">=22.0.0"` and
  `engine-strict=true` in `.npmrc`, the install fails fast with a clear message.

## Recommended fix

```diff
 {
   "name": "meddoc",
   "version": "0.1.0",
   "private": true,
+  "engines": {
+    "node": ">=22.0.0 <23.0.0",
+    "npm": ">=10.0.0"
+  },
+  "packageManager": "npm@10.9.0",
   "workspaces": [
     "apps/*",
     "packages/*"
   ],
+  "overrides": {
+    "next-auth": "5.0.0-beta.31",
+    "postcss": ">=8.5.10"
+  },
```

Plus a `/opt/meddoc-pro/.npmrc`:

```
engine-strict=true
save-exact=false
audit-level=moderate
```

Pair with `corepack enable` documented in the README so dev environments use the pinned npm
exactly.

## Cross-domain hooks

- A08-P1-001 (next-auth pin): the `overrides` block is the clean spot to enforce the pin
  globally.
- A08-P2-002 (npm audit clearance): `overrides.postcss` is the official way to skip the
  spurious "downgrade next" suggestion until next 16.2.5 ships.
