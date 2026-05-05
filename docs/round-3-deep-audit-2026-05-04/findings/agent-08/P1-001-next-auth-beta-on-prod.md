---
id: A08-P1-001
title: next-auth pinned to 5.0.0-beta on the production auth path
severity: P1
domain: dependency-hygiene-supply-chain
status: open
---

## Issue

Both transcribe-md and the auth package depend on `next-auth@^5.0.0-beta.30`. The currently
resolved version is `5.0.0-beta.31` (per `npm outdated`). next-auth v5 has been in beta for
~14 months at audit time and has not yet shipped a stable release. The "Latest" column on
the npm registry still resolves to `4.24.14` because v5 is published only on the `next` /
`beta` dist-tag.

```
next-auth   5.0.0-beta.31  5.0.0-beta.31  4.24.14  ... auth@@meddoc/auth, meddoc-pro, transcribe-md
```

This is the **sole** authentication library in front of every PHI route in transcribe-md
(see `apps/transcribe-md/src/lib/nextauth.ts`, `apps/transcribe-md/src/proxy.ts`). A semver
range of `^5.0.0-beta.30` is unstable: per npm semver rules, `^x.y.z-beta.NN` resolves
**within the same prerelease cadence only**, so pinning is implicit, but a clinician install
that runs `npm ci` against a freshly published `5.0.0-beta.32` (whenever it ships) will pick
up untested behaviour without any human review.

## Evidence

```bash
$ cd /opt/meddoc-pro && npm outdated --workspaces | grep next-auth
next-auth  5.0.0-beta.31  5.0.0-beta.31  4.24.14  node_modules/next-auth ...

$ grep -r '"next-auth"' apps/transcribe-md/package.json packages/auth/package.json
apps/transcribe-md/package.json:    "next-auth": "^5.0.0-beta.30",
packages/auth/package.json:    "next-auth": "^5.0.0-beta.30"
```

Direct usage of the beta API surface:

```bash
$ grep -r "from 'next-auth" apps/transcribe-md/src | head -5
apps/transcribe-md/src/proxy.ts:import NextAuth from 'next-auth';
apps/transcribe-md/src/lib/nextauth.ts:import NextAuth from 'next-auth';
apps/transcribe-md/src/lib/nextauth.ts:import Credentials from 'next-auth/providers/credentials';
apps/transcribe-md/src/app/admin/_components/AdminOverview.client.tsx:import { signOut } from 'next-auth/react';
apps/transcribe-md/src/app/settings/delete-account-dialog.tsx:import { signOut } from 'next-auth/react';
```

`packages/auth/package.json` declares it as a `peerDependency` AND a `devDependency`, no
fallback to v4.

## Risk

- **Production blast radius**: every `/api/*` PHI route, the entire admin UI, every signed-in
  page in transcribe-md goes through this code path. A regression in beta = an authn outage
  for the pilot.
- **Audit posture**: HIPAA technical safeguards (45 CFR 164.312(a)) ask for "reasonable and
  appropriate" auth controls. Telling an OCR auditor that the only authn layer is a 14-month-
  old beta ("we'll upgrade when it ships stable") is a credibility hit.
- **Floating beta range**: `^5.0.0-beta.30` admits any future `5.0.0-beta.NN` if `npm ci`
  isn't strict. Even with a pinned lockfile, `npm install` on a clinician laptop drifts.
- **Security advisory cadence**: pre-1.0 betas typically don't get back-ported security fixes
  to older betas — fixes ship in the next beta and the only remediation path is bumping
  forward, which is exactly the unstable thing we're trying to avoid.

## Recommended fix

Three options, in order of preference:

1. **Pin exactly** in all three manifests (`apps/transcribe-md/package.json`,
   `packages/auth/package.json`, plus the decommissioned `apps/meddoc-pro/package.json` so
   they don't drift apart in the root lockfile):

   ```diff
   -    "next-auth": "^5.0.0-beta.30",
   +    "next-auth": "5.0.0-beta.31",
   ```

   Then any future bump goes through code review.

2. **Add `overrides`** in the root `package.json` so the workspace graph resolves to a single
   pinned version regardless of caret-range drift in any individual workspace:

   ```json
   {
     "overrides": {
       "next-auth": "5.0.0-beta.31"
     }
   }
   ```

3. (Long-term) Track Auth.js's release schedule and migrate to stable `5.0.0` the day it
   ships. Add a Dependabot/Renovate "security-and-version-updates" rule for `next-auth`
   specifically (see A08-P2-001).

## Cross-domain hooks

- Agent 02 (auth/nextauth correctness): if any v5-specific API behaviour has tripped tests,
  pinning will at least make those failures reproducible.
- Agent 09 (CI/CD): add a `semver-range-check` step that fails the PR if any package.json
  introduces a new caret range against a `*-beta.*` version.
