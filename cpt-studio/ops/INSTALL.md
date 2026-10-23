# Installing CPT Studio at cpt.quillmd.com

`ops/install.py` is a ruled-mutation installer. It refuses to run outside
`scripts/run-ruled-mutation.sh`, so every phase is bound to a committed
declaration (`docs/foundation/mutations/20261023-cpt-studio-install.md`) whose
commit time precedes the act. Run one phase at a time, read its receipt, then
run the next. Nothing here was executed by the session that wrote it.

## What gets installed

| object | value |
|---|---|
| image | `cpt-studio:<sha12>`, built from `git archive <revision> cpt-studio/`, label `org.opencontainers.image.revision=<revision>` |
| database | container `cpt-studio-db` (postgres 17.11, pinned by digest), uid 70, all capabilities dropped, `127.0.0.1:55451`, volume `cpt-studio-pg` |
| web | container `cpt-studio-web`, gunicorn, read-only root, uid 10150, `127.0.0.1:9150` → 8000 |
| worker | container `cpt-studio-worker`, read-only root, the only holder of the Corti credentials (live mode only) |
| network | `cpt-studio-net` (bridge). Web and worker reach the database as `cpt-studio-db:5432` |
| files | volume `cpt-studio-files` at `/var/lib/cpt-studio` (originals, reference copies) |
| secrets | `/etc/cpt-studio/` root 0700: `app.env`, `db.env` (root 0600), `corti-credentials.env` (10150:10150 0400), `initial-credentials.json` (root 0600) |
| agent login | `/home/claude/.cpt-studio/agent-credentials.json` (0600, agent account only) |
| ingress | NEW `/etc/nginx/sites-available/quillmd-cpt` + `sites-enabled` symlink. The `quillmd` vhost is never edited |
| certificate | separate lineage `cpt.quillmd.com`, webroot `/var/www/certbot`, existing ACME account |

Every Docker object carries `org.quillmd.cpt-studio=1` and a role label; the
installer refuses to touch a same-named object without them.

## Invocation

```bash
DECL=docs/foundation/mutations/20261023-cpt-studio-install.md
REV=<40-char revision named in the declaration>
RECEIPTS=/home/claude/cpt-studio-install-20261023   # 0700, outside the repository
bash scripts/run-ruled-mutation.sh --declaration "$DECL" -- \
  python3 -B cpt-studio/ops/install.py --phase preflight --revision "$REV" --receipts "$RECEIPTS"
```

The tree must be clean, and HEAD must be the revision or a descendant that
changed nothing under `cpt-studio/` or the ruled-mutation door (so a docs-only
commit carrying the declaration is accepted). The declaration must name the
revision and carry no unfilled revision placeholder.

Each phase prints one JSON line `{"phase", "ok", "summary", "receipt"}` and
writes `<phase>-<UTC>.json` (0600) plus any command logs into the receipts
directory. Exit 0 = done; 1 = refused or failed (the receipt says which and why).

## Phases, in order

| # | phase | extra arguments | changes |
|---|---|---|---|
| 1 | `preflight` | — | nothing (one ACME probe file written and removed) |
| 2 | `secrets` | — | creates `/etc/cpt-studio/` and its three files, once |
| 3 | `image` | — | builds `cpt-studio:<sha12>` |
| 4 | `db` | — | network, two volumes, database container |
| 5 | `app` | `--provider-mode live --authorization-ref docs/foundation/rulings/2026-10-23-cpt-studio-gi.md` (or `--provider-mode disabled`) | migrations; web and worker containers |
| 6 | `reference` | `--pfs-zip <abs> --pfs-retrieved-at <ISO> --mue-zip <abs> --mue-retrieved-at <ISO>` | reference copies in the files volume; two `ReferenceSource` imports |
| 7 | `provision` | `--owner-username <name>` (optional `--agent-username`, display names, `--reset-passwords`) | GI workspace, owner and agent accounts; credentials files |
| 8 | `http-vhost` | — | `quillmd-cpt` (HTTP stage) + symlink; nginx reload |
| 9 | `cert` | — | lineage `cpt.quillmd.com` |
| 10 | `https-vhost` | — | `quillmd-cpt` replaced by the HTTPS stage; nginx reload |
| 11 | `verify` | — | nothing |

`rollback-app` removes the web and worker containers (keeps the database,
volumes, images and secrets). `rollback-vhost` removes `quillmd-cpt` and its
symlink (only if their bytes are this installer's) and reloads nginx; the
certificate lineage is kept.

### What each phase checks before and after

- **preflight** records the baseline the later phases compare against: sha256
  of every readable `sites-available` file, the `sites-enabled` links,
  `nginx.conf`, `sudo -n nginx -t` (with its warnings), a HEAD probe of every
  `server_name`/listen pair in the enabled vhosts against local nginx (status
  and certificate fingerprint per SNI, plus an unmatched host), the current
  answers for `cpt.quillmd.com`, `https://app.quillmd.com/health/`,
  `scripts/check-cotenants.sh`, containers, volumes, networks, ports 9150 and
  55451, DNS (A `147.189.172.8` only, no AAAA), the pinned helper and postgres
  images, the Corti credentials source, Let's Encrypt state by path (live
  names, renewal-config hashes, account ids — key material is never opened)
  and that the ACME webroot is writable. Any problem fails the phase.
- **secrets** generates the Django key and database password inside the root
  helper; the values never leave it. The Corti file is copied byte-for-byte and
  only its four key NAMES are checked. A partial or altered set is refused, not
  repaired.
- **image** builds, then requires the revision label, user 10150, the baked
  release, English OCR data, a working `pdftoppm`, `manage check`, and that the
  WSGI application loads as the image's own user on a read-only root (this is
  what catches unreadable static files, which `manage check` does not).
- **db** is idempotent; an existing container must be ours, on the pinned
  image, loopback-only, `unless-stopped`.
- **app** (live mode) first loads the Corti credentials with the
  application's own loader, in the worker's mount layout, with no network:
  a file the worker could not use stops the phase before anything changes.
  It then migrates with a one-shot container, parks the current web/worker
  (`*-previous`), starts the new pair and waits for
  `/health/` = `{status ok, service cpt-studio, data_mode synthetic-only,
  database ok, release <revision>}` and a worker that stays up. On any failure
  the new pair is removed and the parked pair restored. Migrations already
  applied are not reversed.
- **reference** requires each zip to match its pinned size and sha256 and
  passes the pinned release, URL and window with the retrieval time you give.
- **provision** writes both credentials files only after the accounts exist
  with the generated passwords; an account that already existed (password
  unchanged) aborts and discards them unless `--reset-passwords` was given.
  Passwords travel as RAM-only files under `/dev/shm`, never argv or output.
- **http-vhost / https-vhost / rollback-vhost** validate with
  `sudo -n /usr/sbin/nginx -t`, refuse any new nginx warning, reload with
  `sudo -n /usr/bin/systemctl reload nginx`, then probe with bounded retries
  (reloads are asynchronous). Any failed check restores the exact previous
  file state, validates and reloads again. Co-tenant routing and app health
  must equal the preflight baseline.
- **cert** requires exactly one existing ACME account and passes it with
  `--account`; certbot gets no `--agree-tos` or e-mail, so it cannot register
  one. Other lineages' renewal configs must be byte-identical afterwards.
- **verify** compares everything with the preflight receipt and checks the
  deployed containers' hardening and the HTTPS headers, including that a
  request whose SNI is not `cpt.quillmd.com` is closed (444).

## Reinstalling a new revision

Commit a declaration naming the new revision, then run `preflight`, `image`,
`app`, `verify`. `secrets`, `db`, `reference` and `provision` are idempotent or
refuse rather than repeat. If `deploy/nginx/` changed between the revisions,
`verify` reports the vhost as different: republish with `rollback-vhost`,
`http-vhost`, `cert` (a no-op for a lineage not yet due for renewal; it records
the receipt `https-vhost` requires) and `https-vhost` under the new declaration.

## Recovery notes

- `*-previous` containers left by an interrupted `app`: inspect, then remove or
  rename back by hand; `app` refuses while one exists.
- Staged `.initial-credentials.json.new` / `.agent-credentials.json.new` from an
  interrupted `provision`: delete them (no account uses their passwords unless
  the receipt says the accounts were created) and rerun.
- Rotating the two passwords: `--phase provision --owner-username … --reset-passwords`.

## Local build and tests (no host change)

```bash
cd cpt-studio
python3 -B -m unittest discover -s ops -p 'test_*.py' -v      # installer tests, no Docker
ctx=$(mktemp -d) && git archive HEAD cpt-studio | tar -x -C "$ctx" \
  && cp "$ctx/cpt-studio/deploy/.dockerignore" "$ctx/cpt-studio/.dockerignore" \
  && docker build -f "$ctx/cpt-studio/deploy/Dockerfile" -t cpt-studio:dev-build "$ctx/cpt-studio"
```

The Django suite inside the image needs a disposable PostgreSQL:
`docker run --rm --network host --read-only --tmpfs /tmp:rw,exec,nosuid,nodev,size=1g --env-file <0600 file with CPT_STUDIO_SECRET_KEY and CPT_STUDIO_DB_PASSWORD> -e CPT_STUDIO_DB_HOST=127.0.0.1 -e CPT_STUDIO_DB_PORT=<port> -e CPT_STUDIO_TEST_DB_SUFFIX=<unique> -e CPT_STUDIO_STATE_DIR=/tmp/state cpt-studio:dev-build manage test tests --noinput`.
`exec` on `/tmp` is for the tests only: the OCR plumbing tests run stand-in
`tesseract`/`pdftoppm` scripts from a temporary directory. The installed
containers keep `/tmp` `noexec`; real OCR runs the tools from `/usr/bin` and was
verified inside the image under that setting.

## Known limits

- Data at rest is on the unencrypted root disk (docker volumes, nginx request
  buffering for uploads over 16 KiB). Acceptable only because the service is
  synthetic-only; real data would need an encrypted volume first.
- The database has no scheduled backup in this release.
- The worker has no Docker health check; `app` and `verify` check that it is
  running and not restarting.
- The application uid is 10150, not 10001: 10001 already runs a co-tenant's
  containers here, and RLIMIT_NPROC (set by the extraction sandbox from its
  container's own task count) is accounted per host uid. `preflight` and
  `verify` refuse if any task outside CPT Studio runs as 10150.
