---
id: A01-P1-003
severity: P1
title: ".dockerignore omits .env and .env.backup, ensuring every build embeds production secrets"
domain: Credential & secret hygiene
files:
  - .dockerignore
---

## Issue
`/opt/meddoc-pro/.dockerignore` (full file, exactly 9 lines):
```
node_modules
.next
.git
.env.local
.env.production
*.md
.claude
backups
docs
```

Two critical omissions:
1. **`.env`** — the live production secrets file. With `COPY . .` in every Dockerfile builder stage, this is layered into the image.
2. **`.env.backup`** — a duplicate of `.env` (probably produced by an earlier deploy script) that ALSO holds live secrets and is mode 0755 on the host. Any future build picks it up.

This is the upstream cause of A01-P0-001 (live secrets baked into images) and a structural defect rather than a transient operator mistake.

## Evidence

`.dockerignore` line-by-line:
```
.dockerignore:1: node_modules
.dockerignore:2: .next
.dockerignore:3: .git
.dockerignore:4: .env.local            ← partial coverage
.dockerignore:5: .env.production       ← partial coverage; production never named .env.production here
.dockerignore:6: *.md
.dockerignore:7: .claude
.dockerignore:8: backups
.dockerignore:9: docs
```

The actual production env file (per `.env.production.example:5-6`):
> 1. Copy this file to /opt/meddoc-pro/.env on the VPS.

So the canonical production filename is `.env`, not `.env.production` — and `.env` is **not** listed in `.dockerignore`.

`apps/transcribe-md/Dockerfile:39` (and identical pattern in apps/marketing/Dockerfile, apps/meddoc-pro/Dockerfile):
```
COPY . .
```

Resulting image inspection (already shown in A01-P0-001) confirms `/app/.env` and `/app/.env.backup` survive into the runtime image.

## Risk
1. **Every** image rebuild from a tree that has a populated `.env` ships those secrets in image layers. CI cache, registry mirror, image-pull operations on dev laptops — every consumer of the image gets the keys.
2. Composes with the A01-P0-001 fix: rotating the keys without fixing `.dockerignore` lets the next build re-leak whatever is rotated to.
3. `.env.production` being in the list is essentially dead code — nobody names the file `.env.production` here. The list looks "secured" without actually covering the file in use.

## Recommended fix

Replace the env-related lines of `.dockerignore` with a tighter glob:
```
.env
.env.*
!.env.example
!.env.production.example
!.env.test.example
!.env.phase-6.2.template
```

Plus also exclude:
- `tests/automated/.env.test` (which trufflehog showed survives into `db-migrate`).
- `apps/*/.env*` (catch the per-app dotfiles too).

Then rebuild every image and rotate every secret currently embedded.
