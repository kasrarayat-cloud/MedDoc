---
id: A08-P1-002
title: All Docker base images use floating tags — no SHA256 digest pinning
severity: P1
domain: dependency-hygiene-supply-chain
status: open
---

## Issue

Every Dockerfile in the build (and every infra image referenced from `docker-compose.yml`)
uses a **floating tag**. None pin to an immutable `@sha256:…` digest, and none pin a patch
version. A `docker compose pull` on a freshly provisioned VPS — or an `npm ci`-style rebuild
during the pilot — can silently swap the base image out from under us.

## Evidence

App Dockerfiles — base layer only:

```bash
$ grep -E "^FROM" /opt/meddoc-pro/apps/transcribe-md/Dockerfile \
                 /opt/meddoc-pro/apps/transcribe-md/Dockerfile.worker \
                 /opt/meddoc-pro/apps/marketing/Dockerfile \
                 /opt/meddoc-pro/apps/meddoc-pro/Dockerfile
apps/transcribe-md/Dockerfile:FROM node:22-alpine AS deps
apps/transcribe-md/Dockerfile:FROM node:22-alpine AS builder
apps/transcribe-md/Dockerfile:FROM node:22-alpine AS runner
apps/transcribe-md/Dockerfile.worker:FROM node:22-alpine AS full-deps
apps/transcribe-md/Dockerfile.worker:FROM node:22-alpine AS prod-deps
apps/transcribe-md/Dockerfile.worker:FROM full-deps AS prisma-generate
apps/transcribe-md/Dockerfile.worker:FROM node:22-alpine AS runner
apps/marketing/Dockerfile:FROM node:22-alpine AS deps
apps/marketing/Dockerfile:FROM node:22-alpine AS builder
apps/marketing/Dockerfile:FROM node:22-alpine AS runner
apps/meddoc-pro/Dockerfile:FROM node:22-alpine AS deps
apps/meddoc-pro/Dockerfile:FROM node:22-alpine AS builder
apps/meddoc-pro/Dockerfile:FROM node:22-alpine AS runner
```

Compose-level images (infra):

```bash
$ grep -E "^\s+image:" /opt/meddoc-pro/docker-compose.yml
    image: pgvector/pgvector:pg16
    image: redis:7-alpine
    image: minio/minio:latest        # ← worst offender
    image: caddy:2-alpine
    image: prodrigestivill/postgres-backup-local:16
```

`minio/minio:latest` is the most egregious — `latest` follows MinIO's main release train,
which historically has had silent ABI/CLI changes (e.g., the `mc` admin command renames over
the past 18 months).

`node:22-alpine` resolves to whatever Node maintainers tag last. As of audit, that's `node:
22.20.x`, but a fresh build tomorrow could land on `22.21.x` with a different glibc-substitute
layer. For a HIPAA-eligible workload that's being shipped to clinicians, the inability to
reproduce yesterday's image bit-for-bit is a real audit problem.

## Risk

- **Reproducibility**: a rollback to a known-good commit may produce a *different* image
  than the one that originally passed QA, because the base layer drifted.
- **Supply chain**: a hijacked `node` or `minio` Docker Hub account could silently push a
  malicious tag with the same human-readable name; SHA256 pinning blocks that vector.
- **CVE response window**: when a Node 22 CVE drops, a `docker build --pull` will pick up
  the patched base — good — but if the base also bumps a transitive shell utility in a
  breaking way, our app builds without warning. We want the bump to be a deliberate PR.
- **HIPAA**: 45 CFR 164.312(c)(1) ("Mechanism to authenticate electronic protected health
  information") is much easier to argue when every layer of the runtime is pinned and
  attestation-friendly.

## Recommended fix

1. **App images** — pin to `node:22.X.Y-alpine3.YY@sha256:…`:

   ```dockerfile
   # Resolve once: docker pull node:22-alpine && docker inspect --format='{{index .RepoDigests 0}}' node:22-alpine
   FROM node:22.20.0-alpine3.21@sha256:<digest> AS deps
   ```

   Apply identically across all four Dockerfiles. Update via Dependabot (P2-001).

2. **Infra images** — pin to a specific patch + digest:

   ```yaml
   # docker-compose.yml
   postgres:
     image: pgvector/pgvector:pg16.4-bookworm@sha256:<digest>
   redis:
     image: redis:7.4.1-alpine@sha256:<digest>
   minio:
     image: minio/minio:RELEASE.2025-04-22T22-12-26Z@sha256:<digest>
   caddy:
     image: caddy:2.8.4-alpine@sha256:<digest>
   ```

3. **CI gate**: add a `hadolint` or simple shell check in `.github/workflows/test.yml` that
   `grep -L '@sha256:'` over every Dockerfile and fails the run.

4. **One-time rebase + Dependabot**: after the initial pin, configure Dependabot's
   `docker` ecosystem so PRs land weekly with the new digest, reviewed by humans.

## Cross-domain hooks

- Agent 09 (CI): add the hadolint step.
- Agent 03 (HIPAA / infra): the auditor will likely ask "how do you ensure the runtime image
  hasn't been tampered with?" — SHA256 digest pinning is the textbook answer.
- A08-P2-001 (Dependabot): the same automation handles both npm and docker ecosystems.
