# Agent 01 — Credential & Secret Hygiene · Summary

## Severity counts
**P0: 3 · P1: 3 · P2: 3 · P3: 1 · Total: 10**

## Top 3 findings
1. **P0-001** Live production secrets baked into shipped Docker images. `meddoc-pro-meddoc-pro:latest` carries `/app/apps/meddoc-pro/.env`; `meddoc-pro-db-migrate:latest` carries `/app/.env`, `/app/.env.backup`, `/app/.env.local`, `/app/tests/automated/.env.test` — all with verified-live ANTHROPIC + OPENAI + DEEPGRAM + RESEND + AUTH_SECRET + DB_PASSWORD + MINIO + Scribe service token. Cause: `COPY . .` plus `.dockerignore` that whitelists `.env.local` and `.env.production` but not `.env`.
2. **P0-002** OpenAI key documented as "leaked, must rotate" in `LAUNCH_CHECKLIST.md` §6 (`sk-proj-<REDACTED>…`) is still live in 5 on-disk files + 2 images as of 2026-05-04. Trufflehog `Verified=true` for ANTHROPIC + DEEPGRAM keys at `.env`, `.env.backup`, `.env.local`, `apps/meddoc-pro/.env`. Rotation never completed; LAUNCH_CHECKLIST §6 boxes still un-checked.
3. **P0-003** `apps/meddoc-pro/.env` and `apps/meddoc-pro/.env.local` are mode **0777** (world-writable) holding live Anthropic key. `.env.backup` and `.env.local` (root) are 0755 (world-readable) holding the full keyring. `.env.example` itself documents `chmod 600` as expected.

## Coverage
- Files read: 22 source/config + 7 .env-family + 5 Dockerfiles + 3 GitHub workflows + Caddyfile + docker-compose.yml + Makefile + .gitignore + .dockerignore + 5 runbooks/checklists + auth package source.
- Git history: 654 commits across 41 branches + 19 tags scanned with `git log -p --all -S` for `ghp_`, `github_pat_`, `sk-`, `sk-ant-`, `sk-proj-`. **Zero live secrets ever committed.**
- Trufflehog: full git scan (6 placeholder hits) + filesystem scan (49 hits, 4 verified-live).
- Docker: 5 images via `docker history` + `find / -name '.env*'` + `docker inspect`. 9 running containers' env enumerated.
- `/proc/*/cmdline` clean — no argv-leaked secrets.
- CI: all 3 workflows audited; only `ci-dummy-*` placeholders + `${{ secrets.X }}` references found.

## Positive findings
1. **No live secret has ever been committed to git** across 654 commits / 41 branches / 19 tags.
2. **CI workflows handle secrets correctly** — only `ci-dummy-*` literals and `${{ secrets.X }}` refs.
3. **Compose substitution is hygienic** — every var uses `${VAR}` with obvious-placeholder defaults.
4. **`.gitignore` covers `.env*`** correctly with explicit `!.env.example` whitelist.
5. **`packages/auth/src/index.ts:107-114` hard-fails in production** when AUTH_SECRET is unset (T-M16.3 fix is good).
6. **Process argv is clean** — secrets travel via env_file mounts, not argv.
7. **Team self-aware**: `LAUNCH_CHECKLIST.md` already lists OpenAI rotation + scanner install as launch-gate items.

## Cross-domain hooks
- **Agent 07 (infra)**: P0-001 + P1-003 (`.dockerignore` + `COPY . .`) overlap with image supply-chain.
- **Agent 05 (HIPAA)**: P0-002 + P0-003 are §164.308(a)(3) workforce-access violations.
- **Apps/meddoc-pro decommission**: P1-001 (decommissioned app still runs with full keyring).
- **Agent 08 (deps/CI)**: P2-003 (no gitleaks/trufflehog in pre-commit or CI).
- **Agent 11 (logging)**: P2-002 (smoke-harness + seed scripts log credentials to stdout).
- **Agent 05 (BAA)**: P0-002 — un-rotated leaked key voids any BAA position with OpenAI.
