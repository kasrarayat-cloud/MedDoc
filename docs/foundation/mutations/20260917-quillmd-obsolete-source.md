# Declared delta: obsolete QuillMD source and nightly QA cron, 2026-09-17

The latest owner instruction authorizes deleting verified old QuillMD
application/admin implementation and dedicated obsolete resources without
migration or an old-system archive. It supersedes old application retention,
rollback and migration requirements. Preserve marketing, other projects, shared
services, credentials, domains and certificates.

## Exact expected change

Remove the 19 hash-pinned files in
`docs/rebuild/obsolete-source-manifest.json` from the isolated worktree
`/opt/meddoc-pro/.worktrees/quillmd-fresh` only. These are the retired form-detect
and Gotenberg sidecar source, old database/backfill tools and old QA scripts.
The shared `/opt/meddoc-pro` files remain until the reviewed PR lands; historical
documents and Git history are unchanged. There is no recursive deletion.

Remove exactly one line from user `claude`'s crontab: the 02:00 daily job that
changes into `/opt/meddoc-pro` and invokes
`tests/automated/run-all.sh --smoke --e2e`. Its runner depends on the deleted
`apps/transcribe-md` implementation. The line and entire before/after crontab
are pinned by SHA-256 without storing potentially sensitive cron contents.

All other cron bytes remain unchanged, including marketing uptime, disk,
container monitoring, heartbeat, comments and PATH. Root's crontab is excluded.
Read-only inspection found five other-project DealHunter jobs and one 03:15
backup entry targeting missing `/opt/meddoc-pro/scripts/backup-db.sh`; that
backup entry remains because the intended backup ownership cannot be resolved
from a missing script. No cron is run as verification, and no notifications
are sent.

## Protected resources and checks

Must remain unchanged: all shared-tree target files, all containers and their
images/running state, healthy marketing HTTP 200, services, storage, credentials,
network/ingress configuration, certificates and domains. Preserve shared
mutation/deployment guards and encrypted-mount/reboot checks. Source cleanup
does not deploy the fresh app or update live Caddy.

The script defaults to read-only checks, verifies each exact file's real path,
hash and clean tracked state, and refuses source/cron drift. Execution requires
the committed declaration gate plus unchanged tracked script and manifest.
Crontab has no compare-and-swap API: the script compares immediately before
installation and verifies exact resulting bytes; avoid concurrent crontab edits
during this brief operation. Each file is rechecked before individual unlink.
No old-system archive is created. Success or partial progress is recorded in
`docs/rebuild/obsolete-source-cleanup-result.json`.

```bash
bash scripts/run-ruled-mutation.sh \
  --declaration docs/foundation/mutations/20260917-quillmd-obsolete-source.md \
  -- python3 scripts/retire-old-quillmd-source.py --execute
```

Reboot hazard remains a separate maintenance task: the preserved reboot verifier
expects retired QA and prints obsolete restore advice, but does not execute
that advice. The old cron installer can reintroduce the nightly entry if
manually run; do not run it against the fresh installation. No automatic
old-stack recreation was identified in the inspected user/root crontabs or
relevant systemd units.
