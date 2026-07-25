---
id: A01-P0-001
severity: P0
title: Live production secrets baked into shipped Docker images (anyone with image access steals everything)
domain: Credential & secret hygiene
files:
  - apps/transcribe-md/Dockerfile:39
  - apps/meddoc-pro/Dockerfile
  - apps/marketing/Dockerfile
  - .dockerignore:1-7
  - .env:20,27,29,32,40,44
---

## Issue
Every shipped image built from this tree carries the **complete production `.env`** — and in the case of `meddoc-pro-db-migrate:latest`, also `.env.backup` (which still contains the supposedly-rotated OpenAI key prefix). Confirmed by inspecting the on-host images:

- `meddoc-pro-meddoc-pro:latest` → `/app/apps/meddoc-pro/.env` (live ANTHROPIC_API_KEY, OPENAI_API_KEY, DEEPGRAM_API_KEY, RESEND_API_KEY, AUTH_SECRET, DB_PASSWORD, MINIO_ROOT_PASSWORD, SCRIBE_SERVICE_TOKEN).
- `meddoc-pro-db-migrate:latest` → `/app/.env`, `/app/.env.backup`, `/app/.env.local`, `/app/.env.production.example`, `/app/apps/meddoc-pro/.env`, `/app/tests/automated/.env.test`. **All contain live keys.**

Root cause: the per-app Dockerfiles call `COPY . .` (e.g. `apps/transcribe-md/Dockerfile:39`) for the build stage, and `.dockerignore` excludes `.env.local` and `.env.production` but **not `.env`** itself. Next.js standalone tracing then keeps the `apps/meddoc-pro/.env` file in the runtime layer of `meddoc-pro-meddoc-pro`. The `db-migrate` service targets the `builder` stage directly (where the full source tree, including all dotfiles not gitignored, is preserved), so every secret env file present at build time is layered into the image.

## Redaction note (2026-07-25)

The `DB_PASSWORD` value originally quoted verbatim in the Evidence block below
was still the LIVE production database password as of 2026-07-25 — confirmed by
byte-comparison against `/opt/meddoc-pro/.env` (identical sha256). Every other
credential in this document was already truncated or `<REDACTED>`; this one was
not.

Remediation performed 2026-07-25:
- `ALTER ROLE meddoc WITH PASSWORD <new 32-char value>` on the production
  Postgres, `.env` updated, and the four consumers recreated
  (postgres-backup, transcribe-md-worker, transcribe-md, meddoc-pro).
- Verified over the network path where authentication is actually enforced
  (`pg_hba`: `host all all all scram-sha-256`): the new password authenticates,
  the old one returns `FATAL: password authentication failed`.
  NOTE: a `docker exec psql` test is NOT a valid check here — `pg_hba` grants
  `trust` for local/127.0.0.1 connections inside the container, so it succeeds
  with any password.
- The value remains in git history. That is acceptable only because it is now
  dead; it is no longer a credential.

## Evidence

`apps/transcribe-md/Dockerfile:39`:
```
COPY . .
```

`.dockerignore` (full file, 7 lines):
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
**`.env` is not listed.** `.env.backup` is also not listed.

Image inspection (live host, branch `chore/round-3-deep-audit-2026-05-04`):
```
$ docker run --rm -u 0 --entrypoint sh meddoc-pro-meddoc-pro:latest \
    -c 'cat /app/apps/meddoc-pro/.env | grep -E "API_KEY|PASSWORD|SECRET"'
AUTH_SECRET=1S9z4BGjYjbInNkez...EQc=
OPENAI_API_KEY=sk-proj-<REDACTED>...0A
ANTHROPIC_API_KEY=sk-ant-api03-<REDACTED>...AAA
DEEPGRAM_API_KEY=a905214...e6915a1
RESEND_API_KEY=<REDACTED-LIVE-RESEND>
DB_PASSWORD=<REDACTED-ROTATED-20260725>
MINIO_ROOT_PASSWORD=WHu8b2IFVoc...9B5a
SCRIBE_SERVICE_TOKEN=0edd0e511...debfed

$ docker run --rm -u 0 --entrypoint sh meddoc-pro-db-migrate:latest \
    -c 'find / -name ".env*" 2>/dev/null | grep -v node_modules'
/app/apps/meddoc-pro/.next/standalone/apps/meddoc-pro/.env
/app/apps/meddoc-pro/.env.local
/app/apps/meddoc-pro/.env
/app/.env.example
/app/tests/automated/.env.test.example
/app/tests/automated/.env.test
/app/.env.backup            <-- still has the LEAKED OpenAI key
/app/.env.production.example
/app/.env
```

Verified-live secrets present in `meddoc-pro-db-migrate:latest`'s `/app/.env`:
- `OPENAI_API_KEY=sk-proj-<REDACTED>...` — matches the prefix the LAUNCH_CHECKLIST.md §6 documents as "leaked during development; must rotate before production use."
- `ANTHROPIC_API_KEY=sk-ant-api03-<REDACTED>...` (trufflehog: `Verified=true` → live and accepted by Anthropic).
- `DEEPGRAM_API_KEY=<REDACTED-DEEPGRAM>...` (trufflehog: `Verified=true` → live).

## Risk
1. Any registry push, image export (`docker save`), or shared cache tarball ships the entire production credential set to whoever can pull the layer. The `db-migrate` image is 2.67 GB but it does not need to remain proprietary — pushing to a public/dev-shared registry would publish the production keys.
2. `meddoc-pro-meddoc-pro:latest` is the running production image. Any operator with `docker run` access (including the `claude` UID, group `docker`) can `cat` the embedded `.env` regardless of whether the runtime drops permissions.
3. Compounds with finding A01-P0-002: the **`.env.backup`** baked into `db-migrate` carries the version of the OpenAI key that was supposedly leaked and supposedly rotated. If the new key has the same prefix (it does), this is the un-rotated copy.
4. Image-layer leakage of HIPAA-relevant secrets (DB_PASSWORD opens patient PHI) is itself a §164.308(a)(1) Security Management Process violation if the image is stored anywhere outside the encrypted host volume.

## Recommended fix
**Do not implement** — this is an audit-only PR. Recommendations for the fix-PR:

1. Add `.env` and `.env.backup` to `.dockerignore` (the surgical fix).
2. Audit the existing image layers: tag `meddoc-pro-meddoc-pro:latest` and `meddoc-pro-db-migrate:latest` as compromised; rebuild from a tree where the `.env` family is excluded; re-tag and recreate containers.
3. After rebuild, **rotate every secret listed in §Evidence** because the prior images did exist on disk with live keys and may have been distributed (CI cache, manual `docker save`, etc.).
4. Add a CI check that runs `docker run --rm <image> sh -c 'find / -name ".env*"'` against every PR build and fails on any hit outside `*.example` / `*.template`.
5. Migrate `db-migrate` away from re-using the `builder` stage with full source — instead build a slim migrator that only carries Prisma + the schema.
