---
id: A07-P2-005
title: Build images use `node:22-alpine` (floating patch) — no digest pin
severity: P2
domain: infrastructure-opsec
date: 2026-05-04
---

## Issue

All four QuillMD app Dockerfiles use `FROM node:22-alpine` (no digest, no
patch-level pin). This is on top of the runtime image issue in
A07-P1-005 (MinIO `:latest`) — but separate, because here it's the build
toolchain that floats.

Affected Dockerfiles:
- `apps/transcribe-md/Dockerfile`
- `apps/transcribe-md/Dockerfile.worker`
- `apps/marketing/Dockerfile`
- `apps/meddoc-pro/Dockerfile`

Every CI run + every `docker compose build --pull` resolves
`node:22-alpine` to whatever that tag points at on the day. The CI
workflow `.github/workflows/test.yml` runs on `ubuntu-latest` (also a
floating runner image — but that's GitHub's problem, low blast radius).

## Evidence

```
$ grep -E '^FROM' apps/*/Dockerfile* apps/*/Dockerfile
apps/transcribe-md/Dockerfile.worker:FROM node:22-alpine AS full-deps
apps/transcribe-md/Dockerfile.worker:FROM node:22-alpine AS prod-deps
apps/transcribe-md/Dockerfile.worker:FROM node:22-alpine AS runner
apps/meddoc-pro/Dockerfile:FROM node:22-alpine AS deps
apps/meddoc-pro/Dockerfile:FROM node:22-alpine AS builder
apps/meddoc-pro/Dockerfile:FROM node:22-alpine AS runner
apps/marketing/Dockerfile:FROM node:22-alpine AS deps
apps/marketing/Dockerfile:FROM node:22-alpine AS builder
apps/marketing/Dockerfile:FROM node:22-alpine AS runner
apps/transcribe-md/Dockerfile:FROM node:22-alpine AS deps
apps/transcribe-md/Dockerfile:FROM node:22-alpine AS builder
apps/transcribe-md/Dockerfile:FROM node:22-alpine AS runner
```

`node:22-alpine` resolves to a different digest each upstream patch — a
node 22.x release including a CVE patch *or* a new vulnerability would
ship into the next QuillMD build automatically.

## Risk

- Reproducibility: a regression triage 6 months from now cannot reproduce
  the exact toolchain that built today's image.
- Supply-chain risk: a compromised `node:22-alpine` upload (image
  registry compromise, base-image typosquat — has happened) lands
  silently in CI and production.
- Patch surveillance: with no pinned version the operator does not know
  *what* moved between two builds.

## Recommended fix

Pin to the current release digest. Centralise via a single `ARG NODE_IMAGE`
in a base Dockerfile or repeat the same pin across all four:

```dockerfile
# Pin to node:22.14.0-alpine3.21 (current Apr 2026 LTS), digest verified
FROM node:22.14.0-alpine3.21@sha256:<verified-digest> AS deps
FROM node:22.14.0-alpine3.21@sha256:<verified-digest> AS builder
FROM node:22.14.0-alpine3.21@sha256:<verified-digest> AS runner
```

Or use `node:22.14.0-alpine` (semver-pinned tag, less reproducible than
digest but more reproducible than `:22-alpine`).

Add a quarterly "base-image bump" item to `docs/runbooks/IMAGE_UPGRADE.md`
that:
1. Verifies the new digest's CVE history with `trivy image`.
2. Smoke-tests against the test suite.
3. Diffs the runtime tarball against the previous (compare layer
   manifest sizes — outliers are red flags).
