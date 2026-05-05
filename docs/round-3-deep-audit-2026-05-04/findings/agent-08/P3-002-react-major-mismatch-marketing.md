---
id: A08-P3-002
title: framer-motion version split between marketing (v11) and meddoc-pro (v12)
severity: P3
domain: dependency-hygiene-supply-chain
status: open
---

## Issue

The two consumer apps pin different majors of `framer-motion`:

- `apps/marketing/package.json`: `"framer-motion": "^11.11.11"` → resolved 11.18.2
- `apps/meddoc-pro/package.json`: `"framer-motion": "^12.38.0"` → resolved 12.x

`transcribe-md` does not depend on framer-motion at all (it uses CSS animations).
`apps/meddoc-pro` is the **decommissioned CRM** per the audit scope, so the v12 there is
moot — but it still resolves into the root lockfile and `node_modules/`. The active app
(`marketing`) is a **major version behind**.

## Evidence

```bash
$ grep framer-motion apps/*/package.json
apps/marketing/package.json:    "framer-motion": "^11.11.11",
apps/meddoc-pro/package.json:    "framer-motion": "^12.38.0",

$ npm outdated --workspaces 2>&1 | grep framer
framer-motion  11.18.2  11.18.2  12.38.0  apps/marketing/node_modules/framer-motion  marketing@0.1.0
```

## Risk

- Negligible at runtime — `apps/marketing` builds and runs fine on v11.
- Mostly a *consistency / cognitive overhead* issue: a dev moving between apps has to
  remember that the same import works differently. v12 introduced a soft fork of the API
  (`motion/react` import path).
- Long term, the v11 line is in maintenance only; security fixes go to v12+.

## Recommended fix

Once `apps/meddoc-pro` is deleted (per the post-merge cleanup TODO), bump
`apps/marketing` to v12:

```diff
-    "framer-motion": "^11.11.11",
+    "framer-motion": "^12.38.0",
```

Then update import paths if the marketing components use any of the breaking-changed APIs
(release notes for v12 are short — most usages need no changes).

Until then, this can sit. Tracked here so it doesn't get lost.

## Cross-domain hooks

- Agent 12 (decommissioned-CRM cleanup): `apps/meddoc-pro` removal will simplify several of
  this domain's findings (also #P2-003 stale lockfile, also #P1-001 next-auth manifest list).
