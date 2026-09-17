# Declared delta — private fresh application activation, 2026-09-17

Owner authorizes a fresh local development application and deletion of verified old implementation/resources, with marketing/shared services preserved and no data migration. The scoped old application/data/image retirements have completed separately. Baseline: `docs/rebuild/activation-baseline.json`.

This action occurs after the fresh implementation PR lands and its exact merge commit passes the new CI and secret-scan workflows. The shared `/opt/meddoc-pro` stays on main and advances by fast-forward only. Required GitHub check contexts change from deleted old-app tests to the actual fresh application, marketing, private browser/accessibility and unchanged secret scan checks; no failing new check is overridden. The previous branch-protection configuration is recorded before replacing only its required-status-check collection.

Expected changes:

- Shared tracked source becomes the reviewed fresh tree, retaining marketing and shared service definitions.
- Live Caddy config reloads from its existing shared bind `/opt/meddoc-pro/Caddyfile`: app/admin return deliberate HTTP503 maintenance, pro410, marketing/www200. No fresh preview public route is added. No container recreation or bind repointing.
- The new application's own `.env`/`.runtime` private files move from its isolated implementation worktree into `/opt/meddoc-pro/rebuild`. These were created during this rebuild; none came from the old application. The environment remains0600 and runtime0700. A fresh venv is installed from the reviewed lockfile.
- Three exact new units `quillmd-fresh-{doctor,admin,worker}.service` are installed from `rebuild/deploy/`, enabled and started under user claude. Only verified old fresh-preview processes are gracefully stopped before replacement. Doctor/admin bind127.0.0.1:9130/9131. The existing fresh PostgreSQL container/volume is reused unchanged. Unit stop waits for active work; interrupted unknown provider completion remains in reconciliation and is never retried automatically.
- One exact boot-order drop-in `quillmd-postreboot-proof.service.d/fresh-private.conf` orders preserved boot verification after the three fresh services, without changing its command or other ordering.
- Verified leftover ignored artifacts beneath deleted old app/package/sidecar directories may be removed after confirming no tracked fresh/marketing content, symlink escape or current process consumer. No broad repository/VPS deletion or prune.

Must remain unchanged: all baseline container IDs/images/mounts, old preserved marketing waitlist and other projects, public DNS/certificates/nginx, shared encrypted storage services, useful credentials, unrelated crontab/systemd entries. PostgreSQL/Redis/MinIO/Caddy/marketing are not recreated. New preview remains synthetic-only and authenticated; administrator MFA remains mandatory.

Verify: unit enabled/active states, exact listener addresses, private login/health, actual synthetic document parsing/job/export after relocation, database/application checks, marketing/www/app/admin/pro HTTP expected statuses, baseline container/mount identity and preserved waitlist7 rows. Record execution evidence and unresolved external integrations in the durable checkpoint. If a predicate fails, stop the affected step and repair within this declared scope.
