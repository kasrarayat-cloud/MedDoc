# Security-fix log

Operational fixes that don't live in application code. Server-side
permission changes, infrastructure tweaks, and one-off incident
responses land here so the next operator can trace what was done.

---

## 2026-04-25 — H1: `.env` world-readable (chmod 640)

**Source of finding:** `audit-final-report.md` (audit/ultra-final branch).

**Before:**
```
-rwxr-xr-x 1 claude claude 3450 Apr 21 06:39 /opt/meddoc-pro/.env
```

The file held 7 secrets (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
`DEEPGRAM_API_KEY`, `RESEND_API_KEY`, `AUTH_SECRET`, `DB_PASSWORD`,
`MINIO_ROOT_PASSWORD`) and was world-readable. Any non-privileged
account on the VPS (`ubuntu`, `tester`, `nobody`, plus any future
contractor) could read all of them.

**Action taken:**
```
chmod 640 /opt/meddoc-pro/.env
```

No `chown` was needed — file is owned by `claude`, which is the
docker-compose invoking user on this host. Group is `claude` (empty
membership other than the user itself), so group-read via the `640`
mode is functionally owner-only.

**After:**
```
-rw-r----- 1 claude claude 3450 Apr 21 06:39 /opt/meddoc-pro/.env
(mode 640, owner claude:claude)
```

**Verification performed on 2026-04-25 ~02:10 UTC:**

1. Container env vars still set after permission change — confirmed
   `AUTH_SECRET`, `DATABASE_URL`, `ANTHROPIC_API_KEY`,
   `DEEPGRAM_API_KEY`, `OPENAI_API_KEY` all present inside
   `transcribe-md-1`, `meddoc-pro-1`, and
   `transcribe-md-worker-1` via `docker exec ... printenv` probe.
2. All 9 containers still running / healthy via `docker compose ps`
   (caddy was already unhealthy pre-change for an unrelated
   healthcheck reason — not affected).
3. Smoke-test suite: **13/13 pass**
   (`tests/automated/reports/2026-04-25-02-09.json`).
4. Group-membership proof that no other user can read:
   - `/etc/group` lists only `claude` in the `claude` group.
   - `ubuntu`, `tester`, `nobody` are all NOT members.
   - `stat -c '%a %U %G' /opt/meddoc-pro/.env` → `640 claude claude`.
   - Any future user that needs docker-compose access should be
     added to the `docker` group only; they still won't be able to
     read `.env` without being added to the `claude` group or
     having `sudo`.

**Next steps (not done here — tomorrow's batch):**

- H2: port `logAudit()` from meddoc-pro to transcribe-md and
  wire call sites on every mutation.
- H3: disk-encryption migration (LUKS volume OR Postgres + MinIO
  server-side encryption).
- H4: add `user:` directive in `docker-compose.yml` for
  postgres / redis / minio; document the caddy=root decision.

If the pilot launches before H3 ships, the BAA rider needs to
name it and commit to a closure timeline.

**Rollback (if ever needed):**
```
chmod 644 /opt/meddoc-pro/.env
```
would make the file world-readable again. Do not run this.
