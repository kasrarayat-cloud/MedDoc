---
id: A01-P1-002
severity: P1
title: "tests/automated/.env.test stores live RESEND_API_KEY despite being managed by CI-secret seeding"
domain: Credential & secret hygiene
files:
  - tests/automated/.env.test:25,30
  - .github/workflows/nightly-tests.yml:44-62
---

## Issue
The CI workflow `nightly-tests.yml` correctly seeds `tests/automated/.env.test` from `${{ secrets.X }}` at runtime, never embedding values:

```yaml
- name: Seed .env.test from secrets
  env:
    TEST_APP_EMAIL:    ${{ secrets.TEST_APP_EMAIL }}
    ...
```

But the **on-host** copy of that file at `/opt/meddoc-pro/tests/automated/.env.test` carries a live Resend API key (`<REDACTED-LIVE-RESEND>`) hardcoded at lines 25 and 30 — once as `RESEND_API_KEY` and once as `TEST_ALERT_RESEND_API_KEY`.

```
$ cat /opt/meddoc-pro/tests/automated/.env.test | grep RESEND
RESEND_API_KEY=<REDACTED-LIVE-RESEND>
TEST_ALERT_RESEND_API_KEY=<REDACTED-LIVE-RESEND>
```

This is the **same** live RESEND key embedded in the production `.env`, the production `.env.backup`, and the `meddoc-pro-meddoc-pro:latest` image. So even though the file is gitignored (and its 0600 mode is correct), the *host* now has the production RESEND key duplicated into a tests directory that:

- Was meant to be CI-only secret-seeded.
- Is now also baked into `meddoc-pro-db-migrate:latest` (see A01-P0-001 — `find / -name '.env*'` listed `/app/tests/automated/.env.test`).
- Triggers a layer-leak whenever the db-migrate image is exported.

## Evidence
`/opt/meddoc-pro/tests/automated/.env.test:25,30`:
```
RESEND_API_KEY=<REDACTED-LIVE-RESEND>
TEST_ALERT_RESEND_API_KEY=<REDACTED-LIVE-RESEND>
```

`/opt/meddoc-pro/.env:32`:
```
RESEND_API_KEY=<REDACTED-LIVE-RESEND>
```

`/opt/meddoc-pro/.env.production.example:160`:
```
RESEND_API_KEY=
```
(blank in the template, as intended.)

`docker run --rm -u 0 --entrypoint sh meddoc-pro-db-migrate:latest -c 'find / -name ".env*" 2>/dev/null'`:
```
/app/tests/automated/.env.test          ← RESEND key present
/app/.env                               ← RESEND key present
/app/.env.backup                        ← RESEND key NOT present (older snapshot)
```

## Risk
1. The Resend key gives full domain-sender control over `quillmd.com` (DKIM+SPF+DMARC verified per `.env:33-36` comment). An attacker reads it, spoofs `noreply@quillmd.com`, and sends phishing to the user list — high reputational impact even pre-pilot.
2. Test environments and production sharing an API key violates the standard practice of "test → its own credentials". Rotating one rotates both, generating cross-environment downtime risk.
3. The on-host file duplication compounds the on-image duplication from A01-P0-001.

## Recommended fix
1. Generate a **separate** Resend API key for tests, scoped (if Resend supports it) to a non-customer-facing domain or sender. Use that in `tests/automated/.env.test`.
2. Delete the production `RESEND_API_KEY=` from `tests/automated/.env.test` on host.
3. Remove `tests/` from the Docker build context for `db-migrate` (or add it to `.dockerignore`).
4. Add a CI assertion: `git diff --check` plus a grep that fails the build if `tests/automated/.env.test` is committed with non-empty values.
