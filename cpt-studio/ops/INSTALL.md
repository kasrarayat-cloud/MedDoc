# Installing CPT Studio at cpt.quillmd.com and admin.quillmd.com

`ops/install.py` is a ruled-mutation installer. It refuses to run outside
`scripts/run-ruled-mutation.sh`, so every phase is bound to a committed
declaration (`docs/foundation/mutations/20261023-cpt-studio-install.md`) whose
commit time precedes the act. The installer re-checks the binding itself: the
declaration must be tracked, unmodified, last touched by the commit the door
names, and byte-identical to that commit's copy. Run one phase at a time, read its receipt, then
run the next. Nothing here was executed by the session that wrote it.

## What gets installed

| object | value |
|---|---|
| image | `cpt-studio:<sha12>`, built from `git archive <revision> cpt-studio/`, label `org.opencontainers.image.revision=<revision>` |
| database | container `cpt-studio-db` (postgres 17.11, pinned by digest), uid 70, all capabilities dropped, `127.0.0.1:55451`, volume `cpt-studio-pg`; release 1 (A3, A5): 512m of memory and no swap (memory and memory + swap equal, its own cgroup's `memory.swap.max` 0), core dumps off, and a log that never holds statement text (`log_min_error_statement` panic, `log_error_verbosity` terse); release 2's search needs PostgreSQL 17 or newer (**Known limits**) |
| web | container `cpt-studio-web`, gunicorn: four sync processes forked from one master that has loaded and warmed the application, in 1 GiB of memory without swap (memory and memory + swap equal), each keeping its own database connection (release 2, R2-5 to R2-7; **Known limits**); read-only root, uid 10150, `127.0.0.1:9150` or `127.0.0.1:9151` → 8000: a fresh host starts on 9150, and each install after it starts the incoming web `cpt-studio-web-next` on the other port and switches to it (blue/green, **app**), so the port alternates |
| worker | container `cpt-studio-worker`, read-only root, stop timeout 3,600 s (the Fable coding build: one coding stage prepares the document - a Word file converted in a bounded child of at most 60 s - then streams the reader's send and the checker's, each up to 96,000 output tokens at effort max, about 1,000 s each at the slowest rate measured, so a round can pass 2,000 s; the bound is `studio.jobs.CODE_STALE_SECONDS`, the age at which the stale sweep takes a running coding job for a dead worker's; a deploy may wait up to 60 minutes for it; round r3's question stage had 1,800 s before it), the only holder of a credentials file: the Fable coder's Anthropic file, read-only, when `--coding-mode live` (an earlier revision's pair a `switch-back` starts holds what its own `app` gave it: Corti's, a live participant's, the interpreter's) |
| network | `cpt-studio-net` (bridge). Web and worker reach the database as `cpt-studio-db:5432` |
| files | volume `cpt-studio-files` at `/var/lib/cpt-studio` (originals, reference copies) |
| secrets | `/etc/cpt-studio/` root 0700: `app.env`, `db.env` (root 0600), `initial-credentials.json` (root 0600), `operator-enrolment.json` (root 0600, the platform operator's single-use setup code, valid 30 minutes: **operators** and **manage**; release 1, A6). No operator password is written to a file: an `operator-credentials.json` an earlier install wrote is left untouched, and deleting it is the owner's decision (D12). The Fable coding build (DECISIONS D351-D353) neither reads Corti's source nor writes Corti's copy: a `corti-credentials.env` an earlier install wrote is left as it is, and only a `switch-back` to an earlier pair given `--provider-mode live` mounts it |
| coding credential | the Fable coder's (Claude Fable 5.2; CPT Studio's existing Anthropic credential): `/etc/cpt-studio/anthropic-credentials.env`, 10150:10150 0400, copied from `/etc/cpt-studio-provider-sources/anthropic.env` (root 0600 in a root 0700 directory, `ANTHROPIC_API_KEY` and an optional `ANTHROPIC_WORKSPACE_ID`) when the owner placed it; never part of the two-file set above. The only credentials file an `app` requires (`--coding-mode live`) or mounts: read-only into the WORKER alone at `/run/cpt-studio/anthropic-credentials.env` (the web is given the mode and the path, never the file); no access check. Astra's `openai.env` is no longer read or copied; an `openai-credentials.env` an earlier install wrote is left as it is, for a `switch-back` to an earlier pair that runs Astra. An earlier `/etc/cpt-studio/gemini.env` is no longer copied or mounted: it is left untouched and reported (`preflight`, `secrets`), deleting it being the owner's decision |
| passages | the CMS passage files the revision commits under `studio/reference/data/`, imported into `PassageSource`/`ReferencePassage` |
| agent login | `/home/claude/.cpt-studio/agent-credentials.json` (0600, agent account only) - only when `provision` is given `--agent-username` (release 1, A6: a review agent is opt-in) |
| operator accounts | `platform-operator` (human) alone (release 1, A6): no workspace membership, an operator grant (`manage grant_operator` with `--by`, `--review-by` and the declaration as `--authorization-ref`), an unusable password until its holder sets one with the setup code on admin.quillmd.com. No automated account is an operator: `ops-agent` (an earlier install's) is revoked by a ruled act, and its login file is left untouched - deleting it is the owner's decision (D11) |
| converter | container `cpt-studio-converter` (release 1, A7, E3): this revision's image, network `none`, no environment file, no files volume, uid 10151 with the application's group 10150, read-only root, all capabilities dropped, 1536m without swap, two CPUs, init, a health check that pings its socket; volume `cpt-studio-convert` (the socket alone, 10151:10150 0750). A worker of a revision that has it mounts the volume read-only and is told the converter is required; an older revision's worker converts in-process as before |
| edge logs | `/var/log/nginx/cpt-studio-access.log` (format `cpt_studio`: the path without its query string, the request id, the session reference) and `cpt-studio-error.log` (warn), kept by the host's nginx log rotation (release 1, A2) |
| application logs | `/var/log/cpt-studio/` root 0700: `containers/<role>-<revision12>-<UTC>.log` (root 0600), the ids-only copy of each container a deploy removes, and `oneshots-<UTC date>.log` (root 0600), one line per one-shot and helper run; both deleted after 14 days (D7; release 1, A13) |
| exports | `/var/lib/cpt-studio-exports/` root 0700: one new folder per practice export (**manage** `export-workspace`), root-only once written (release 1, D2) |
| ingress | NEW `/etc/nginx/sites-available/quillmd-cpt` + `sites-enabled` symlink: one HTTPS server block for cpt.quillmd.com and admin.quillmd.com (D396). The `quillmd` vhost (QuillMD's) changes in one line alone - its :443 `server_name`, line 26, loses `admin.quillmd.com` in `ingress` and gets it back in `ingress-rollback` - under the coupling invariant (**The admin host and the coupling invariant**) |
| certificate | lineage `cpt-studio` for cpt.quillmd.com and admin.quillmd.com, webroot `/var/www/certbot` for both, existing ACME account; the earlier lineage `cpt.quillmd.com` stays and keeps renewing: no stage of this revision loads it, but the stage `ingress-rollback` gives back does |

Every Docker object carries `org.quillmd.cpt-studio=1` and a role label; the
installer refuses to touch a same-named object without them.

The physician PDF report (2026-11-21) adds no host object. The image installs
ReportLab, with pillow and charset-normalizer, from `requirements.txt`; the
report's fonts ship in the code tree under `studio/report_fonts/` (their
licences and `PROVENANCE.md` beside them) and are read from there, not
collected as static files. `ops/scan_customer.py` reads a PDF export with pypdf
(`requirements-dev.txt`): run it with a Python that has pypdf, or every PDF
export fails the scan.

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
revision and carry no unfilled revision placeholder. Every option is given
once: one given twice (as `--name value` or `--name=value`) is refused before
anything runs, the receipt's `given_more_than_once` naming it (refutation round
2, installer-2: the last value had run and the first was dropped without a
word - a command line edited from an earlier one closed the practice named
last, for good).

**The door's ceiling.** The door kills what it runs after `RULED_ACT_MAX_SECS`
of wall clock (`scripts/lib/run-watched.sh`; by default as long as one worker's
stop), wherever it is. `app`, `switch-back` and `rollback-app` may each wait for
a worker to stop once or twice (each wait up to 60 minutes since the Fable
coding build), so they refuse to start, changing nothing, unless the ceiling is
at least 9,000 s (two stops and a margin; the receipt's `door.ceiling`): run
them as `RULED_ACT_MAX_SECS=9000 bash scripts/run-ruled-mutation.sh ...`. The
installer reads the value exactly as the door does: digits only, in bash's
signed 64-bit arithmetic, so a value of 2^63 or more is its 64-bit wrap (19
nines reads as the door's default ceiling, which the door would run at, and is
refused).

Each phase prints one JSON line `{"phase", "ok", "summary", "receipt"}` and
writes `<phase>-<UTC>.json` (0600) plus any command logs into the receipts
directory. Exit 0 = done; 1 = refused or failed (the receipt says which and why).

## Phases, in order

| # | phase | extra arguments | changes |
|---|---|---|---|
| 1 | `preflight` | — | nothing (one ACME probe file written and removed) |
| 2 | `secrets` | — | creates `/etc/cpt-studio/` and its two files, once; copies the coder's Anthropic credentials source when the owner placed it, once; an earlier `gemini.env` is reported, never touched |
| 3 | `image` | — | builds `cpt-studio:<sha12>` |
| 4 | `db` | — | network, two volumes, database container; release 1: an existing container's memory and swap set to 512m/512m in place (`docker update`, no restart) when its peak allows, and its statement logging set (`ALTER SYSTEM`, a reload, no restart) |
| 4a | `converter` | — | `cpt-studio-converter` and its volume from this revision's image (release 1, A7): started, kept, or replaced; before `app` |
| 5 | `app` | `--coding-mode live --authorization-ref docs/foundation/rulings/2026-10-23-cpt-studio-gi.md` (or `--coding-mode disabled`): the Fable coder's mode, always explicit (`CPT_STUDIO_CODING_MODE`; live needs `--authorization-ref` and `/etc/cpt-studio/anthropic-credentials.env`, mounted read-only into the worker alone); Corti, the participants and the interpreter are started disabled, and their arguments are a `switch-back`'s alone | migrations; web and worker containers - on a served site blue/green: the incoming web on the idle port, the worker handed over, the vhost's upstream switched (`nginx -t`, a graceful reload: the two `sudo -n` commands), the old web drained and stopped, an availability record of the public `/health/` in the receipt |
| 6 | `reference` | `--pfs-zip <abs> --pfs-retrieved-at <ISO> --mue-zip <abs> --mue-retrieved-at <ISO>` | reference copies in the files volume; two `ReferenceSource` imports |
| 7 | `passages` | — | each committed `studio/reference/data/` file imported (`PassageSource`, `ReferencePassage`); idempotent |
| 8 | `license-note` | — | CPT Studio's own licence note on each imported reference source (`ReferenceSource.license_note`): exactly the old text replaced by the corrected one, nothing else; idempotent |
| 9 | `provision` | `--owner-username <name> --by <person>` (optional `--specialty`, `--agent-username`, display names, `--reset-passwords`) | a specialty's workspace (Gastroenterology unless `--specialty` names neurosurgery or orthopedic-surgery), its owner (who chooses a new password at the first sign-in) and - only when `--agent-username` names one - a review agent; credentials files |
| 9a | `operators` | optional `--reset-passwords`; `--by <person> --review-by <YYYY-MM-DD>` when it grants; `--regrant <name>` for a revoked account the declaration approves (`Approved: --regrant <name>`) | the human platform-operator account (no membership, an unusable password), its grant, and a setup code kept root-only |
| 10 | `http-vhost` | — | `quillmd-cpt` (HTTP stage) + symlink; nginx reload (a fresh host; refused while `quillmd-cpt` claims admin's :443) |
| 11 | `cert` | — | lineage `cpt-studio` for both hosts (on a fresh host after `http-vhost`, or on a served site) |
| 12 | `ingress` | — | admin.quillmd.com's :443 moved onto `quillmd-cpt`: this revision's HTTPS stage and the `quillmd` vhost's line 26, one root-helper write, one nginx reload |
| 12a | `https-vhost` | — | a later `deploy/nginx/` change republished: `quillmd-cpt` replaced in place by this revision's HTTPS stage (both stages name admin); nginx reload |
| 13 | `verify` | — | nothing |
| 14 | `manage` | `--command <act>` and that act's arguments (**manage**, below) | one allow-listed ruled act of the application, run once this revision's migrations are applied |

`switch-back` returns to the pair this revision's last successful `app` replaced
(its receipt's `replaced`; images are never removed; after a same-revision
re-run, the pair an earlier `app` since the last `switch-back` replaced) by the
same switch in reverse, so the site is never interrupted: see **Switching back**.
`rollback-app` removes the web and worker containers - the site is down from
that moment until a pair is installed again; prefer `switch-back` after a
successful `app`. (In an undo's layout - the S4 keep layout, or the back layout
an S3 undo that stopped half way leaves - `rollback-app` acts on the right
containers instead, with this revision's image, and the site stays served: see
**Recovery notes**. With a `cpt-studio-web-next` in any other layout, or a web and
a worker of different images, it refuses and stops nothing: which web serves, and
whose records to read, cannot be told from the names. It removes only this
revision's own pair: a web or worker under the canonical names that carries
another revision - the old pair an undo put back - is refused, and nothing is
stopped.) When the web that serves next has no session policy - in the keep
layout the old web, in the removal the parked pair, or a pair not known when
none is parked - it ends every session first (refutation round 2,
sessions-2: **Known limits**), as a `switch-back` does at B4. It keeps the database,
volumes, images and secrets, and needs the database to be running. First, with
the pair's own image, it reads the records their revision made that an older
revision would act on, or show, wrongly (listed under **Reinstalling an older
revision**): while any exists it refuses, naming the encounters, and stops
nothing. Otherwise it stops the pair, closes every stage it queued, ran or left
resumable since it was created, and every stage of a kind the next worker cannot
run (queued, running, or cancelled as its encounter's latest stage) whichever
pair created it, settles the provider runs they left unsettled (as **app**
below does on a failure), reads again, and only then removes the pair. The next
worker is the parked pair's when one is left (its kinds read from its image);
otherwise one that runs extract, analyze, predict and assess only. A harness
stage is closed like a second review's whenever that worker has no stage for
it, as failed, with the installer's message naming the revision (no web offers
a Resume for it): the participants' `astra` and `fable`, which no revision
before the harness (80df1831d168 and older) runs, and harness@2's peer reviews
`astra_peer` and `fable_peer` (HARNESS.md 11.1), which no revision before
harness@2 runs; a next worker that runs some of them (read from its image)
keeps those, and the rest are still closed. If the stages
cannot be closed, or the second read names a record (a request in flight when
the worker stopped is then an unknown outcome), the pair is left stopped, not
removed: start it, clear the records, rerun.
`rollback-vhost` removes `quillmd-cpt` and its symlink (only if their bytes are
this installer's) and reloads nginx; the certificate lineage is kept. It runs
only while the `quillmd` vhost claims admin.quillmd.com's :443 (the before
state): while `quillmd-cpt` does, a removal would leave admin claimed by
nothing, so run `ingress-rollback` first. `ingress-rollback` gives
admin.quillmd.com's :443 back to the `quillmd` vhost and `quillmd-cpt` the
stage `ingress` replaced (**The admin host and the coupling invariant**).

### What each phase checks before and after

- **preflight** records the baseline the later phases compare against: sha256
  of every readable `sites-available` file, the `sites-enabled` links,
  `nginx.conf`, `sudo -n nginx -t` (with its warnings), a HEAD probe of every
  `server_name`/listen pair in the enabled vhosts against local nginx (status
  and certificate fingerprint per SNI, plus an unmatched host), the current
  answers for `cpt.quillmd.com`, `https://app.quillmd.com/health/`,
  `scripts/check-cotenants.sh`, containers, volumes, networks, the two web
  ports - the active one (the port `cpt-studio-web` publishes, else the one the
  live HTTPS stage proxies to, else 9150) held by `cpt-studio-web` alone, the
  other free for the next incoming web, and no `cpt-studio-web-next` left from an
  interrupted `app` - and 55451, DNS (A `147.189.172.8` only, no AAAA), the pinned helper and postgres
  images, Let's Encrypt state by path (live
  names, renewal-config hashes, account ids — key material is never opened)
  and that the ACME webroot is writable. It also records whether the coder's
  Anthropic credentials source is there (`coding_source`): one that is absent
  is not a problem (the coder can then only be installed disabled), but a
  sources directory that is not root 0700, or a source that is not a root 0600
  regular file, is. Corti's source is no longer required, and no other source
  is read. Since release 2 of the admin move it also records the coupling of
  the `quillmd` vhost and `quillmd-cpt` (before or after is a baseline; any
  other state is a problem), checks admin.quillmd.com's DNS (A `147.189.172.8`
  only) and proves its HTTP-01 route (a probe file served for
  `http://admin.quillmd.com/.well-known/acme-challenge/` through 127.0.0.1: the
  `quillmd` vhost's :80 block), and requires that `scripts/check-cotenants.sh`,
  told to skip admin.quillmd.com, judged no row for it. Any problem fails the
  phase.
- **secrets** generates the Django key and database password inside the root
  helper; the values never leave it. The set is `app.env` and `db.env`: Corti's
  source is no longer read and Corti's copy no longer written or checked (one
  an earlier install wrote stays as it is). A partial or altered set is
  refused, not repaired. Then, separately from that set, the coder's Anthropic
  credentials source, when the owner placed it, is copied once, unread, byte for
  byte, through the root helper:
  `/etc/cpt-studio-provider-sources/anthropic.env` to
  `/etc/cpt-studio/anthropic-credentials.env`, 10150:10150 0400, then read
  back. The sources directory is mounted (read-only) only once it is seen to be
  a root 0700 directory, and the source is opened without following a link and
  must be a root 0600 regular file of at most 32,000 bytes. Only key NAMES are
  checked: `ANTHROPIC_API_KEY` (and optionally `ANTHROPIC_WORKSPACE_ID`), each
  once and nothing else. Only those expected names are ever reported: a line
  setting any other key is counted, never echoed, since a key pasted without its
  name would otherwise be printed as one. Every check runs before anything is
  written. A copy already there must be the 10150:10150 0400 file and equal its
  source; one whose source was since removed is reported `present` with its
  source `absent`. A missing source is `not provided`: the coder can then only
  be installed disabled. The receipt's `coding_credentials` names its state,
  whether its source is there and the expected key names found; no value leaves
  the helper. Astra's `openai.env` is no longer read.
- **image** first reads the revision's migrations (with `ast`; nothing is
  imported or run) and refuses, before building anything, any migration after
  0005 that is not additive for a pair that does not know it. 0005 is the leaf
  of 057a7d39, the oldest revision a rollback goes back to; `app` migrates while
  the previous pair still runs, a failed replacement restores that pair on the
  migrated schema, `rollback-app` hands an older pair the rows, and nothing is
  reversed. Accepted: a new table; a column that is nullable, has `db_default`,
  or whose database default the same migration's SQL sets (an older pair's
  insert names no such column) - but a unique column (`unique`, a primary key or
  a one-to-one field) added to an existing table only when it is nullable with
  no database default: an older pair's inserts then leave it NULL, which a
  unique constraint never refuses, where a default gives every one of them the
  same value and refuses the second; Django's own (non-unique) index, or any index on
  a new table; a unique index (`studio.models.UniqueIndex`) only when it is
  partial over rows whose column - one the same migration adds as nullable,
  with no database default, and one the index holds - is set
  (`condition=Q(<column>__isnull=False)`: an older pair never writes that
  column, so its rows hold NULL there and stay outside the index, and none of
  its writes is refused); a constraint on a new table; SQL
  that only sets column defaults. Anything else (a removed, renamed or altered
  column or table, a constraint or any other unique index on an existing table,
  an index of a class the check does not read, `RunPython`, other SQL, a form
  the check does not read, a file in the migrations directory that is not a
  migration) is refused. The receipt records each checked migration and why it
  passed. 0016 (the Fable coding build) passes: four new tables -
  `CodingRound` (its two nullable columns of the converted Word view among
  them), `CodingAnswer`, `CodeDecision` and `ExportArtifact` - and a constraint
  on a table it creates; no column is added to an existing table. 0006, 0007
  and 0008 pass: 0007 adds `endpoint`, `requested_model`,
  `returned_model` and `response_id` to `studio_providerrun` and `participants`
  and `retrieval` to `studio_assessment`, each NOT NULL and each given a
  database default by the same migration's SQL, and creates `PassageSource` and
  `ReferencePassage`, tables no older revision reads. 0008 (harness@2) only
  creates tables no older revision reads - `ProviderExchange` (each HTTP
  exchange of a participant's tool loop), `ToolCall` (the tool traces) and
  `FindingConfirmation` (reviewer-confirmed answers) - and puts its two unique
  constraints on two of them; it adds no column to an existing table. Their
  foreign keys point at existing rows (provider runs, clarifications,
  encounters, revisions, users), which no revision deletes (057a7d39 and
  80df1831d168 delete no row), so a row of theirs never refuses an older
  pair's write. So the previous pair keeps
  inserting valid rows between `migrate` and the swap, and a restored or older
  pair runs on the migrated schema. The phase then builds, and requires the
  revision label, user 10150, the baked release, `manage check`, and that the
  WSGI application loads as the image's own user on a read-only root (this is
  what catches unreadable static files, which `manage check` does not). The
  same way (as the image's own user, read-only root, no network), two checks
  replace the earlier OCR and PDF-reader gates - the image reads no PDF and
  runs no OCR now, the coder sends the original file:
  `soffice --version` must run and name LibreOffice (it converts an uploaded
  Word file to PDF; its version line is reported in the receipt's `soffice`,
  never pinned), and `python -c "import anthropic; print(anthropic.__version__)"`
  must print exactly anthropic 2.11.0, the SDK release the coder sends through
  (the receipt's `anthropic`). Either failing refuses the image, with what the
  command printed in the failure log. Then the **conversion gate**: a real
  Word-to-PDF conversion inside the built image, as the worker runs one - the
  application's own entry point (`studio.fable.document.convert_docx`:
  LibreOffice in its bounded child, 60 s, a throwaway HOME and profile, no
  inherited environment) under the worker's runtime constraints (user
  10150:10150, a read-only root, `/tmp` a tmpfs, the worker's memory and pids
  limits) and with no network - of a tiny synthetic Word document the installer
  builds (`synthetic_docx`: three parts, one paragraph, fixed timestamps, the
  same bytes every time). Its PDF must start with `%PDF-`, or the image is
  refused (every Word upload would fail its conversion); the receipt's
  `conversion` records the PDF's size and sha256, never pinned (LibreOffice
  stamps a creation time in it).
- **db** is idempotent; an existing container must be ours, on the pinned
  image, loopback-only, `unless-stopped`, with every capability dropped, core
  dumps off and a 128 MiB `/dev/shm` - anything else refuses before anything
  changes (recreating the container would interrupt the site: the owner's
  call). Release 1 (A3): its memory and memory + swap must be 512m each and its
  own cgroup (read inside it) must allow no swap. When they differ, the
  cgroup's `memory.peak`, `memory.swap.current` and `memory.swap.peak` are read
  first, and `memory.peak` plus the swap's high-water mark (`memory.swap.peak`,
  never less than what sits in swap now) - swap the database used, even if it
  has since paged it back, is memory it needed (refutation round 1,
  installer-2) - must stay below 80% of 512 MiB; a cgroup whose
  `memory.swap.peak` cannot be read skips the change (its limits left as they
  are, the receipt saying why). The limits are then set on the running
  container (`docker update
  --memory 512m --memory-swap 512m`: no restart, no connection dropped) and the
  receipt records them before and after; otherwise it refuses and prints the
  numbers, so the owner can choose a larger limit. `memory.peak` counts only
  since the container last started, so the change is made only once it has run
  7 days (a week of the practices' use); a younger one is skipped - its limits
  left as they are, the receipt saying why - and `verify` reports the swap
  until a later `db` makes the change. A stopped database is never started
  here: the phase refuses, starting and changing nothing. Then (A5) `ALTER SYSTEM` sets
  `log_min_error_statement` to `panic` and `log_error_verbosity` to `terse`
  (they persist in `postgresql.auto.conf` on the data volume), `pg_reload_conf()`
  applies them without a restart, and `SHOW` on fresh connections must read
  them, or it refuses: a failed statement is then logged without its text or
  values. psql runs inside the database container as the bootstrap user over
  its own socket, as the readiness probe does. A new cluster gets the same two
  settings as server flags (`db_args`).
- **converter** (release 1, A7; after `image`, before `app`) needs this
  revision's image and a revision that has the converter service
  (`studio/converter_server.py`). It makes the volume `cpt-studio-convert` and
  gives its root to the converter's uid (10151:10150 0750, through the root
  helper), and reads it back before anything starts: the image does not make
  `/run/cpt-convert`, so a fresh volume's root would be root's and the converter
  could not make its socket there. Every mount of that volume says
  `volume-nocopy`, so Docker never copies an image's mount point over this
  preparation. It keeps a converter of this revision that runs healthy and sealed; and
  otherwise stops the one there (its log kept, ids only), with a grace that lets
  a conversion in progress finish (80 s: LibreOffice's own 55 s inside the
  converter's 70 s; the figure is Lane 5's to confirm), removes it and starts
  the new one - network
  `none`, no environment file, no files volume, no credential, its own uid,
  init on - then waits for its health check. A Word conversion asked for in the
  few seconds between fails as busy and can be retried. The image gate runs the
  converter's self-test as the converter runs (its user, limits, read-only root,
  `noexec` `/tmp`, no network) and passes only on exit 0 with its success line
  (`cpt-studio converter self-test: ok, a PDF of ...`). `app` refuses to start
  anything until a healthy converter of this revision runs (`run --phase
  converter first`), and a `switch-back` to a revision that has the converter
  refuses until one runs; an older revision's pair never uses it.
- **app** (live mode) first checks the Fable coder's credentials
  (`--coding-mode live`) before anything changes: its copy in `/etc/cpt-studio/` must be
  the 10150:10150 0400 file the secrets phase writes (a missing source leaves
  none, and the coder can then only be installed disabled), and the
  application's own loader (`studio.fable.credentials.load_anthropic_credentials`)
  must read it in the worker's mount layout with no network and the coder itself
  disabled. A refusal's error output is kept in the receipt directory only once
  a root helper has found no value from that file in it. Corti's and Astra's
  files are neither required nor mounted. The new web and worker are both given
  `CPT_STUDIO_CODING_MODE` (the mode given), `CPT_STUDIO_CODING_EFFORT` (`max`,
  the owner's setting) and the two owner figures `CPT_STUDIO_DOCUMENT_CEILING_USD`
  and `CPT_STUDIO_CONCURRENT_DOCUMENTS` at the defaults the revision's
  `cptstudio/settings.py` gives them (read without running it; each must be
  given exactly once, as one `_env('<name>', '<value>')` call, and be valid - a
  non-negative amount of US dollars, a whole number of documents of at least 1 -
  or nothing is started); every one-shot is given them too. They replace the
  question stage's `CPT_STUDIO_QUESTION_*` figures, which no container is given
  now. Corti (`CPT_STUDIO_PROVIDER_MODE`), the participants and the interpreter
  are named disabled. Live, both are given
  `CPT_STUDIO_ANTHROPIC_CREDENTIALS_FILE=/run/cpt-studio/anthropic-credentials.env`;
  only the worker mounts the file there, read-only (the web builds nothing that
  needs it). Every one-shot runs with the coder disabled. No access check runs:
  the install sends nothing to the vendor.
  After migrating (as before), and right before anything is started or
  stopped, it reads how the site is served and so how the pair is replaced
  (containers first, the vhost only where it decides), refusing - starting and
  stopping nothing - a state it cannot read as one of these (`preflight` has
  already refused a held idle port and a leftover incoming web before the
  install began): **blue/green** when `quillmd-cpt` is this revision's HTTPS stage
  proxying to the port the running `cpt-studio-web` publishes (the site is
  served: the incoming web goes on the other port, which must be free, with no
  `cpt-studio-web-next` or `*-previous` left over, and the preflight receipt -
  the baseline the switch is verified against - must exist, and co-tenant
  routing and app.quillmd.com must still answer as it recorded: a baseline that
  no longer holds refuses the switch before anything starts, starting and
  stopping nothing - run `preflight` again, then `app`); otherwise the
  **swap** of a host where nothing is served through the vhost (no
  `quillmd-cpt`, its HTTP stage, or an HTTPS stage no running web answers),
  on 9150 or the port that HTTPS stage names. A vhost holding an earlier
  revision's HTTPS stage that this revision does not render for its port
  (`deploy/nginx/` changed) is refused for blue/green: the switch would change
  more than its upstream (see **Reinstalling a new revision**).
  It migrates with a one-shot container first. Since release 1 (spec 6.2) that
  one-shot waits at most 5 s for a table's lock (`PGOPTIONS=-c
  lock_timeout=5s`: the migration files the image gate reads are untouched), so
  an `ALTER TABLE` never queues behind a long transaction with every later
  reader of that table queued behind it; Django applies each migration in a
  transaction of its own, so a timed-out attempt leaves that migration
  unapplied, and the one-shot is run again after 10 s, up to three more times
  (the receipt's `migrate_attempts`; every attempt's output is in the migrate
  log). Any other failure is not retried. It then reads (and records as
  `unrunnable_stages`, never refusing on them) the stages of a kind this
  revision's worker does not run - every kind of the pipeline before the Fable
  coding build - that are queued, running, or cancelled as their encounter's
  latest stage: this worker claims coding jobs only (`studio.jobs.claim_next`),
  its startup sweep settles every running stage of any kind, and a member's
  Review again retires a stage of the earlier pipeline left queued
  (`studio.decisions.retry`), so none can end it, where an earlier worker
  claiming one ended (refusing here would refuse every install over a site
  where one stage was ever stopped).
  **Design v2** (docs/gemini-migration/FINAL-V2.md 6.2 [R:MO-1]): then, still
  before anything is replaced, it reads the target twice in
  this revision's image. First it **refuses while a design v1 row exists** - an
  `Assessment` whose `engine_version` is exactly `cpt-studio-events@1`, or an
  `EventInventory` whose `interpretation_version` is exactly `gemini-events@1`
  (`V1_ROWS`; the receipt's `v1_rows` names the encounters). v1 rows only: v2's
  own rows (`cpt-studio-events@2`, `gemini-events@2/appraisal@1`), AMENDMENT-2's
  (`cpt-studio-events@3`, `gemini-events@3/appraisal@2`) and every legacy row
  never trip it, so a fix release after the walk, the re-install
  after a switch-back and a same-revision re-run all pass; live never held a v1
  row, and a test instance's are read as stored and never deleted here. Then it
  **counts, and never refuses on**, what the owner is told before the switch
  (`INSTALL_COUNTS`, the receipt's `install_counts` with its `report`, and a
  clause of the summary): every encounter and those with a coding round, every
  stage by kind and state (a stage of the earlier pipeline still queued is
  never run by this worker: its document reads as an earlier review until a
  member asks for it to be reviewed again; one still running is settled by the
  startup sweep), every provider run by purpose and state, the provider
  outcomes still unknown and not reconciled (their encounters named) and the
  runs left reserved or sending, the rows of the four tables of migration 0016
  (0 on the first install over a revision before it: more says this is a
  reinstall or a same-revision run), and the standing holds (each refuses every
  coding send until an operator releases it). A count that cannot be read is
  recorded as not counted and the phase goes on.
  **Blue/green** (the site stays served throughout; the receipt's `steps` time
  each step): **S1** the incoming web `cpt-studio-web-next` starts on the idle
  port and must answer `/health/` = `{status ok, service cpt-studio, data_mode
  synthetic-only, database ok, release <revision>}` there and serve its own
  sign-in page and every static file that page names (read-only GETs) - the
  old web still serves everything; **S2** the old worker is parked (`docker
  stop --time 3600`: its current stage finishes, nothing new is claimed) - the
  old web still serves, and what members start waits in the queue - and, when
  the old web's revision and this one do not share release 1's session policy
  (one of the two trees has `studio/sessions.py`: the first install of release 1
  over a revision before it, or `app` again after a `switch-back` to one; read
  from each revision's tree before anything starts, and a revision this
  checkout cannot read refuses, nothing started or stopped), every session is
  ended in this revision's image: every `django_session` row deleted and one
  SecurityEvent `sessions.ended_at_install` (the count and the two revisions,
  the actor label `installer`) written, in one transaction. None of them could
  be used once the new web serves (release 1's cookies have their `__Host-`
  names, B6), and ending them all keeps a session from coming back for whoever
  uses that browser next across a later switch (refutation round 1,
  rollback-0 and rollback-3). The receipt's `sessions_ended` says how many and
  the summary says so; a later release over release 1 ends none; **S3** the
  vhost's upstream is switched to the idle port: the live file must be this
  revision's HTTPS stage for the old port, and is replaced atomically by the
  rendering for the new one (the two differ in their `proxy_pass` line alone),
  `sudo -n nginx -t` must pass with no new warning, `sudo -n systemctl reload
  nginx` reloads gracefully (old nginx workers finish what they accepted), and
  `https://cpt.quillmd.com/health/` must serve this revision through the public
  path with the co-tenants and app.quillmd.com as the preflight baseline found
  them (read again right before the file is replaced: a baseline that drifted
  since S1 fails S3 before anything changes). When the old web is the same
  revision (a same-revision re-run), `/health/` cannot tell the two webs apart,
  so nginx must also be seen loading the switched file: new nginx worker
  processes started since it was written (`/proc`, the host master's children;
  nginx applies a reload by starting new workers and refuses one by keeping
  them, and `systemctl reload` exits 0 either way). In every switch a reload that
  was asked for is treated as applied, whatever its call answered: systemd runs a
  reload job it took even when its client is interrupted (Ctrl-C) or gives up
  at the 30 s timeout; **S4** the new worker starts - processing resumes under
  the new rules;
  **S5** the old web is drained - at least 130 s (above gunicorn's 120 s
  request timeout), then until 10 consecutive one-second samples of
  `/proc/net/tcp` and `tcp6` show no connection to its port a request can be in
  flight on and no host nginx worker still shutting down from the reload, never
  longer than 600 s (the receipt's `drain` says `bounded_out` then) - and only
  then stopped (graceful, 30 s), parked as `cpt-studio-web-previous`, and the
  incoming web renamed `cpt-studio-web` (in place: nothing restarts). From
  before S1 to the end, a thread probes `https://cpt.quillmd.com/health/` every
  0.5 s through the public path and the receipt's `availability` records
  `{samples, statuses, releases_seen, non_200, non_200_count}`: any non-200 is
  the declaration's stop condition to judge. The receipt also records `ports`
  `{from, to}`, the `switch` (vhost sha256 before and after, the `nginx -t` log,
  the HTTPS observations), the `drain`, and the `smoke` of the incoming web.
  **Swap** (a host where nothing is served through the vhost): the current
  web/worker are parked (`*-previous`), the new pair starts and the phase waits
  for `/health/` as above and a worker that stays up. Every session is ended
  as at S2 once both old containers are stopped, before the new web starts,
  when the pair replaced and this revision do not share release 1's session
  policy; a failure there restores the parked pair. Once the new
  pair runs - and before the parked pair is removed - every encounter's stored
  list state is recomputed with this revision's derivation (only a changed one
  is written; nothing is sent; the receipt names each that changed): the
  revision replaced may have derived it otherwise (an unreconciled unknown
  outcome it listed as reviewed is on this revision's review queue; a response
  refused whole it listed as 'No CPT codes proposed'), and an action on the
  encounter is otherwise the only thing that recomputes it. In blue/green this
  runs only once the drained old web has stopped too (old code recomputes a
  state on any action it serves), so during the drain the new web lists the
  stored states as the old revision derived them. A provider outcome
  still unknown is not refused: reconcile it on this revision's web. Whatever
  stops the phase once the new pair runs - the recompute fails, the parked pair
  cannot be removed, the installer is interrupted (Ctrl-C) - the pair keeps
  running and the receipt says whether the states were recomputed: if not,
  remove the parked pair (`*-previous`) by hand if it is left - keeping its log
  first (**Recovery notes**, a parked container's log) - then rerun `app`,
  which recomputes them; if they were, only the parked pair is left to keep and
  remove. Release 1 (A13): before any container is removed - the parked pair, an
  undo's incoming web or new worker (S1, S3, S4), a switch-back's, rollback-app's
  pair - its log is kept ids only in `/var/log/cpt-studio/containers/` (the receipt's
  `logs_kept`: a file name, its sha256 and the lines kept and dropped, never a
  line); a copy that fails removes nothing, and the receipt says so. A web's
  access lines are kept in release 1's format and in the one before it (no
  request id or actor: the web this install retires, and one a `switch-back`
  to such a revision started), each its address, path, status, size and time
  only (refutation round 1, installer-6). A static
  file's name in a kept path is written `static-file` (its content hash and
  extension kept): its name part could carry free text. The failure note an
  undo writes into the receipts folder (`*-incoming-web-failed.log`,
  `*-worker-failed.log`) holds the container's last 200 lines ids only, with
  how many were dropped - never a raw line, so a traceback's document text never
  reaches it.
  An installer killed outright writes no receipt: rerun `app` (see **Recovery
  notes**).
  **A blue/green step that fails, or is interrupted (Ctrl-C), never stops the
  serving web**; the receipt says what is left (`failed_at`, `left`: the port
  the vhost names and every CPT Studio container's state, port and image):
  - S1 (the incoming web is not healthy, or does not serve its pages): it is
    stopped and removed; nothing else changed and nothing is closed - no
    customer request reached it.
  - S2 (the old worker could not be parked, or the end of every session
    failed): it runs again (park starts it when its rename fails); the
    incoming web is removed. An end that was started and gave no answer may
    have ended every session: the receipt says so (everyone may have to sign
    in again on the old revision), never that nothing else changed.
  - S3 (`nginx -t`, a new warning, the reload or the verification): the exact
    previous vhost bytes are put back, and nginx is reloaded with them whenever
    a reload of the switched file was asked for, so the old web serves. Whenever
    nginx may have run the switched file - a reload of it was asked for,
    whatever its call answered, or nginx loaded any configuration since the file
    was written (anyone's reload: the TLS renewal hook's, a co-tenant's) - the
    undo reloads the restored file once more and must prove nginx runs it (new
    nginx workers seen, and the public `/health/` answered by the old revision;
    the new workers alone when both webs are the same revision) before the
    incoming web is drained and removed; when that is not proven, both webs are
    left running, the old worker parked and nothing closed (a switch that stopped
    half way: **Recovery notes** - this revision's `rollback-app` finishes the
    undo; the old worker is never started by hand). Every stage queued, run or
    left resumable since the file was replaced, and every open stage of a kind
    the old worker cannot run, is closed as failed (the new web may have served
    seconds of requests; this can also close what a member started on the old
    web in those seconds), and closed again once it has stopped taking traffic:
    the incoming web is drained and stopped, and only then closed again (it
    finished the requests it had accepted; a request an old nginx worker still
    held after a drain that ended `bounded_out` can no longer queue a stage that
    close does not see). The list states the old revision labels otherwise are
    put back after each close, the incoming web is removed, and the old worker
    is put back and started - held, as in the swap below, while either close
    names records it would act on under its own rules, or records only a
    revision since the core repair writes (a member's answer, a reviewer's
    chosen modifier: no worker makes either) written since the file was
    replaced: a revision before the core repair shows them wrongly, and its
    worker's re-assessment would drop a chosen modifier. Since the completion
    repair (2026-11-06) a member's answer also re-makes the assessment, whose
    answered code a revision before it reads as an ordinary exclusion - so a
    base code that answer still held may show READY there; the standing answer
    that made it names the encounter for the same reason. Which web wrote one
    cannot be read - a revision since the core repair writes them too, and
    reads them as this one does - so the receipt says when each was written,
    never by whom. Such records written before the switch began are named only:
    they were beside the old pair before this install (the close says which,
    and one it does not place in time holds). A state the old web would merely
    show wrongly that a worker made (a second review's, a harness
    participant's) is named in the receipt only: the old web never stopped
    showing it, and no new worker ran. The old worker is put back as it was: one
    that was not running when the install parked it (an earlier undo held it,
    or a person stopped it) is left stopped. A close or put-back that does not
    finish (it may have closed some stages before it stopped: the receipt says
    so), or an incoming web that cannot be stopped, stops the undo there: the
    incoming web stays beside the old web and the old worker parked, and
    `rollback-app` finishes it (**Recovery notes**).
  - S4 (the new worker is not ready): it is stopped and what the new pair
    started is closed. When the close names a state the old web would show
    wrongly whatever it is handed (**second_review_refused**,
    **second_review_unread**, **participant**, or a member's answer or chosen
    modifier written since the switch began - one written before it was beside
    the old pair before this install, and is named only) and the old pair is
    another revision, the NEW web keeps serving (it shows them correctly), its
    worker stopped and the old worker parked: nothing is processed until a
    person decides (**Recovery notes**). Otherwise the states are put back and
    the upstream is switched back the same way (graceful reload, `/health/` = the
    old revision), the incoming web is drained and stopped, what the new web
    started is closed again once it has stopped taking traffic (it took every
    request until the switch back's reload, and finished those in flight during
    the drain), the states are put back again, the incoming web is removed with
    the new worker, and the old worker is put back and started, as it was - or
    held, while either close names records it would act on, or the second one a
    state the old web shows wrongly written since the first close (a member's
    answer, a chosen modifier; the receipt names it and when it was written). An
    incoming web that cannot be stopped, or a second close or put-back that does
    not finish, leaves the old web serving, the incoming web beside it and the
    old worker parked, for `rollback-app` (**Recovery notes**). A close, put-back or
    switch back that fails also leaves the new web serving - unless the switch
    back's reload was asked for: then the undo reloads the new web's vhost again
    and must prove nginx runs it, and when that is not proven both webs are left
    running, the new worker stopped and the old worker parked, and the receipt
    says that nginx may route to either web.
  - S5 (the drain or the renames): the new pair serves and nothing is undone;
    the receipt says which names are left and that the stored list states were
    not recomputed (rerun `app` once it is resolved).
  - An installer killed outright (`kill -9`, or the door's ceiling) inside S3
    writes no receipt and runs no undo: see **Recovery notes**.
  On any failure of the swap before the new pair runs, the recompute does not
  run: the new pair is stopped and, before the parked pair is restored, every
  stage
  it queued, ran or left resumable since the swap, and every stage of a kind the
  parked worker cannot run (read from the parked image; when it cannot be read,
  every kind but extract, analyze, predict and assess) that is queued, running,
  or cancelled as its encounter's latest stage, whichever pair created it, is
  closed as failed, naming the revision (failed, not cancelled: no web offers a
  Resume for it), and the provider runs they left unsettled are settled as the
  stale-stage sweep settles them (the closed encounters' states are refreshed).
  Nothing finished is touched and no row is removed. If the close then names
  an encounter whose state the parked revision would show wrongly whatever it
  is handed - a bounded second review's response refused whole, a second
  review left unread, or a code only a harness participant proposed
  (**second_review_refused**, **second_review_unread**, **participant**,
  under **Reinstalling an older revision**) - and
  the parked pair is not this revision, nothing is restored over it: the new
  pair is left stopped and the parked pair parked, and the receipt names the
  encounters. To keep this revision, remove the parked pair by hand and rerun
  `app` once its failure is fixed; to go back, start this pair again, clear
  them on its web, run `rollback-app`, then rename the parked pair back. (A
  parked pair of this same revision - a same-revision re-run - shows them as
  this revision does, and is restored as below.) Each stored state this
  revision labels from more than the state - the primary answer's response
  refused whole is `provider_failed`, which this revision labels 'Provider
  response not used' and the parked revision would list as 'Provider request
  failed' - is then given the state the parked image itself derives for it
  (see **Reinstalling an older revision**). Then the new pair is removed and
  the parked pair renamed back. Its web is started. Its worker is started too
  unless the close names records it would act on wrongly (listed under
  **Reinstalling an older revision**); then the worker is left stopped - it
  alone holds the credentials files, so nothing can be sent - and the receipt
  names the encounters: install this revision again once its failure is fixed
  (its worker reads those records under its own rules). If the stages cannot be
  closed, or those states cannot be put back, the new pair is left stopped and
  the parked pair parked (the receipt says so): run `rollback-app`, then rename
  the parked pair back. Migrations already applied are not reversed.
- **Work in flight at the switch** (or the swap) is not frozen: in blue/green
  the old worker stops (S2) before the new web takes traffic (S3) and the new
  worker starts only once it has exited (S4): no worker of the old code claims
  a stage the new web queued, and the two workers never run together. What
  members start between S2 and S4 waits in the queue (the old worker's
  remaining stage time, about a second when idle, up to 3,600 s), inside the
  120 minutes a queued stage waits. **The Fable coding build's worker runs no
  stage of the pipeline before it**: it claims coding jobs only
  (`studio.jobs.claim_next`), so a stage of an earlier kind the previous pair
  left queued is never run - its document reads as an earlier review until a
  member asks for it to be reviewed again, which retires that stage
  (`studio.decisions.retry`) - and its startup sweep settles one left running
  (cancelled, or unknown when it was sending). `app` reads these stages before
  the switch and records them (`unrunnable_stages`), never refusing on them;
  the install counts say how many were queued and running. What follows in
  this item describes the pipeline before the Fable coding build, kept for the
  record. Round r3's question stage is a reading stage like
  interpret and appraise: a question round the previous pair queued is
  finished by the new pair, which recomputes it from the stored question runs
  (a request whose identical request this document has a deciding outcome for
  is never sent again); a round whose requests were in flight when the old worker
  stopped is the old worker's to finish (its stop timeout outlasts the round);
  one cut short is recorded unknown, request by request, and waits for its
  reconciliation. A predict the previous pair queued
  (for an upload, a date change, a Resume or a reconciliation) sends its one
  request, for the context remade under the new rules, unless a recorded
  answer is reused, an unknown outcome waits for its reconciliation, or that
  request was already sent for this document and failed (a not-sent run then
  names that failure; nothing is sent again); a member's conflicting service
  date is held, not sent. A re-assessment never asks for the bounded second
  review: a reviewer does (ARCHITECTURE 5.11).
  When no recorded answer answers the request the remade context makes (the
  new rules read a date the old ones could not, or the previous pair sent
  nothing), the predict a re-assessment or the stale-stage sweep queues for it
  runs as any other (a disabled provider, a request that cannot be built, a
  retained answer, an unknown outcome and a request that already failed for
  this document are recorded and shown as such) but stops where it would
  send, with the reason, for a member's Resume (the encounter reads Stopped;
  the Resume sends that request once).
  Encounters with nothing in flight are neither reprocessed nor sent until a
  member acts. To install with nothing in flight, let the queue drain (or Stop
  the encounters) before `app`.
- **reference** requires each zip to match its pinned size and sha256 and
  passes the pinned release, URL and window with the retrieval time you give.
- **passages** (after `app`) lists every file the revision commits under
  `cpt-studio/studio/reference/data/` (`git ls-tree` of the revision; the image
  ships exactly those, built from `git archive` of it) and refuses a link or a
  submodule there, or an empty directory, before any container runs. It then
  refuses unless `manage migrate --check` passes with this revision's image (the
  passage tables are migration 0007's: run `app` first), and imports each file
  with the application's own importer,
  `manage import_passages --data /app/studio/reference/data/<file>`, one
  one-shot per file, in name order. The importer is idempotent, so the phase is
  too: rerun it freely. The receipt records each file's git blob id, the
  importer's output and its log; a failed import names its file and the files
  imported before it (they stay imported). Until it has run there is no
  passage to retrieve, and an assessment the new pair makes meanwhile is
  recorded without one: to have none, run it right after `app`, or let the
  queue drain first.
- **license-note** (after `app`) corrects the note CPT Studio itself writes on
  every CMS reference source it imports (`ReferenceSource.license_note`, from
  `studio.reference.importers.LICENSE_NOTE`), on the rows `reference` imported
  in this install or an earlier one. The owner, 2026-11-01
  (HARNESS.md 11.6): CPT Studio's own wording must not imply a licensing
  exemption. The rows imported before the importer changed read "CPT codes are
  copyright the American Medical Association; descriptors are not imported or
  displayed. Used for internal synthetic evaluation only; commercial CPT use
  requires an AMA license."; each becomes "CPT codes are copyright the American
  Medical Association; descriptors are not imported or displayed. CPT Studio
  holds no AMA licence; whether its use of CPT content needs one is an open
  owner decision." It refuses unless `manage migrate --check` passes with this
  revision's image (run `app` first), then runs in a one-shot of that image, as
  `passages` runs its importer. There it refuses, changing nothing, unless the
  image's importer writes exactly the corrected note (its next import would
  otherwise write another text than the rows hold). Then, in one transaction
  that holds the table against writers (readers are not blocked), every row
  whose note is exactly the old text gets exactly the new one. A row with any
  other note - even one differing by a space - is left as it is, and no other
  column or row changes: the rows are read before and after, and any other
  difference rolls the transaction back. The receipt records the number of
  rows, the counts of old, corrected and other notes before and after, the
  keys of the rows corrected and of those holding another note, both texts and
  their sha256, and how many recorded assessments carry the old note.
  Assessments and reports already made record what was shown and are never
  rewritten; every assessment made afterwards carries the corrected note, so a
  re-assessment records a new assessment rather than keeping the current one.
  Decisions carry to it (no proposal fingerprint includes a note); a decision
  that does not carry for another reason names 'reference sources' among the
  changes. It never touches `PassageSource`, whose notes quote each CMS file's own
  notices. With no row left holding the old text it changes nothing and says
  so: rerun it freely. Until it has run, an assessment the new pair makes still
  carries the old note: to have none, run it right after `app` (with
  `passages`), or let the queue drain first.
- **provision** writes its credentials files only after the accounts exist
  with the generated passwords; an account that already existed (password
  unchanged) aborts and discards them unless `--reset-passwords` was given.
  Passwords travel as RAM-only files under `/dev/shm`, never argv or output.
  Release 1 (A6, B4, C3): a review agent is created only when `--agent-username`
  names one (no default; no agent file otherwise); the owner's password is one
  staff set, so `provision` is given `--require-password-change` (the owner
  chooses a new password at the first sign-in, within 72 hours, after which an
  unchanged one stops working); and `--by` names the person who ran it. An
  operator account is never a practice's owner or agent: `platform-operator`
  and `ops-agent` are refused as either name, and the accounts named are read
  first - one that holds or ever held an operator grant is refused before any
  password is set or any file staged, so an operator's password never reaches a
  credentials file.
  `--specialty neurosurgery` or `--specialty orthopedic-surgery` (owner direction
  2026-11-22, D390) provisions that specialty's own workspace (named after it
  unless `--workspace-name` says otherwise), with a review agent when
  `--agent-username` names one (earlier installs named them `review-agent-neuro`
  and `review-agent-ortho`), and its own pair of files, `/etc/cpt-studio/initial-credentials-<specialty>.json`
  and `~/.cpt-studio/agent-credentials-<specialty>.json`; Gastroenterology keeps
  `initial-credentials.json` and `agent-credentials.json`, so provisioning one
  specialty never touches another's. One login serves one workspace until a
  workspace switcher exists: `manage provision` never adds an account to a
  second workspace (an account an earlier installation put in several keeps
  working there). An existing workspace is found by its name exactly as
  stored; a new workspace needs a name that does not name another specialty
  (read by its letters and digits, case aside: `orthopedic-surgery` names
  Orthopedic Surgery) and that no workspace of another specialty has exactly.
  A refusal states what is in the way. An empty `--workspace-name`
  is refused; without one, the workspace is the specialty's name. The
  specialty is a label the page and the PDF show; the coding path does not
  read it (D358).
- **operators** (after `app`; it needs the revision's operator grant, owner
  directive 2026-11-03 section 2, and refuses - creating no account - unless
  `manage migrate --check` passes with this revision's image) keeps the human
  platform operator alone (release 1, A6; TEC-4, TEC-16 (2)). `platform-operator`
  is created with NO workspace membership and an unusable password - or kept
  as it is, password included; `--reset-passwords` makes its password unusable -
  and an account of that name that exists with another actor kind or holds any
  membership is refused, changing nothing. When it is not an operator already,
  it is granted by the application's own command, `manage grant_operator
  --username platform-operator --reason-file <RAM-only file> --by <person>
  --authorization-ref <declaration>@<commit> --review-by <date>` (C3): `--by`
  and `--review-by` are then required, `--by` names a person, never a role. An
  account any of whose grants was ever revoked is never granted again unless the
  run passes `--regrant <name>` and the committed declaration approves it
  (ADM-10 3(i)) with one line: `Approved: --regrant <name>` (the words may be
  in backticks), the whole of a line that starts with it, outside any fenced
  block or HTML comment - and names `--regrant <name>` nowhere else
  (refutation round 2, installer-3: a list of re-grants NOT approved held the
  words alone on lines of their own, which round 1 read as approval).
  Nothing else approves: the words alone on a line, inside a sentence ("do
  not --regrant ali"), a list item, a quote, an indented or fenced block, a
  comment; and another name that starts with them (`--regrant alice` for
  `ali`) is not even a mention. It is read back: an active human operator
  with no membership.
  An account created or reset then gets a single-use setup code: generated by
  the installer, handed to `manage issue_enrolment` as a RAM-only `--code-file`
  (only its sha256 reaches the database), committed root-only to
  `/etc/cpt-studio/operator-enrolment.json` (root 0600) through the root helper,
  never printed, logged or put in a receipt. The operator opens
  admin.quillmd.com within 30 minutes and sets a password and the first security
  key with it (B2, B4). No operator password is written to a file; today's
  `operator-credentials.json` and `ops-agent`'s login file are left untouched
  and reported (deleting either is the owner's decision, D11, D12). On the
  current host the existing operator keeps its password until its first
  sign-in after release 1, where it must change it; its key is enrolled with a
  setup code from `manage issue-enrolment`.
- **manage** (release 1, A6) runs one allow-listed ruled act in a one-shot of
  the installed image, through the door, once `manage migrate --check` passes:
  `revoke-operator` and `clear-signin-failures` (`--username --reason-file
  --by`), `grant-operator` (also `--review-by`; the declaration is passed as
  `--authorization-ref <declaration>@<commit>`; the account is read first, and
  one any of whose grants was ever revoked is refused unless the run passes
  `--regrant <name>` and the declaration approves it with the line
  `Approved: --regrant <name>` - as in **operators** - and the command is then
  told `--regrant`), `issue-enrolment` and
  `reset-second-factor` (`--username --reason-file --by`; each issues a new
  setup code, kept as **operators** keeps one), `require-password-change`
  (`--username` or `--all-human-accounts`, which the command is given as its
  `--all`, D22; never an automated account),
  `dispose` and `export-workspace` (below: **Disposal, returns and the
  ledger**). The reason file must be a short UTF-8 text file; it reaches the
  command as a RAM-only file under `/dev/shm` - 0600, in a 0700 folder with an
  unguessable name; a disposal or an export runs as the application's uid, so
  the root helper hands that folder to it for the act and wipes it afterwards -
  and the receipt keeps its sha256 and size, never its text. It is read through
  one descriptor that never follows a link, at most 4,096 bytes counted as read,
  and a file whose contents differ from the size it reports (`/proc`, `/sys`) is
  refused. Once the act has run, its record is always kept (refutation round 1,
  phileak-1 and dataloss-3: a destruction's certificate that repeated the plan's
  reason was discarded with its log): every occurrence of the setup code, the
  application's own secret values and the reason's text (whole, or any line of
  12 characters or more, as written or as JSON writes it inside a string) is
  replaced by `[redacted by the installer]` before the log and
  the receipt are written, and the receipt's `redacted` counts them by kind
  (`secret`, `reason`), never a value; the summary says so, and a secret the
  command printed is a FINDING. A setup code it printed is never kept (the
  act's receipt fails, and the act runs again for a new code), and `provision`
  never hands over a password it printed (the credentials files are
  discarded; `--reset-passwords` sets new ones). Nor does what follows the act
  ever take its record away: when its RAM folder's wipe or an export's seal
  fails, the receipt fails with the act's record (its exit, its log, its
  output) and says what did not finish, and a signal or a Ctrl-C there is
  recorded beside it (a setup code is then not kept). Nor does the one-shot's
  own leftover check. After the act's own exit `docker run --rm` has removed
  its container (the CLI waits for the removal), and it is not looked for
  (refutation round 2, installer-1); after the CLI's own failure (125: the
  removal failed, or its wait on the daemon broke) or a CLI killed by a
  signal, the container may be left - running on, and holding the secrets of
  its environment - so it is looked for, sent its own SIGTERM with 10 s to
  record, and removed (refutation round 3, installer-3). No daemon error or
  signal in that check takes the answer away: a signal is raised once the
  one-shot is removed, with the act's record. A one-shot whose run timed out is first sent its own
  SIGTERM, with 10 s to record (a disposal then records its run 'failed'),
  then removed; one interrupted is removed at once, since the door's SIGKILL
  follows its SIGTERM by 15 s, which the RAM folder's wipe and the receipt
  need. The receipt keeps the
  command's stdout (ids and counts) and its log. A reason must be in words, so
  that its redaction can never touch an id or a count: its text 12 characters
  or more that are not white space, and neither the text nor any line of 12
  characters or more made of ids, links and numbers alone. A part of it (a run
  between white space) is one of those when it is written in ASCII and holds a
  digit, a `/`, `\` or `@`, or a `.`, `_` or `=` between two letters or digits,
  or is 12 or more hexadecimal letters; a word, in any script, never is, so a
  heading, a label, a line of one word, a reason of two words and one written
  without spaces all run (refutation round 3, installer-2: they were refused).
  A ticket number alone, or a line that is an id, a link or a number
  alone, is refused before the act (refutation round 2, installer-5: a reason
  `4521` was redacted inside a plan id's group, which `--plan-id` then needs,
  and inside a byte count). Nothing that is not on the list
  runs. An act holds the receipts' lock for its whole run, as every phase does,
  so no install, `switch-back` or `rollback-app` can start while it runs (and
  none of them can be running when it starts). An act's own time ends 300 s
  before the door's ceiling
  (`RULED_ACT_MAX_SECS`), which leaves its cleanup, the export's seal and the
  receipt their time. A SIGTERM - the door's kill at its ceiling - or a SIGHUP
  stops any phase where it is: its RAM files are wiped, its one-shot removed,
  its undo run, and its receipt says `interrupted` (exit 143, or 129). One that
  lands while the RAM files are being wiped - or a Ctrl-C there - is acted on
  once the wipe has finished (refutation round 1, installer-3: it had stopped
  the wipe and left the reason in `/dev/shm`). The root helper's wipe of a
  folder handed to the application's uid runs in a session of its own, so a
  signal sent to the installer's whole process group never reaches the
  docker CLI running it - the door's ceiling is `timeout`, which signals the
  group, its SIGKILL too (refutation round 2, installer-4: that CLI died
  before the wipe began and left the reason). A wipe that fails while a
  signal is held is said beside the interrupt (`details.after_act`), with the
  folder it may leave. Only a SIGKILL (the door's, 15 s after its SIGTERM, or
  a `kill -9`) can still leave a `/dev/shm/cpt-studio-<word>-<32 hex>`
  folder - one that lands before the root helper's wipe has begun, during the
  installer's own wipe of a folder it never handed over, or on the wipe's own
  CLI - which holds the act's RAM-only
  files (the reason, a code): overwrite and remove it as root (the root-via-
  docker path), never read it. Every
  phase's receipt is written before its journal (A13), so an interrupt while the
  journal is written never costs a finished phase its receipt.
- **http-vhost / https-vhost / ingress / ingress-rollback / rollback-vhost**
  validate with `sudo -n /usr/sbin/nginx -t`, refuse any new nginx warning,
  reload with `sudo -n /usr/bin/systemctl reload nginx`, then probe with bounded
  retries (reloads are asynchronous). Any failed check restores the exact
  previous file state - both files for `ingress` and `ingress-rollback`, in the
  safe order - validates and reloads again. Co-tenant routing and app health
  must equal the preflight baseline. A stage this installer writes is the HTTP
  stage or the HTTPS stage for either web port (`cert`, `rollback-vhost` and
  `verify` accept any of the three). Since release 2 every HTTPS stage names
  admin.quillmd.com, so one is written only by `ingress` (the first, with the
  `quillmd` vhost's edit) or in place over another that names admin
  (`https-vhost`, the blue/green switch); `http-vhost` and `rollback-vhost` run
  in the before state alone. `https-vhost` renders the HTTPS stage for the port
  the running `cpt-studio-web` publishes, and refuses an HTTPS stage for the
  other port, the HTTP stage and an earlier stage that names no admin host
  (both `ingress`'s). Release 1's stage (A1-A4, B6) is published this way before
  `app`, and works with the previous revision's web behind it. Its `verify`
  also probes the TLS policy (A4): the host's `openssl s_client` against
  127.0.0.1:443 with each name as the server name must negotiate an AES-GCM
  suite by default, and every other family it offers alone (TLS 1.3 ChaCha20;
  TLS 1.2 ChaCha20, ARIA-GCM, Camellia and AES-CBC; TLS 1.0 and 1.1) must end in
  the server's alert - a client that could not offer it is never counted as
  refused. The result is recorded; a finding never undoes the publish (D27).
- **cert** requires exactly one existing ACME account and passes it with
  `--account`; certbot gets no `--agree-tos` or e-mail, so it cannot register
  one, and no `--expand`. One order for cpt.quillmd.com and admin.quillmd.com
  under `--cert-name cpt-studio`, webroot `/var/www/certbot` for both. On a
  fresh host it needs this revision's `http-vhost` receipt; on a served site
  none: `quillmd-cpt` must be the stage the running web is served through
  (recorded by a successful receipt here, proxying to the port that web
  publishes). DNS (A `147.189.172.8` only) and the HTTP-01 route (an ACME
  probe) are checked for both names before certbot runs. Other lineages'
  renewal configs must be byte-identical afterwards; neither CPT lineage
  (`cpt.quillmd.com`, `cpt-studio`) counts as another.
- **verify** compares everything with the preflight receipt and checks the
  deployed containers' hardening and the HTTPS headers. `quillmd-cpt` must be
  this revision's HTTPS stage for the port the running web publishes (it
  alternates) and the `quillmd` vhost exactly the state that stage couples
  (after); a request for either host on a connection opened for
  app.quillmd.com is answered 421 Misdirected Request, one for either host on
  the other's connection is served, admin.quillmd.com is judged by the
  own-host checks, and both HTTP-01 routes are proven. Nothing an `app` parks
  or starts (`cpt-studio-web-next`,
  `*-previous`) may be left beside the pair. The containers'
  check (also run as each starts in `app`) includes their bind mounts: the web
  holds none, and the worker only the credentials files, read-only, at their
  worker paths; and, since release 1, no swap and no core dump for any of them.
  Release 1 also reads: the database's own cgroup (no swap) and its two log
  settings (`SHOW`, through `docker exec`: verify starts no one-shot); the
  converter of this revision, sealed and healthy; and the TLS policy (A4) -
  recorded as findings, never a failure (D27). `/health/` is judged by the
  revision it expects (B7): through nginx a revision whose health view answers
  the digest - read from its tree, as the converter is - must answer
  `release_digest` alone (an answer with its release means B7 is not in force,
  and is refused), and an older revision - the pair before release 1, after a
  switch-back - its release; the web's own port answers the release either way.
  After a switch-back to that pair, `verify --revision <its revision>` passes.
  Release 1's own `verify_login.py`, `scan_customer.py` and walk do not, and
  are not meant to (refutation round 2, switchback-1; round 1 recorded it as
  rollback-4): each sends release 1's client version (the build of
  2026-11-24; this release's tools send `X-CPT-Studio-Client:
  customer-2026-11-26`), which the server pins (specification 3.6), so that
  pair's web answers `/api/session` and `/api/encounters` with `409`
  (`client_outdated`); and release 1's shared contract
  (`ops/verification/customer-contract.json`) lists keys that pair's session
  does not have (`can_manage_team`). Each fails closed - a fail, never a pass:
  `verify_login.py` on `session.read` and every check read from it,
  `scan_customer.py` on `session.contract` and `customer.list_contract`, the
  walk with `refusing to upload: GET /api/session served no object` (its
  `--release <that revision>` judges only `/health/`, reading B7 from that
  tree). Run that pair's own tools instead, from a checkout of its revision
  (for example `git worktree add <dir> <its revision>`): its
  `ops/verify_login.py` and `ops/scan_customer.py` send its own client version
  and read its own contract, and pass against it (measured in round 2 against
  the pair before release 1 serving a database release 1 had migrated). Its
  `ops/walk.cjs` speaks its version too but has no `--release` (it predates B7)
  and reads that revision's own operator credentials file, which release 1
  writes none of; it was not run against that pair, so read what it reports
  as that revision's own walk. Every one of these tools reads the cookie names
  the server sets - the plain ones before release 1, the `__Host-` ones from
  it - never the scheme's.

## The admin host and the coupling invariant (D396, release 2)

admin.quillmd.com - the operator console's own host (owner direction
2026-11-23, DECISIONS D396) - is served by the same `quillmd-cpt` server block
as cpt.quillmd.com: one certificate (the `cpt-studio` lineage, which names
exactly the two hosts), one upstream (the single `proxy_pass` the blue/green
switch moves), and `Host $host` behind a guard that closes any other Host (444)
and answers a TLS server name that is neither name with 421 Misdirected
Request: a browser that reused a connection opened for another QuillMD name -
whose certificate also covers admin.quillmd.com - retries on a fresh
connection, where a 444 would have ended in an error page; a connection opened
for either of the two serves both. The application has answered the admin host
since release 1 (a revision whose tree holds `cptstudio/urls_admin.py` and
`studio/hosts.py`). admin.quillmd.com's :80 stays the `quillmd` vhost's
(QuillMD's file, its line 13): it answers admin's HTTP-01 challenge for both
lineages that name admin, QuillMD's `quillmd.com` and `cpt-studio`.

**The coupling invariant.** nginx loads `quillmd` before `quillmd-cpt`; a name
both claim stays the first one's (with a `conflicting server name` warning),
and a name neither claims falls to a co-tenant's default server and
certificate. So the two files are coupled, and every state but two refuses.
`quillmd-cpt` is read as nginx loads it: without its `sites-enabled` link it
claims nothing, and behind a link that is not the installer's own (another
target, or not a link) it cannot be told, which refuses like any other
uncoupled state (the R2 check, round R2-1).

| state | `quillmd` vhost | `quillmd-cpt` | admin.quillmd.com :443 |
|---|---|---|---|
| before | `QUILLMD_VHOST_BEFORE` (`e9aa049d…`, the file as QuillMD keeps it) | names no admin host on 443, or is absent | QuillMD's Caddy notice |
| after | `QUILLMD_VHOST_AFTER` (`b3ab6602…`): line 26 is `server_name quillmd.com www.quillmd.com;` | names admin.quillmd.com on 443 | CPT Studio |
| both | before | names admin | still Caddy's (nginx keeps the `quillmd` vhost's): the only state between the two renames of the two-file write, never left by a phase |
| anything else | | | refused by every phase and by the root helper |

`preflight` takes before or after as a baseline and refuses any other;
`verify` requires the state this revision's stage couples (after); the root
helper reads it before every operation - refusing, before writing, a
`quillmd-cpt` the `quillmd` vhost would not be coupled with - and after it,
against the `quillmd` digest it read at the start. So `rollback-vhost` and
`http-vhost` refuse in the after state (run `ingress-rollback` first), a
blue/green switch moves between two stages that both name admin, and nothing
but `ingress` and `ingress-rollback` writes the `quillmd` vhost - only between
its two pinned states: line 26 replaced whole
(`    server_name quillmd.com www.quillmd.com admin.quillmd.com;` and
`    server_name quillmd.com www.quillmd.com;`), that full line asserted once at
line 26, every other line - line 13, admin's HTTP-01 route, among them -
byte-identical, and the result's sha256 the pinned value, all before anything
is written. The after state's pin was derived from the live file, read only,
by exactly that replacement.

**The two-file write.** One root-helper operation holds both files. `couple`
(`ingress`) checks that the `quillmd` vhost is the before state, its new
content the after state and `quillmd-cpt` the stage expected, stages and
fsyncs both files, then renames `quillmd-cpt` FIRST and the `quillmd` vhost
SECOND; `decouple` (`ingress-rollback`, and the undo of `couple`) renames the
`quillmd` vhost FIRST and `quillmd-cpt` SECOND. Either way the only state
between the renames is both naming admin, which keeps admin on Caddy: no
moment - and no state a stopped helper, or anyone's reload in between (the
renewal deploy hook's, a co-tenant's), could publish - leaves admin claimed by
nothing. Each operation accepts the other's partial state as its start and
clears a staged file a stopped operation left, so an undo completes from
wherever its operation stopped. `nginx -t` runs once both files are written (no
new warning), then one reload, and both files' sha256 are read back.

**ingress** runs after `cert`, while release 1 or later serves. It refuses,
writing nothing, unless: the state is before; `quillmd-cpt` is the stage the
running web is served through - an HTTPS stage a successful receipt in this
receipts directory recorded (or this revision renders), proxying to the port
that web publishes, or on a fresh host this revision's HTTP stage after its
`http-vhost`; the running web serves the admin host - its revision is release 1
or later, and on its loopback port it answers `/api/session` 404, an anonymous
GET and HEAD of `/` 302 to exactly `/login/`, and the operator sign-in 200
naming static files that answer 200, so the application answers admin from the
reload on (no window); the `cpt-studio` lineage is present; and co-tenant
routing and app.quillmd.com answer as the preflight baseline recorded. It
writes this revision's HTTPS stage for that port and the `quillmd` vhost's
after state (`couple`), then verifies through the public path - the own-host
checks below for the running web's revision, both HTTP-01 routes (cpt's through
`quillmd-cpt`'s :80, admin's through the `quillmd` vhost's), the
`http://cpt.quillmd.com/` redirect, co-tenant routing and app.quillmd.com - and
reads both files back; any failure writes both back (`decouple`). Its receipt
records the stage it replaced byte for byte (`from`: sha256, kind, port, the
revision whose receipt recorded it, base64), the stage it wrote
(`vhost_sha256`), both `quillmd` pins and the web it found serving. Run again
on the after state with this revision's stage live, it verifies and writes
nothing (`moved: false`).

**ingress-rollback** gives admin.quillmd.com's :443 back to the `quillmd`
vhost and `quillmd-cpt` the stage that the newest successful `ingress` of this
revision that moved admin replaced. When the newest move was another
revision's and admin is still moved, it refuses and names that revision and
the way there: switch back revision by revision, newest first, each with its
own installer, until the web that ingress found serves, then that revision's
`ingress-rollback` (the R2 check, round R2-2; the R2 refutation, round 1). It
runs only while the web that ingress found serving - the revision its receipt
recorded - serves again: before `app`, or after a `switch-back` to that
revision, on either port (**ingress-rollback's guards**). Otherwise the stage it
gives back would send cpt.quillmd.com to a web that does not serve (the old web
is removed once `app` succeeds), so it refuses and names `switch-back` first. It also needs the after state with this revision's
HTTPS stage for that port live, and co-tenant routing as the baseline
recorded. Before it writes anything it completes a TLS handshake with QuillMD's
Caddy (`127.0.0.1:8443`, SNI admin.quillmd.com) and reads the notice it answers
(a Caddy that lost its certificates would leave admin a raw 502). It writes the
`quillmd` vhost's before state first, then the saved stage (`decouple`), and
verifies: cpt.quillmd.com/health/ answers that web's revision (a fresh host's
saved HTTP stage: cpt's :443 routes like an unknown host again),
admin.quillmd.com through nginx answers Caddy's notice (the same status and
body) with the `quillmd.com` lineage's certificate, co-tenant routing is
unchanged, and both files read back; any failure writes both forward again
(`couple`). Run again in the state it left, it verifies and writes nothing. The
QuillMD-side checks the move changed to expect CPT Studio's answer on admin -
`scripts/check-cotenants.sh` (its admin row, narrowed to the console's 302 on 2026-11-23),
`scripts/verify-post-reboot.sh` and `tests/automated/monitoring/uptime-check.sh`
(admin's row 302) - are QuillMD's: revert them to Caddy's notice in the same
step. (`rebuild/ops/owner_normal_origin.py` also expects the notice, but it is a
spent one-time act: its precondition, line 26 naming app.quillmd.com, no longer
holds, so it refuses before any write; it is left as it is.)

**The write-ahead intent.** Before its two-file write, `ingress` writes
`intent-ingress-<stamp>.json` into the receipts directory (0600, fsynced): the
stage it is about to replace, byte for byte, its sha, the quillmd pins and the
web it found. A run killed outright between the write and its receipt (an OOM
kill, a host reset, the door's ceiling: no undo runs, no receipt is written)
therefore still leaves the way back on disk. Run `ingress` again: finding the
after state with this revision's stage and an intent no recorded move followed,
it completes the move exactly as the move runs - co-tenant routing checked
first, nginx tested against the warnings the intent recorded before the write,
reloaded (nginx may still run what it loaded before the kill), verified, and
written back to the intent's stage on any failure - and records it with the
intent's stage and the web the intent found (`recovered`). Only a recorded move
resolves an intent; whether one matters is read from the files (the coupling
not before). Until it is recorded, `app`, `https-vhost`, `switch-back` and
`rollback-app` refuse and name the rerun, and so does `ingress-rollback`. If the
stage moved since anyway (a phase run by hand), the rerun refuses and names the
way: switch back until the web the intent found serves with this revision's
stage for its port, then rerun `ingress`. A torn intent file changed nothing
(it is written and fsynced before either file changes) and is skipped.

**ingress-rollback's guards** (the R2 refutation, round 1). It runs only while
the web the ingress found serving serves again, on either port: on the port the
saved stage proxies to it gives back the saved stage byte for byte; on the other
(an even number of `app` runs since the ingress) it gives back that revision's
own stage rendered for the port it serves on, and only when this installer
renders the saved stage byte for byte. It refuses when the stage to give back
loads certificate files Let's Encrypt's live directory does not hold (the
saved stage loads the `cpt.quillmd.com` lineage: re-issue it by hand - this
installer's cert phase orders the `cpt-studio` lineage alone), and when
QuillMD's Caddy answers admin.quillmd.com with anything but a deliberate state -
its maintenance notice (503 with QuillMD's sentence) or a 2xx or 3xx answer -
so the way back never serves an error. It checks in this order: a coupling
neither before nor after refuses (recover it first: no switch-back or rerun can
pass meanwhile); an unrecorded ingress of this revision names the rerun; a move
of another revision names that way back. Run again in the state it left, it
reloads nginx onto the files (a run killed before its reload left nginx on the
after state) and verifies.

**The own-host checks.** admin.quillmd.com's :443 is the installer's own host:
`routing_diff` leaves out the `https://admin.quillmd.com:443` keys (its :80
stays a co-tenant route - QuillMD's block - watched like any other), and
`scripts/check-cotenants.sh` is told not to judge it:
`CPT_INSTALLER_SKIP_HOSTS=admin.quillmd.com`, the exact host, set by the
installer itself (it never hands the script the operator's environment); the
script counts its discrimination floor from the rows it judged, and a checkout
whose script judged the host anyway (a row naming it with two codes) fails
`preflight`. The installer judges the host positively instead - in `ingress`,
`https-vhost`, every blue/green switch's verification and `verify`, through
the public path: served with the `cpt-studio` certificate (exactly the two
names, the certificate cpt.quillmd.com is served with) and the four policy
headers once each; then, for a web whose revision serves the admin host,
`/health/` for that revision, `/api/session` 404 (the doctors' urlconf answers
401), an anonymous GET and HEAD of `/` 302 to exactly `/login/` (the doctors'
urlconf: `/login/?next=/`), and the operator sign-in 200 naming static files
that answer 200. A request for either host on a connection opened for
app.quillmd.com is answered 421, and one for either host on a connection opened
for the other is served. Before a switch the incoming web gives the same admin
answers on its loopback port (`smoke_web`). All revision-aware: a revision
before release 1 answers the admin host with Django's 400 (DisallowedHost),
which is recorded and never a failure, and a `switch-back` to one says so in its
summary. A revision the act checkout cannot read is refused, never taken for one
before release 1 (that would leave the admin answers unjudged; the R2 check,
round R2-3): fetch it into the checkout, then rerun. The operators phase writes the console's address as
`https://admin.quillmd.com/ops/` (`operator_url`) and keeps
`https://cpt.quillmd.com/ops/` (`operator_url_cpt`) while both hosts serve it.

**The act's order (release 2).** `preflight`, `image`, `cert` (the
`cpt-studio` lineage; ingress unchanged), `ingress` (both files for the live
port; the running web is release 1 or later and already answers admin, so
there is no window), `preflight` again (the post-ingress baseline `app` and
`verify` read), the database check, `app` (blue/green: the live stage is now
this revision's rendering), `verify`, the post-checks, the live check on both
hosts. `verify` accepts the coupled state whichever side of the ingress its
preflight was taken on: `sites-available` must be the baseline plus
`quillmd-cpt` - this revision's stage for the live port - with the `quillmd`
vhost exactly the after state, and neither CPT lineage counts as another.

## Reinstalling a new revision

Commit a declaration naming the new revision, then run `preflight`, `image`,
`app`, `passages`, `license-note`, `verify`. On a served site `app` is the
blue/green switch: the site stays up, the web moves to the other port, and the
vhost's sha256 changes by its `proxy_pass` line (declarations no longer list
`quillmd-cpt` under "must not change"; they name the expected sha256 instead).
`app` needs the preflight receipt of this install in the receipts directory. `secrets`, `db`, `reference`,
`passages`, `license-note` and `provision` are idempotent or refuse rather than
repeat. A harness participant
credentials source placed since the last `secrets` is copied by running
`secrets` again (the three-file set reads `present`) before `app`. If `deploy/nginx/` changed between the revisions,
`app` refuses the blue/green switch (it would change more than the upstream)
and `verify` reports the vhost as different. Under the coupling invariant the
republish never removes `quillmd-cpt` (that would leave admin.quillmd.com's
:443 claimed by nothing, and `rollback-vhost` refuses it): run `cert` (a no-op
for a lineage not yet due for renewal; it records the receipt `https-vhost`
requires), then `https-vhost` under the new declaration, which replaces in
place the earlier revision's HTTPS stage - recorded by a successful receipt
here, proxying to the port the running web publishes, and naming
admin.quillmd.com as every stage since release 2 does - with this revision's
for that port: the `quillmd` vhost stays the after state, one file is
replaced in one reload, and both hosts are served throughout. Then `app`
switches blue/green. Over an earlier stage that names no admin host (release
1 and before) `https-vhost` refuses and names `ingress`, which moves admin in
the same act. A template change that would stop naming admin.quillmd.com
cannot be republished so (see **Known limits**).
`rollback-vhost` removes a stage an earlier successful vhost receipt recorded
(its digest), and a failed removal is restored to exactly the bytes that were
live. A reinstall must therefore use the receipts directory of the install whose
stage is live (or copy its vhost receipts into the new one): without the receipt,
the stage is not provably this installer's and `rollback-vhost` refuses. `verify` compares the other
Let's Encrypt lineages only; this domain's own lineage may already be in the
reinstall's preflight baseline.

## Switching back (post-success rollback without interruption)

Run `preflight` again right before `switch-back` (as before any `app`): the
switch is verified against that receipt's baseline - co-tenant routing and
`app.quillmd.com /health/`, whose release changes on every deploy of that
co-tenant - and `switch-back` refuses, starting and stopping nothing, while they
no longer answer as it recorded.

**No way back to a revision without release 1's disposal while anything was
disposed** (refutation round 1, rollback-1 and rollback-2). Release 1's closed
practices (`dispose --close`) and destroyed documents (a tombstone: the row
kept, title emptied, its PHI-free decision trail kept) are rows only its own
code reads. A revision whose tree has no `studio/disposal.py` - every revision
before release 1 - would list and count each tombstone again, with its kept
activity on its page and its console, and take uploads into a closed practice
and send them for coding. So `switch-back` to such a revision refuses, starting
and stopping nothing, while any practice is closed or any document destroyed
(read in this revision's image, counts only; read again at B4 before anything
is closed), and says how many of each. `rollback-app` refuses the same way
before it returns such an older web (the S4 keep layout), and before it removes
this revision's pair when the parked pair it leaves is such a revision or no
parked pair says which revision runs next. Neither a closure nor a destruction
is ever undone, so once the first one has run the way back is gone for good:
the owner's path is a fix forward (a revision with disposal, by its `app`). A
`switch-back` to a revision that has disposal is not affected.

`--phase switch-back --provider-mode <mode> [--astra-mode …] [--fable-mode …]
[--interpreter-mode …] [--coding-mode …] [--authorization-ref …]` runs under this
revision's declaration and installer
(an older installer cannot switch: `check_tree` binds a phase to its own
revision) and returns to the pair this revision's last successful `app`
replaced - its receipt's `replaced`, whose image is still present - with the
modes given (the previous pair's, as its own `app` was given them; the
credentials files are checked with the previous image's own loaders). Corti
(`--provider-mode`, required), the participants and the interpreter exist only
in a pair before the Fable coding build (DECISIONS D351-D353), which these
arguments start as its own `app` started it: `--interpreter-mode` is `live`,
`replay` - nothing sent, answered only from a recording in the image, which
ships no Fable recording, so every reading fails unsent - or `disabled` (the
default); `--coding-mode` (`live` or `disabled`, the default) is for a previous
pair of the Fable coding build - a pair before it reads no coding mode, and its
image fails the coder's loader check live. When that
`app` replaced this same revision - a same-revision re-run: a coding-mode
switch, or the re-run a failed `app`'s receipt asks
for once its parked pair is removed - the pair is read instead from the newest
`app` receipt of this revision written since its last successful `switch-back`
that names another revision whose image is still present (DECISIONS D83): a
successful one, or one that failed once its switch had finished (only such a
receipt records the web it replaced: its recompute or the removal of the parked
pair failed after the old web was parked). With none, there
is nothing to switch back to: an `app` whose receipt records no replaced web
(the S4 keep layout, an S5 failure, an undo) leaves none, so after the S4 keep
layout's recovery the way back is `rollback-app`. It refuses, starting
nothing, unless this revision's web serves the site through
its HTTPS stage, and while this revision recorded what an older revision would
act on, or show, wrongly (`rollback-app`'s check: **Reinstalling an older
revision**). For a switch-back that check is read against the revision it
returns to (DECISIONS D51): a reason that revision reads is no hazard to it -
participants and second reviews when its worker runs their stages, a member's
answer and a chosen modifier when its own models read them - and an encounter
with no record created since this revision's pair could last have served in that
pair's place holds only what that pair left there. That time is the earliest `started_at` of the `app`
receipt the pair is read from and of every `app` receipt of this revision
written after this revision's last successful `switch-back` to that pair,
whatever it replaced and however it ended (DECISIONS D59, D65, D82, D95 and
D110): a successful one, over that pair or another; one that failed once its
switch had finished; one undone after it parked a role; a swap undone after its
web had served, whose receipt records nothing it replaced; one interrupted, or
refused before anything changed. Most of them may have put this revision's pair
in front of traffic without the receipt saying so (one refused before anything
changed did not, and says so), and the rule asks none of them whether it
served, so none is left out: an earlier time names more encounters, which only
refuses more. A receipt
whose order cannot be told from its name is counted too. It never reaches
across that `switch-back`: what the pair wrote while it served again after it,
until this revision's next `app` began, is its own. A `switch-back` that did
not complete, one to another revision and another revision's are no such
bound. When the receipt the pair is read from is itself older than that
`switch-back` (no successful `app` has replaced that pair since: a later one
failed, or replaced another revision), the time is that `switch-back`'s own
`started_at` (the earliest of it and of what the `app` receipts written after
it record). Never the current containers' creation: a later `app` of this same
revision that installed a pair and then failed made those, and what this
revision wrote under its earlier pair is not the previous revision's own (the
receipt's `touched_since` says which time was read). A reviewer's
reinstatement on a new-path assessment is always named
(`reinstatement`: no older overlay adds the hold it brings back), and stays
named once the reinstated code is approved - the normal end of a
reinstatement: revoke that code's decision on this revision's web first. Then,
without ever stopping the serving web first: **B2** the
previous image's web starts as `cpt-studio-web-next` on the idle port and must
answer `/health/` with ITS revision and serve its pages; **B3** this revision's
worker is parked; **B4** every coding job still queued or running is closed
as its own stage would have ended it (failed, its round stopped, when nothing it
sent is unsettled; unknown, its round failed as unknown, when its request was in
flight - that request recorded unknown - or a send of it was left unknown and
not reconciled; failed, its round failed with that send's kind, when a send of
it failed: (a) below) and every open
stage of another kind the previous worker does not run is failed (as
`rollback-app` closes them; let the queue drain first: **Switching back to the
pipeline before the Fable coding build**, below), the switch-back refusing to
go on while the close names a record, and the previous image derives the stored
state of every encounter this revision coded with its own code (the put-back) -
and before that close, the baseline and this revision's records are read
again, so nothing is closed for a switch that cannot pass or would refuse on
what that read finds (a request the close itself finds in flight is recorded
unknown, and that record still refuses the switch-back after the close; the
receipt then says what the close closed, each way above) - and, when the
previous revision is before release 1's session policy, every session is ended
as at `app`'s S2 (`sessions.ended_at_install`; the receipt's `sessions_ended`):
the previous web reads none of this revision's cookies, and a session of its
own left in a browser nobody used meanwhile would be valid again;
**B5** the upstream is switched to the idle port (`/health/` = the previous
revision; a reload of the switched file that was asked for and then failed is
treated as applied, as in `app`: nginx is reloaded with this revision's vhost
again and must be proven to run it before the previous web is drained and
removed, and both webs are left running otherwise); **B6** this revision's web
is drained, stopped and parked;
**B7** the close runs again for what this revision's web started between B4 and
the end of its drain (a coding job a member queued there; a stage a member
started on the previous web in that window is of a kind the previous worker
runs, and is left to it), what this revision coded and does not carry back is
counted again (the receipt's `not_carried_back`, B4's count kept as
`not_carried_back_at_b4`; read before the hold below, so a receipt that stops
here carries it too), the states are put back again, and the previous worker is
held while the close names a record (an unknown outcome, or a stage it cannot
run still open: `app` again comes back to this revision); **B8** the previous
worker starts; **B9** this
revision's parked pair is removed (its image is kept), each log first kept ids
only (A13). The previous pair serves by then, so a copy (or a removal) that fails
at B9 is a recorded finding, never a failed switch-back: the receipt's
`parked_left` names the pair left parked and why, its summary says FINDING, and
the next `app` keeps their logs, then removes them, before it plans its switch
(only the containers that receipt names; any other `*-previous` still refuses).
Before B5 any failure
resumes this revision's pair (its worker started again, its list states
recomputed with its own derivation, the previous web drained when it took
traffic and removed); from B5 on the previous web serves and the receipt says
what is left. A B4 close that was started and gave no answer (a Ctrl-C, or the
180 s timeout while it recomputes states after it has committed) may have
closed this revision's open stages: the receipt says so, never that nothing
was closed, and says that it set no member's details back (this revision's
close changes none). The S4 undo, `rollback-app` (in the keep layout and
outside it) and the swap say the same of a close of theirs that raised or was
interrupted (DECISIONS D247, F4); a `rollback-app` whose database refused
before its close started says the close was not started, and that nothing was
closed or set back. The availability record runs from B2 to the end.
To come back to this revision, run `app` again.

Since release 2 of the admin move the previous pair is judged on
admin.quillmd.com too when its revision serves the admin host (release 1 and
later): B2's smoke and B5's verification ask its admin answers. A previous
revision before release 1 answers the admin host 400 - recorded, never a
failure - and the summary says so: admin.quillmd.com answers that 400 until
`ingress-rollback` gives admin back to the `quillmd` vhost (which needs the web
its `ingress` found serving).

### Switching back to the pipeline before the Fable coding build

The pair a `switch-back` (or the failure path of `app`) returns to from this
revision is e426c747c7b7's - the pipeline before the Fable coding build. Its
worker has no coding stage, its web reads none of migration 0016's four tables,
and its state derivation knows none of this revision's state names. What the
undo does about each, in this revision's image unless said otherwise:

- **(a) Coding jobs are closed before the earlier worker starts.** The close
  (`CLOSE_STAGES`, B4 and again at B7, once this revision's web is drained; the
  same close in `rollback-app` and the app phase's own undos) takes every job of
  kind `code` still queued or running - the earlier worker claims a job of any
  kind and would end on `STAGES['code']` - and closes it as this revision's own
  worker closes a stage it stopped (`studio.jobs.mark_stale`'s rule,
  `studio.jobs.abandoned_outcome`): for one with nothing it sent unsettled the
  job is **failed** with the installer's note and its round **cancelled**, so
  the round reads stopped and a Resume continues it (reusing every read it
  already paid for) whenever this revision serves again; one whose send was in
  flight has that request recorded **unknown** (sent, when it called a vendor;
  never sent again), the job unknown and its round failed as unknown, and so
  does one with a send left unknown earlier that no operator reconciled (its
  Resume and retry wait for the reconcile); one with a send that failed has its
  round failed with that send's own kind; a reservation never sent is recorded
  not sent, and so is any
  coding run still in flight whose round has no open job (an orphan its stage
  left). No coding job is left cancelled as its revision's latest stage (a
  member's Stop): the earlier revision counts such a job as a stage it cannot
  run, and its installer's `app` refuses on one, so it is failed with the note
  too, its round left stopped. The rollback rehearsal below found exactly that
  one on e426c747c7b7's own code. A stage of another
  kind the next worker does not run (only when the next worker cannot be asked:
  every kind but `COMMON_STAGE_KINDS`) is failed with the installer's note, as
  before. Nothing else is closed: this revision queues no stage but a coding
  job, so a stage of the earlier pipeline the earlier worker runs is left to it.
  Read after the close, a stage the next worker cannot run that is still open
  (a coding job a member queued on this revision's web after B4's close) is a
  record (`open_stage`) that holds the earlier worker until B7's close has
  taken it; `app` again comes back to this revision.
- **(b) No row of the four new tables is deleted; closed rounds are marked
  cancelled.** No undo removes a row of `CodingRound`, `CodingAnswer`,
  `CodeDecision` or `ExportArtifact`, or any other row. The close writes only
  the rounds it closes - a round with nothing it sent unsettled is marked
  cancelled (and its finish time set), one whose request was in flight or whose
  send is unknown is marked failed, its outcome unknown, and one whose send
  failed is marked failed with that send's kind, as (a) says and as this
  revision's own stale sweep marks it - together with the jobs and provider
  runs that were still open. Answers, code
  decisions, exports and every finished round are not written. The receipt's
  `not_carried_back` note says the same, and its close answer counts the rounds
  closed (`rounds`: cancelled, failed).
- **(c) The earlier pair derives the state of every encounter this revision
  coded, with its own code.** Their stored `Encounter.state` is this revision's
  derivation (`awaiting_answer`, `needs_review`, `ready` and `failed`, which the
  earlier code does not know, or `processing`, `stopped`, `reviewed` and
  `no_codes`, which it knows with another meaning). The close names them in its
  `relabel` - every encounter with a coding round, and every one whose earlier
  stage this revision's worker settled - and `put_back_states` runs
  `PUT_BACK_STATES` for them **in the earlier image**: its own
  `studio.review.refresh_state` (in an image of this design, `studio.state`).
  The receipt's `states_put_back` names each encounter whose state changed (as
  read, as derived). With no image to ask (`rollback-app` with no pair parked)
  nothing is put back (`put_back: false`): the revision installed next
  recomputes every stored state in its own `app` (every revision since 057a7d39
  does; 057a7d39 itself is no rollback this revision supports).
- **(d) Approvals and answers made in this revision are not carried back - an
  accepted loss of a rollback, declared before it.** The earlier revision reads
  none of the four tables, so it shows no code, answer, decision or export of
  this revision: an encounter of its own that a member had reviewed again here
  shows its earlier review, and one created here holds no reading the earlier
  revision made (it shows it by its own derivation and processes it only if the
  document is uploaded again there). The receipt's `not_carried_back`
  (`CODING_MADE`, read in this revision's image; also in the summary) counts the
  encounters coded (`created` here, and of the earlier review coded again), the
  rounds, the answers, the code decisions by action, the codes approved now and
  the exports. It never refuses: a count that cannot be read is said so. **The
  install declaration of a revision of this design must state this loss**
  (DECISIONS D351-D353 replace the pipeline; class b of the standing
  authority): after a switch-back the members redo on the earlier web the
  reviews they made here, and a switch-back that follows real use loses them
  from view (the rows stay, for this revision's next `app`).

**The rollback rehearsal (2026-11-20).** On a disposable database migrated to
0016, synthetic rows of this design - a coded encounter with a code approved,
one with a question open, one queued, one failed, one a member stopped - were
closed by this revision's `CLOSE_STAGES` with B4's parameters; then
e426c747c7b7's own tree (`git archive`, run with the same Python requirements)
ran this installer's `PUT_BACK_STATES` and `UNRUNNABLE_STAGES` and read each
encounter as its web reads it. Its `studio.review.refresh_state` derived every
encounter created here as `processing`, with nothing claimable and no Resume
offered (it never processes them: (d)); its own stage read first counted the
stopped coding job as a stage it cannot run - which is why the close now fails
it - and, once the close did, found none. Synthetic rows only; the database was
dropped. A rehearsal before an install runs the whole sequence on the test
instance with synthetic data only (RELEASE-1-SPEC 6.4): live is never restored
or copied for it (P08, TEC-8 (5)).

**What still refuses.** `undo_hazards` (`UNDO_HAZARDS_READ`) names one reason:
**unknown** - a coding run whose outcome is still unknown and not reconciled.
The earlier revision reads every unknown run of an encounter as an outcome to
reconcile on its own console, and its reconcile allows one new attempt by its
own rules (a paid Corti predict for an encounter of its own with a context),
for a request it never made; reconcile it on this revision's operator console
first. A switch-back reads it only on encounters with a record created since
this revision's pair (`touched_since`, `TOUCHED_SINCE_READ`, the four tables
included); `rollback-app` reads it everywhere. None of the earlier pipeline's
reasons (below) can be this revision's record: it writes no assessment,
proposal, clarification, decision, member's answer, context or event inventory.
`rollback-app` checks only what this revision recorded: a rollback past
e426c747c7b7 goes back through it (`switch-back`), whose own `rollback-app`
reads its records.

**Holds.** An authentication, permission, payment or quota refusal of a coding
send sets an `InterpreterHold` (the build specification, 3.3), released on this
revision's operator console. The earlier revision's interpreter reads the same
table: a hold this revision set also pauses its readings, which is right - it
names the same Anthropic account - and it is released there with `manage
interpreter_hold`.

### Which image runs each in-image script

Each script runs by `manage shell -c` in a one-shot container (`app_script`),
or as named. The forward install runs only this revision's image; an undo runs
this revision's image for everything it reads of this revision's records, and
the earlier image only for what that pair reads of its own.

| script | image | runs in | what the Fable coding build did |
|---|---|---|---|
| `INSTALL_COUNTS` | this revision's (new) | `app`, after migrate, before the switch | rewritten: encounters (and those coded), jobs by kind and state, provider runs by purpose and state, unknown and in-flight runs, the four tables, standing holds; never a refusal |
| `V1_ROWS` | this revision's | `app`, before the switch | kept (reads legacy rows only; models kept) |
| `UNRUNNABLE_STAGES` | this revision's, and the next worker's (`stage_kinds_of`) | `app`; every undo | body kept (every revision's `jobs.STAGES`); `app` records it and no longer refuses on it |
| `RECOMPUTE_STATES` | this revision's | `app` S6 and the swap; an undo that keeps this revision | rewritten: `studio.state.refresh` for encounters with a coding round, every other state left |
| `UNDO_HAZARDS_READ`, `TOUCHED_SINCE_READ` | this revision's | `switch-back`, `rollback-app`, the app undos | rewritten: `unknown` coding runs only; the four tables among the records touched |
| `CLOSE_STAGES` | this revision's (the revision undone) | B4 and B7, `rollback-app`, the app undos | rewritten: (a) above; its answer's `relabel` and `hazards` |
| `CODING_MADE` (was `INTERPRETATION_MADE`) | this revision's | every undo that hands the rows on | new: (d) above |
| `PUT_BACK_STATES` (was `RECOMPUTE_STATES` with encounters) | the next pair's (e426c747c7b7's) | B4 and B7, `rollback-app`, the app undos | new: (c) above, that image's own `studio.review.refresh_state` (`studio.state` in an image of this design) |
| `TARGET_MODEL_READS` | the previous pair's | `switch-back` | kept (every revision's `jobs` and `models`) |
| `CREDENTIALS_CHECK`, `PARTICIPANT_CREDENTIALS_CHECKS`, `INTERPRETER_CREDENTIALS_CHECK` | the previous pair's | `switch-back` with that mode live | kept: Corti, the participants and the interpreter exist only there; never run in this revision's image (`app` starts them disabled) |
| `CODING_CREDENTIALS_CHECK` | this revision's | `app --coding-mode live` | kept |
| `CONVERSION_GATE` | the image just built | `image` | new: the conversion gate |
| `LICENSE_NOTE_FIX`, `OPERATOR_ACCOUNTS`, `OPERATOR_CHECK` | this revision's | `license-note`, `operators` | kept |
| `INSTALLED_STATES`, `REAPPLY_REVERTED`, `UPDATE_PENDING` | - | - | removed: 057a7d39's derivation and design v2's update put-back need the earlier pipeline's modules, and this revision's close sets nothing back |

The ops tools: `ops/scan_customer.py` (this host; the shared contract and
denylist reader, which the Django suite's API tests load) was adapted to the
Fable coding build's routes. The download verifier, the D15 rollback runtime
test of the Gemini migration, the GI round-4 proof harness and the differential
"what changed" check read the earlier pipeline's records, exports and code and
were removed with their tests: the walk (`ops/walk.cjs`) scans every customer
API JSON response and header and the DOM text for the denylist (the downloads -
the PDF reports' wording and their answers - are `scan_customer.py`'s, which reads
them as the report prints them), holds every session, list and
encounter answer it or the page reads to `ops/verification/customer-contract.json`
(the same reading as `scan_customer.py`'s, `ops/test_walk_contract.py` holding the
two to each other), approves one line through the review dialog as the page draws
it - the page's request naming the round shown and the line - and checks the
exports.
`ops/verify_passages.py`, the host tool that re-proved the reference passages
from the publishers' PDFs through the earlier PDF reader, was removed with that
reader; the committed passage files and their import are unchanged.

## Reinstalling an older revision

**Since release 2 of the admin move: a changed procedure, not a lost
capability.** Every earlier revision's installer pins the `quillmd` vhost's
before state alone, so from `ingress` until `ingress-rollback` its preflight,
verify and vhost phases refuse. Its `rollback-app` and a fresh `app` do NOT read
the coupling: run in the after state they can leave quillmd-cpt claiming both
hosts for a port nothing answers. **Never run any phase of an earlier
revision's installer while admin.quillmd.com is moved.** Every older revision
stays installable, by more steps first: switch back revision by revision,
newest first, each with its own installer (`switch-back`), until the web the
moving `ingress` found serves; then that revision's `ingress-rollback` (the
receipt holding the stage is that revision's); then the older installer. A
later revision's `ingress-rollback` refuses and names that way. This revision's
own `rollback-app` refuses while admin is moved. (DECISIONS D396 records why
this is not taken to the owner as a class-b loss: nothing a person uses stops
working, and the way back is written here.)

The Fable coding build's own reasons are above (**What still refuses**): an
unknown coding outcome, and a stage the next worker cannot run still open after
the close. The reasons below are the earlier pipeline's - what its records
would make a still older revision do wrongly - which this revision neither
writes nor reads (its image has none of the modules they need); they are kept
for the record of the revisions that check them.

An older revision's installer does not close a newer revision's stages, and its
worker and web read the newer revision's records under their own rules. The
installed revision 057a7d39 acts wrongly on these (`rollback-app` and the
failure path of `app` read them as it reads the rows), and every revision
before the harness, 80df1831d168 included, on the last two:

- **unknown**: a provider outcome still unknown. Its reconcile requests the
  current context under its rules: without a date when that context holds a
  member's conflicting service date, and whether or not that request failed
  before.
- **outcome**: a request of the document's current revision that failed (or
  was not sent although it went through the send), with no answer to it
  retained that it would reuse, and that it could make again. A metadata save
  requests the member's service date when one is set, otherwise its own
  reading of the document's date - which can differ from this revision's and
  which this revision cannot read, so then every such request counts - and
  sends that request unless its run in use (the newest finished run, a hold or
  a bounded second review included) carries it. A Resume of a stopped predict,
  or of a stopped assess of an earlier context, requests the current context's
  date, and of a stopped extract or analyze what a fresh reading gives, without
  that check. Either sends the failed request again.
- **conflict**: a member's conflicting service date in the current context,
  while the latest stage is a stopped predict, or a stopped assess of an
  earlier context. Its Resume requests the context, which it reads as having
  no date.
- **second_review**: a code only the bounded second review selected, in the
  current assessment's decision set (selected or excluded). Its re-assessment
  (after a metadata save, a Resume or a reconciliation) reads the primary
  answer alone, so the code leaves the decision set without a reviewer's
  decision.
- **second_review_refused**: the current assessment read a bounded second
  review whose response this revision refused whole (not used), beside a
  primary answer that was used and leaves nothing to decide. 057a7d39
  recognises a refusal of the primary answer only, so whatever state it is
  handed it says that no code was proposed beside a response it never read:
  as `no_codes` it lists 'No CPT codes proposed', as `provider_failed`
  'Provider request failed' ("The provider request failed. The provider did not
  return proposals."), and its blocker is "No CPT code was proposed" and its
  page "No CPT codes were proposed for this document." either way. No list
  state can be put back for it, so it is named, never handed over.
- **second_review_unread**: the current assessment did not read a bounded
  second review made for the answer it reads, and that review may hold codes
  nobody read - it was sent and its outcome is unknown (reconciled or not), or
  it was answered and not read yet - beside a primary answer that was used and
  leaves nothing to decide. Every second review made for that answer is read,
  not only the newest: a reconciled unknown one releases another ask, and a
  retry that then failed or was not sent does not clear it. This revision states that review's outcome ('Second
  review outcome unknown', "No CPT code was proposed in the response that was
  read; the second review has an unknown outcome"); 057a7d39 reads no second
  review, so whatever state it is handed it lists 'No CPT codes proposed' (or
  its name for the state it is given), with the blocker "No CPT code was
  proposed" and the page "No CPT codes were proposed for this document.", beside
  a request that was sent. No list state can be put back for it, so it is
  named, never handed over. A second review that failed or was not sent
  proposed nothing, so what 057a7d39 says of those rows is true: they are put
  back (below) - unless an earlier one made for the same answer is unread as
  above, which names the encounter.
- **participant**: a code only a harness participant (Astra or Fable)
  proposed, in the current assessment's decision set (selected or excluded).
  No revision before the harness reads a participant: its page and both
  reports show the code as the provider's own proposal, naming no other
  proposer, and its re-assessment reads Corti's answer alone, so the code
  leaves the decision set without a reviewer's decision. No list state can be
  put back for it, so it is named, never handed over.
- **member_answer** (core repair 2026-11-03): a member's answer that stands
  ("Not documented" or "Cannot confirm") on the revision of the current
  assessment or the current revision - an answer belongs to its revision and
  stands through every re-assessment of it (a context change re-assesses the
  same revision), as this revision's review applies it. No revision
  before the core repair reads one: its page asks that question again and shows
  the code held, where this revision shows it Excluded with the answer and who
  gave it. Named, never handed over; the answer row stays. An assessment this
  revision's worker re-made with a member's answer (support 'answered') names
  the hazard too, standing answer or not, and always counts as written since
  the switch (completion repair, refutation cycle 2): only this revision makes
  such an assessment, so the undo holds the old worker for it.
- **modifier** (core repair 2026-11-03): a current decision of the current
  assessment carries the reviewer's chosen modifier (59 or XS). No revision
  before the core repair reads one: its page and both reports show that
  approval without the modifier. Named, never handed over; the decision row
  stays.
- a stage of a kind it has no stage for (the second review; the harness
  participants' `astra` and `fable`, which no revision before the harness
  runs; harness@2's peer reviews `astra_peer` and `fable_peer`, which no
  revision before harness@2 runs), queued, running, or stopped as the latest:
  its worker ends on it.

`rollback-app` closes the last as failed, and refuses, naming the encounters,
while any of the first nine exists. They are cleared on this revision's web:
reconcile each unknown outcome; Resume the stopped stage, or answer the date
question (correct or clear the metadata date), after which this revision makes
the request for the agreed date (re-assessing with, or re-using, a recorded
answer to it where one exists). A request that failed or was not sent stays
recorded on its revision, so only an addendum (a newer revision, whose own
request then stands) clears an encounter a metadata save would send it again
for, or this revision stays installed. A code only a second review selected,
a second review's response refused whole, and a second review left unread are
cleared likewise by an addendum (the newer revision's assessment reads no second
review, and none is made for its answer, until one is asked for), or this
revision stays installed. A code only a harness participant proposed is cleared
by an assessment made with no participant configured, which holds none: install
this revision again with `--astra-mode disabled --fable-mode disabled`, then
re-assess each named encounter on its web (a saved change to its context
re-checks the answer in use; an addendum makes a new request), or this revision
stays installed. A member's answer is cleared with "Change this answer" on
the encounter's "A few details needed" panel (its withdrawal is recorded; the
question is open again), and a chosen modifier with "Undo decision" on that
approval (the decision row stays, revoked), then approving again without a
modifier - or this revision stays installed. So,
before reinstalling an older revision over this one:

1. Clear those records on this revision's web.
2. Run this revision's `rollback-app`: it refuses while one remains;
   otherwise it closes every stage this revision queued, ran or left resumable
   since its pair was created, and every stage of a kind the next worker cannot
   run, whichever pair created it, puts back the list states an older revision
   labels otherwise (below), and removes the pair.
3. Then install the older revision as usual. Its migrate is a no-op on this
   schema (migrations are not reversed). Revisions from this one on also
   refuse, in `app`, while a stage they cannot run is open.

Records this revision made stay as they are and are read by the older code as
it reads them: its reports do not mark a bounded second review as used, and its
re-assessment does not read one (the alternatives and the check of a second
review that added no code leave the assessment there; one that added a code is
named above); it reads a hold as a provider request that failed; it requests a
member's service date that differs from the document's as the date (its own
rule, which this revision holds); and where it reads the document's date
otherwise than this revision does, its next metadata save requests its own
reading (a first request, sent; one that failed or was not sent before is named
above). The harness participants' runs (provider `astra` or `fable`, purpose
`independent`, or harness@2's `peer_review`) are no run of 80df1831d168's own
(its run in use is a primary run); 057a7d39 takes the newest finished run of
any kind as its run in use, so a participant run can be it: its metadata save
then re-predicts, reusing Corti's retained answer to an unchanged request
(nothing is sent), and a failed request it would send again is **outcome**,
named above. An unknown outcome of a participant run is **unknown**. The runs'
endpoint, models and response id, the assessment's participants and retrieval,
the passage tables, and harness@2's exchanges, tool calls and finding
confirmations (migration 0008's tables) are columns and tables no older
revision reads (migration 0007 gives each column a database default). The
licence note `license-note` corrected is a text an older revision shows as it
is; a source an older revision imports afterwards gets its own importer's note,
which this revision's `license-note` corrects once this revision is installed
again. Encounter list states stay as this revision last derived them until an
action on each encounter recomputes them - except a state this revision labels
from more than the state. An older revision labels a stored state by its name
alone, and never recomputes one: a response refused whole is `provider_failed`
here, labelled 'Provider response not used', and 057a7d39 would list it as
'Provider request failed' ("The provider request failed. The provider did not
return proposals.") although the request succeeded. So `rollback-app`, and the
failure path of `app`, give each such encounter the state the next pair
derives for it before handing the rows over: the parked image's own
derivation when a pair is parked, else 057a7d39's (its derivation, run in this
revision's image). That is truthful for the primary answer's response refused
whole only: `no_codes` - 'No CPT codes proposed', with its blocker "The
provider response was not used" and its page saying the response was not used,
so there are no CPT proposals - what 057a7d39 itself shows for that row. A
bounded second review's response refused whole has no such state (057a7d39
reads a refusal of the primary answer only: as `no_codes` it would say "No CPT
code was proposed"), so it is never put back: it is **second_review_refused**,
named above, and `rollback-app` refuses while one exists; nor is a second
review left unread (**second_review_unread**, named above). This revision also
words `no_codes` from its rows: a second review that failed ('Second review
failed') or was not sent ('Second review not sent'), and codes the provider
proposed that none can decide ('No code selected for approval': excluded with
no reinstatement, or alternatives only). Put back to 057a7d39's own derivation,
also `no_codes`, each reads 'No CPT codes proposed' with the blocker "No CPT
code was proposed": true of the first two (neither request proposed anything;
the review is not named, as 057a7d39 reads none), and for the last what
057a7d39 says of such rows it writes itself (refutation p2, reports2:3,
pre-existing there). A bounded second review the undo closes that had sent
nothing - stopped while it ran, before sending, or settled as not sent - left
the assessment as it was: this revision derives the assessment's own state,
never `provider_failed` (no request failed). Where nothing is left to decide it
words that state from the run ('Second review not sent'), so it is put back to
057a7d39's own derivation, `processing_failed` ('Processing failed'), never
handed over as 'Provider request failed' beside a request that succeeded; on the
review queue it stays as it is (refutation P2FR, ROLLBACK 1). Every other state
is labelled alike by both revisions and keeps this revision's derivation:
057a7d39's own reading of a hold (a request that failed) or of a second review
the undo closed (a failed stage) would list a date question as 'Provider
request failed' and drop both from its review queue - and a state on the review
queue is never put back, whatever its label. Installing this revision again
recomputes every state.

## Recovery notes

- Both the `quillmd` vhost and `quillmd-cpt` name admin.quillmd.com
  (`preflight`, a phase or the root helper says the state is `both`): a
  two-file write stopped between its renames and was killed outright, so its
  own undo never ran. nginx keeps the `quillmd` vhost's admin (Caddy's notice,
  with a `conflicting server name` warning), so nothing falls through, but
  every phase refuses that state. Finish it by hand through the root helper,
  either way: back - `quillmd-cpt` given the stage the `ingress` replaced (its
  receipt's `from` when it wrote one; else that earlier revision's rendering
  for the port, as its recording receipt names it, or the HTTP stage on a
  fresh host) - or forward, the `quillmd` vhost given its after state; then
  `sudo -n /usr/sbin/nginx -t`, one reload, and `preflight` - and, after a
  forward finish, `ingress` again, which records the move from its intent. A
  `.quillmd.new` or `.quillmd-cpt.new` left in `sites-available` is the
  stopped operation's staged file; the root helper's two-file operations
  clear it.
- The after state with no recorded move (an `ingress` killed between its
  two-file write and its receipt): run `ingress` again - its intent completes
  and records the move (**The write-ahead intent**) - then, if wanted,
  `ingress-rollback`. Should the rerun itself refuse, the intent file holds the
  replaced stage byte for byte (`from.b64`) for a recovery by hand through the
  root helper.
- `*-previous` containers left by an interrupted `app` while admin.quillmd.com
  is moved: `rollback-app` refuses to remove the pair quillmd-cpt proxies to
  (both hosts would be left on a port nothing answers). Keep the new pair:
  remove the parked pair by hand and run `app` again; then `switch-back` returns
  the previous pair if it is wanted. Do not run `ingress-rollback` first.
- The files in the before state while nginx may still run the after state (an
  undo or a rollback killed before its reload): `ingress-rollback` run again
  reloads nginx onto them; with no recorded move, reload by hand
  (`sudo -n /usr/sbin/nginx -t`, then `systemctl reload nginx`) or run `ingress`.
- `*-previous` containers left by an interrupted `app`: to go back, run
  `rollback-app` first (it refuses while the new pair's records would be acted
  on, or shown, wrongly, as above; otherwise it closes what the new pair left
  open and every stage of a kind the parked worker cannot run, puts back the
  list states the parked revision labels otherwise, with the parked image's own
  derivation, and removes the new pair), then rename the parked pair back by
  hand; to keep the new pair, remove them by hand, then rerun `app` - which
  recomputes the stored list states - unless its receipt says they were
  recomputed (an installer killed outright writes no receipt: rerun `app`).
  `app` refuses while one exists.
- A `cpt-studio-web-next` left by an interrupted blue/green `app` (or
  `switch-back`): read the receipt's `left` and the vhost's port
  (`grep proxy_pass /etc/nginx/sites-available/quillmd-cpt`). When the receipt
  says the switch stopped half way, nginx may run another configuration than
  the file names (a reload whose outcome was not seen): make it run the file
  first (`sudo -n /usr/sbin/nginx -t`, then `sudo -n /usr/bin/systemctl reload
  nginx`), confirm a new set of nginx worker processes, and confirm
  `https://cpt.quillmd.com/health/` answers the revision of the web on the port
  the file names - only then is the rest of this note true. If the vhost
  names the old web's port and the incoming web is this revision's (an `app`
  undo: the back layout), nothing more is routed to it, but what it queued
  while nginx routed to it is still open: never start the old worker by hand,
  which would run that work under its own rules, and do not remove the
  incoming web. Run this revision's `rollback-app`: it proves nginx runs the
  vhost (a reload, new workers seen, `/health/` answered by the old revision -
  otherwise it stops nothing), drains the incoming web while it runs and stops
  it, closes every stage this revision's pair queued, ran or left resumable
  since the incoming web was created (and every open stage of a kind the old
  worker cannot run), puts back the list states, removes this revision's
  worker if one is there and the incoming web, and puts the old worker back -
  held while the close names a record it would act on, or any member's answer
  or chosen modifier (it cannot tell whether the old worker ran beside one
  before the install: once the receipt's reasons are cleared, or the old
  revision is one since the core repair, which reads them, start it by hand
  with `docker start cpt-studio-worker`). A close it cannot finish leaves the
  same layout, for another run. If the incoming web is the previous revision's
  (a `switch-back`), this revision's own worker runs what it queued, under this
  revision's rules: once it has no connection, stop and remove it, put this
  revision's worker back (`docker rename cpt-studio-worker-previous
  cpt-studio-worker`, `docker start` it), and rerun `app`, which recomputes the
  list states. If the vhost names the incoming web's port, the new web serves:
  to keep this revision, start the new worker if none runs, or stop and remove
  what is left of the old web only once it has no connection; to go back, run
  this revision's `rollback-app` (the S4 keep layout, below). `app` and
  `preflight` refuse while a `-next` exists.
- An installer killed outright inside S3 writes no receipt and runs no undo.
  If it was killed after the file was replaced but before nginx reloaded, nginx
  still serves the old web on the old configuration - but the file names the
  incoming web's port, so the next reload by anyone (the TLS renewal deploy
  hook included) moves traffic there, possibly with the old worker parked and
  no new worker. Both webs are still running, so either way the site stays
  served; recover at once: read the file's port and the containers, then either
  complete (start the new worker: rerun `app` once the leftovers are resolved)
  or put the vhost bytes back (`rollback-vhost` is not for this: restore the
  rendering for the old port through the root helper and reload), then run
  this revision's `rollback-app`, which finishes the way back in that back
  layout as above - never start the old worker by hand.
- An S4 failure whose close named a shown state leaves the S4 keep layout: the
  NEW web serving as `cpt-studio-web-next`, its worker stopped as
  `cpt-studio-worker`, the old worker parked and the old web running on the old
  port with no traffic. To keep this revision: fix the worker's failure, remove
  the old web and the parked worker, rename `-next` to `cpt-studio-web`, then
  rerun `app` (a same-revision switch, which starts the worker and recomputes
  the states). To go back: clear the named records on this web first
  (**Reinstalling an older revision**), then run this revision's
  `rollback-app`. In the S4 keep layout `rollback-app` acts on the right
  containers - this revision's web and worker, with this revision's image -
  and the site stays served. No new `preflight` is needed, nor possible here
  (it refuses while a `-next` exists): rollback-app reads co-tenant routing and
  app.quillmd.com itself, right before it acts, records them in its receipt and
  verifies the switch back against them. It refuses, changing nothing, while
  this revision recorded what an older revision would act on or show wrongly,
  or while app.quillmd.com does not answer 200 JSON; otherwise it closes every
  stage this revision's pair started since its incoming web was created (and
  every open stage of a kind the old worker cannot run), stopping there if that
  close names a record, puts back the list states, switches the upstream back
  to the old web (graceful, `/health/` = its revision), drains and stops this
  revision's web, closes again, removes this revision's web and worker, and
  puts the old worker back - held while a close names a record. It succeeds
  only when it did all of that: an incoming web it could not remove fails the
  phase, which says it is left (everything else was done; remove it by hand),
  and so does a Ctrl-C. A drift in the seconds between its read and the switch
  refuses the switch back, and the new web keeps serving: run `rollback-app`
  again. Do not remove the old web by hand: it is what `rollback-app` switches
  back to.
- Staged `.initial-credentials.json.new` / `.agent-credentials.json.new` (for
  another specialty `.initial-credentials-<specialty>.json.new` /
  `.agent-credentials-<specialty>.json.new`; the refusal names them) from an
  interrupted `provision`, or `.operator-enrolment.json.new` from an
  interrupted `operators` or `manage` (a setup code no command may have
  stored: delete it, then issue a new one with `manage issue-enrolment`): delete
  them (no account uses their passwords unless the receipt says the accounts
  were created) and rerun.
- A parked container's log (release 1, A13): when `app` or a `switch-back` could
  not keep a parked container's log, the container is left in place and the
  receipt says why (a `switch-back`'s `parked_left` is retried by the next `app`
  first). Fix that cause first (a full `/var/log`, a `docker logs`
  that fails), then keep the log before removing the container: as root, write
  `docker logs --timestamps <container>` into `/var/log/cpt-studio/containers/`
  (root 0600, named `<role>-<revision12>-<UTC>-by-hand.log`). A copy made by
  hand keeps every line - the installer's keeps ids only - so it is the
  incident's record: read it, keep what the incident needs, delete it. Then
  remove the container (`docker rm`).
- Rotating the two passwords: `--phase provision --owner-username … --reset-passwords`,
  with `--specialty neurosurgery` or `--specialty orthopedic-surgery` (and that
  specialty's owner and agent) for those workspaces, and `--workspace-name` for
  any workspace, Gastroenterology's included, that was given its own name. The installer keeps one
  workspace per specialty, its pair of files naming it; a second workspace of a
  specialty is provisioned with `manage provision` directly.
- Rotating the coder's key: the owner replaces its source; remove
  `/etc/cpt-studio/anthropic-credentials.env` by hand (root), run `secrets`,
  which copies the new source, then `app` with the same `--coding-mode`: the
  running worker's mount holds the file it was started with. `secrets` refuses a
  copy that differs from its source rather than replace it.
- A staged `.anthropic-credentials.env.new` in `/etc/cpt-studio/` from an
  interrupted `secrets`: delete it by hand and rerun; `secrets` refuses while one
  exists.

## Emergency access (release 1, B8)

Practices never need the operator to read their own documents: members
download originals and reports themselves, and a complete per-document bundle
(`api/encounters/<id>/bundle`). Each locked state below is cleared by one
recorded act - a ruled act through `--phase manage` runs under a committed
declaration, with `--reason-file <file>` (RAM-only for the command) and
`--by <person>` (a person, never a role):

| the state | what clears it |
|---|---|
| a sign-in delay on a username (B1) | wait: it ends within 15 minutes at most; a device or a network the person signed in from before skips it; or `--command clear-signin-failures --username <name>` |
| the refusal of one username from one address (B1) | wait 15 minutes; or `--command clear-signin-failures --username <name>`, or `--address <address>` for that address |
| the refusal of a whole address (B1: too many failed sign-ins from one IPv4 address or one IPv6 /64, for example an office behind one address) | it ends 15 minutes after the last failed sign-in (a refused attempt no longer extends it); or at once with `--command clear-signin-failures --address <IPv4 address, or IPv6 address or /64>` |
| the forced password change (B4: a password staff set, at its first sign-in) | the account page, `/account/`: its owner chooses a new password |
| a member's staff-set password not replaced within 72 hours (B4, D31) | a reset in the console (People, the person's password): a new password and a new 72 hours; the clock is never extended |
| the operator's staff-set password not replaced within 72 hours, or a setup code that expired (30 minutes) or was claimed in another browser | `--command issue-enrolment --username <name>`: a new single-use setup code (it revokes an unfinished claim), kept root-only in `/etc/cpt-studio/operator-enrolment.json` and never printed, then the setup on admin.quillmd.com |
| lost security keys | one of the recovery codes, at `/login/recovery` on admin.quillmd.com (printed once at enrolment; held sealed by the security officer, D20); otherwise `--command reset-second-factor --username <name>`, which marks the keys removed, voids the recovery codes, ends the account's sessions and issues a new setup code, kept as `issue-enrolment` keeps one, for enrolling again within 30 minutes |

Losing both keys and every recovery code locks the console until that reset
from the server, by design. When the site itself is down, the existing
`switch-back` returns the previous pair (**Switching back**); on the new
server, a restore from backup.

## Disposal, returns and the ledger (release 1, D1, D2)

`dispose` and `export-workspace` are the application's commands (Lane 4 of
release 1), run only through `--phase manage`, never over HTTP:

- `--command dispose --dispose-step close --workspace-id <id> --reason-file
  <file> --by <person>` closes a practice (uploads and coding stop; reading
  stays on until the practice confirms it received its data);
- `--dispose-step plan` (`--workspace-id`, or `--encounter-id` for one
  document, never both) `--reason-file <file> --by <person>` is a dry run
  that records what would be destroyed;
- `--dispose-step execute --plan-id <id> --by <person> --approved-by <another
  person>` carries out a plan under a day old: two different named people run
  and approve it (D14), under the plan's own reason. It takes nothing else: a
  `--workspace-id` or `--encounter-id` is refused before anything runs, since
  the plan's own scope is what is destroyed (refutation round 1, installer-1).
  Every step takes exactly what it passes to the command - `close`
  `--workspace-id --reason-file`, `plan` `--workspace-id` or `--encounter-id`
  and `--reason-file`, `execute` `--plan-id --approved-by`, `ledger` nothing
  more, `replay-ledger` `--ledger-file` (and `--execute --approved-by`), each
  with `--by` - and refuses any other, so what was typed is what ran. A
  reason is required exactly where the command reads one, `close` and `plan`,
  and refused everywhere else (refutation round 1: `execute` and
  `replay-ledger` had required one their command never read);
- `--dispose-step ledger` prints the ledger - the MAC-signed list of every
  disposal - into a log file of its own in the receipts folder
  (`manage-<UTC>-NN-dispose-ledger.log`; the receipt's `ledger_printed` names
  it with its sha256, size and line count). **Keep that log file whole** with
  the backups, and before a replay check its sha256 against the receipt's: the
  receipt's own `stdout` keeps only the last 16,000 characters of any act's
  output (its `stdout_cut` and `stdout_chars` say whether it was cut and how
  long it was), so it is never the copy to keep (refutation round 1,
  dataloss-1: a cut copy was refused, or replayed without the oldest
  disposals). A secret the command printed in it is redacted there, and that
  line no longer verifies: the summary says so (a FINDING), and the ledger is
  printed again once that is fixed. The ledger step keeps only a ledger the
  replay step reads - at most `LEDGER_LIMIT` (16 MiB) and UTF-8, the one limit
  both steps read (refutation round 2, installer-0: the replay had refused, at
  1 MiB, a 5,000-document practice's ledger the ledger step called kept whole).
  The limit is sized for the largest practice this release serves: at the
  owner's figure (1,000 practices at 50 uploads a day) a practice reaches
  18,250 documents in a year, and its whole-practice disposal adds about
  3.8 MB of ledger at one file a document (209 bytes a document, 92 more for
  each further file, about 5 KB a disposal), 8.9 MB at four files. A ledger past
  the limit is written to no file: the step fails, says why, and changes
  nothing (the database keeps every row the ledger is printed from); see
  **Known limits**;
- `--dispose-step replay-ledger --ledger-file <file>` is,
  on its own, a dry run that changes nothing (the receipt's `mode` says `dry
  run`, and its summary never says done); with `--execute --approved-by
  <another person>` it re-applies the ledger after a database restore, so
  destroyed data stays destroyed - two different named people, as for a
  disposal (D14). A replay with `--execute` that ends with an entry needing a
  person's decision - one whose commit's outcome was unknown, while nothing
  else failed: the command exits 3 - is recorded so: the receipt's `mode` says
  `needs a person's decision`, with the command's ids-only output, never done
  and never undone. Any other non-zero exit is a failure, its ids-only output
  in the receipt too. The decision is made by
  planning that scope again (`--dispose-step plan` for its workspace or
  encounter) and executing that plan with two people. The ledger, like every
  destruction certificate, holds ids, counts, digests, storage names (random
  ids) and the names of the two people, never a document's text or title, and
  a reason only as `sha256:` with the sha256 of its text as the DisposalEvent
  row keeps it (the reason file's text without leading and trailing white
  space, so not the digest the receipt records for the file). Only the
  database rows hold a reason's words; a row written back by a replay after a
  restore holds the digest, so keep the reason files if their words must
  outlive a restore.
  **After a database restore, replay the ledger BEFORE the site is opened**
  (web and worker stopped, or no pair at all: **Restoring the database**,
  below): a whole practice's replay destroys again everything
  of that practice, including anything a member added to the restored copy, and
  the replay's report counts such documents. A signal (SIGTERM, SIGHUP) or
  Ctrl-C before a destruction's commit stops it with nothing destroyed. From the
  moment a commit begins it is held: the commit and the run's record go to their
  end, the steps after the commit stop at the next one (a statement still
  running is cancelled; the run is recorded 'failed', the signal named as the
  problem of the step it stopped), a signal that comes once those steps are done
  leaves the record as it stands, and the command, once it has printed its
  record, ends with 143 (SIGTERM), 129 (SIGHUP) or 130 (Ctrl-C) - though under
  the door's ceiling the installer removes its one-shot before that record can
  be finished (**Known limits**). A replay stops
  the same way before its next ledger entry and prints its record. Every
  certificate and ledger line it prints names only what the database committed.

The first closure or destruction ends the way back to every revision before
release 1: `switch-back` and `rollback-app` refuse to hand those rows to a
revision without disposal (**Switching back**, above); the way on is a fix
forward. Nor is a practice closed or a document destroyed while such a
revision serves (below).

Every disposal step refuses while an install or switch-back is in progress (a
`cpt-studio-web-next` or a `*-previous` container). A step that changes rows -
`close`, `execute`, `replay-ledger --execute` (the receipt's mode `executed`) -
also refuses, running nothing, unless the pair under the canonical names
(`cpt-studio-web` and `cpt-studio-worker`, running or stopped) is a revision
with disposal, read from its tree as `switch-back` reads it (refutation round
2, switchback-0: a switch-back allowed because nothing was closed, followed by
a closure and a destruction while the revision before release 1 served, handed
that revision the very rows the switch-back refuses to hand it). No web there,
a container this installer did not start, one with no revision label, or a
revision this checkout cannot read refuses too. Install a revision with
disposal (`--phase app`), then run the step again. One exception, for
`replay-ledger --execute` alone: with no pair at all - docker answers that
neither `cpt-studio-web` nor `cpt-studio-worker` exists; an answer it cannot
read refuses - nothing serves, so the replay runs, before `app` starts a pair
(refutation round 3, installer-0: **Restoring the database**, below); `close`
and `execute` still need a pair with disposal. The dry runs (`plan`, and
`replay-ledger` without `--execute`) and `ledger` stay open: they change no
row an older revision reads (a plan writes only its own `planned`
DisposalEvent, a release-1 table), and the step that would carry a plan out is
refused until a revision with disposal serves. Only after these readings is
the command told no switch is under way (`CPT_STUDIO_SWITCH_STATE=idle`, which
it requires). It runs
as the application's user with the files volume, the declaration passed as
`--authorization-ref <declaration>@<commit>`. `--command export-workspace
--workspace-id <id> --reason-file <file> --by <person>` writes one practice's
documents and manifests into a new folder of its own: the installer makes
`/var/lib/cpt-studio-exports/<id>-<UTC>/` for the application's user, mounts it
at `/run/cpt-export`, and the command makes `--out /run/cpt-export/<id>-<UTC>`
inside it (Lane 4's command refuses a folder that exists; the files volume is
read-only). Everything in it is then made root-only (folders 0700, files 0600);
the receipt counts its files and bytes and never names one. If the export's
'exported' DisposalEvent cannot be written, the command removes the export and
says nothing was kept (exit 1). If it cannot remove it, its error says a copy
may remain; remove that folder by hand, as root, without reading it.
Delivery to the practice is the termination runbook's step.

**Restoring the database.** After any restore from a backup older than a
disposal, replay the ledger before the site serves again: a dry run
(`--dispose-step replay-ledger --ledger-file <the kept ledger log>`), then the
same with `--execute --approved-by <another person>`. The command refuses the
replay while the worker runs or stopped less than two minutes ago - it reads
the worker's last beat in the database, since a restored copy's queued coding
would send documents the ledger destroyed - and, as every manage act, it needs
this revision's migrations applied (`manage migrate --check`). One sequence
serves both kinds of host (refutation round 3, installer-0):

1. Stop the pair, never remove it, before the restore, so nothing runs on the
   restored copy: as root, first `docker stop cpt-studio-worker`, then
   `docker stop cpt-studio-web` - each waits its own stop timeout, the one the
   installer starts the container with (**What gets installed**; the worker
   finishes the stage it is in and claims nothing new). A fresh server has no
   pair (neither `cpt-studio-web` nor `cpt-studio-worker`) and nothing to
   stop.
2. Restore the database, and the files volume from the same backup.
3. Wait two minutes after the worker stopped (on a fresh server, after the
   backup was taken): the restored database holds the worker's last beat.
4. Replay: the dry run, then `--execute`. A stopped pair is read as above (its
   revision must have disposal); with no pair at all the replay runs too,
   since nothing serves.
5. Start a pair. On the serving host rerun `app` with the `--coding-mode` (and
   `--authorization-ref`) it was installed with - with its web stopped, `app`
   replaces the pair on the port the vhost names - or start the stopped pair
   as root: `docker start cpt-studio-web cpt-studio-worker`. On a fresh
   server, `app`, and only then `http-vhost`, `cert` and `ingress`, in that
   order: `ingress` writes the HTTPS stage, which opens the site (the HTTP
   stage only redirects). `https-vhost` republishes a stage that is already
   live and refuses on a fresh server (refutation round 4, installer-2).

A backup from before this revision's migrations (the dump taken before an
install) is replayed onto only once it is migrated, and only `app` migrates:
`migrate --check` refuses the replay until then. Run that `app` with
`--coding-mode disabled`, so its worker sends nothing, then stop the pair at
once as in step 1 and go on from step 3; on the serving host its web serves
the restored copy in between (**Known limits**). The ledger's MAC is keyed by the
application's `CPT_STUDIO_SECRET_KEY` (`/etc/cpt-studio/app.env`), so a restore
must keep the same secret key: with another key the ledger cannot be verified,
and destroyed data could come back.

## Local build and tests (no host change)

The installer tests need no Docker. Those of the in-image scripts in
`test_install_harness2.py` (the licence-note correction, the close of
peer-review stages) also run on a disposable PostgreSQL when the
`CPT_STUDIO_*` variables name one, as CI sets them (never the live port
55451): they create `test_cptstudio_<suffix>_installer` and drop it again.
Without one they are skipped, and say so.

```bash
cd cpt-studio
python3 -B -m unittest discover -s ops -p 'test_*.py' -v      # installer tests, no Docker
ctx=$(mktemp -d) && git archive HEAD cpt-studio | tar -x -C "$ctx" \
  && cp "$ctx/cpt-studio/deploy/.dockerignore" "$ctx/cpt-studio/.dockerignore" \
  && docker build -f "$ctx/cpt-studio/deploy/Dockerfile" -t cpt-studio:dev-build "$ctx/cpt-studio"
```

The Django suite inside the image needs a disposable PostgreSQL:
`docker run --rm --network host --read-only --tmpfs /tmp:rw,exec,nosuid,nodev,size=1g --env-file <0600 file with CPT_STUDIO_SECRET_KEY and CPT_STUDIO_DB_PASSWORD> -e CPT_STUDIO_DB_HOST=127.0.0.1 -e CPT_STUDIO_DB_PORT=<port> -e CPT_STUDIO_TEST_DB_SUFFIX=<unique> -e CPT_STUDIO_STATE_DIR=/tmp/state cpt-studio:dev-build manage test tests --noinput`.
`exec` on `/tmp` is for the tests only (a test may run a stand-in executable
from a temporary directory). The installed containers keep `/tmp` `noexec`;
LibreOffice runs from `/usr/bin` and `/usr/lib/libreoffice`.

## Known limits

- admin.quillmd.com's HTTP-01 challenge is answered by QuillMD's :80 block:
  the `cpt-studio` lineage renews by webroot for both names, and admin's
  challenge is served by the `quillmd` vhost's :80 `server_name` (its line
  13, QuillMD's file, which this installer never changes). If QuillMD drops
  admin from that line or reroutes it, the next `cpt-studio` renewal fails for
  both names - and with it cpt.quillmd.com's certificate at expiry, though the
  `cpt.quillmd.com` lineage (the way back's) keeps renewing. `preflight`, `cert`,
  `ingress`, `https-vhost` and `verify` each prove the route (an ACME probe
  file served for `http://admin.quillmd.com/` through 127.0.0.1); between
  installs nothing here watches it: a renewal dry run, or a monitor of the
  served certificate's expiry, is the host monitoring's.
- The coupling invariant pins the whole `quillmd` vhost (QuillMD's file) in two
  states. Any later edit QuillMD makes to it - its own acts rewrite the app
  block at its end - leaves it in neither, and every phase here refuses until a
  CPT Studio release re-derives the pins from the file as it then is (line 26's
  edit and line 13's route still hold). Serving is not affected; installs wait.
- A later revision whose template differs from the moving revision's must have
  the mover's stage republished over its own (the mover's `https-vhost`) before
  the mover's `switch-back`/`ingress-rollback` chain can pass; nothing automates
  that step.
- The cert phase runs certbot in a chroot where the renewal deploy hook
  (`renewal-hooks/deploy/reload-nginx.sh`) cannot reload nginx: certbot reports
  the hook's failure as a warning and exits 0. On a first order nothing loads
  the new lineage yet (`ingress` reloads); a renewal inside `cert` is published
  by the next reload, which `ingress` and `https-vhost` perform.
- The installer's probes are HTTP/1.1, one connection per request: they stand
  in for a browser's HTTP/2 connection reuse by sending one name's Host on a
  connection opened for another (421 expected for a QuillMD name, service for
  cpt.quillmd.com and admin.quillmd.com). The reuse itself is the act's live
  check's to prove.
- A checkout whose `scripts/check-cotenants.sh` judges admin.quillmd.com
  despite `CPT_INSTALLER_SKIP_HOSTS` is refused by `preflight`; the installer
  reads a judged row as one naming the host with two three-digit codes, so the
  script must print a skipped host without them.
- Data at rest is on the unencrypted root disk (docker volumes). Since release
  1 (A3) nginx writes neither an upload nor a response to its temporary
  directories (request bodies are held in memory up to 20m, responses in 24 MiB
  of memory buffers, and a larger one is relayed without a file), and the
  database runs without swap; nginx's own memory can still be paged to the
  host's unencrypted swap file under pressure (no swap, or encrypted swap, is
  the new server's). Acceptable only because the service is
  synthetic-only; real data would need an encrypted volume first.
- The database has no scheduled backup in this release.
- A restore from a backup older than this revision's migrations is migrated
  only by `app`, which starts the pair: on the serving host its web serves the
  restored copy - the documents the ledger destroyed among them - from that
  `app` until the pair is stopped for the replay (with `--coding-mode
  disabled` nothing is sent), while on a fresh server nothing is served before
  `ingress` (**Restoring the database**).
- A refusal that quotes the re-grant approval line (`Approved: --regrant
  <name>`) inside a fence or a quote the installer's reader does not take for
  one - a fence of another length or character, a quote's lazy continuation,
  an HTML `<pre>` block - approves that re-grant (refutation round 3,
  installer-1): never quote the approval line in a declaration.
- Under the door's ceiling an interrupted one-shot is removed at once, without
  its own stop, so a destruction's held stop may not finish its record: the
  plan's 'committed' DisposalEvent stays the record of what was destroyed (the
  ledger and a replay read it so), and a new plan of that scope finishes the
  run (refutation round 3, installer-4).
- A ruled act's reason in words is still redacted wherever the act's output
  repeats it, as any echo of it is: one written as the act's own printed words
  around an id or a count (a reason line such as `Files in scope: 1`) is
  redacted there too. The receipt counts every redaction (`redacted`) and the
  summary says how many, so such a record is seen, never silent.
- The disposal ledger holds every disposal ever made, and this release replays
  and keeps one of at most 16 MiB (`LEDGER_LIMIT`; **Disposal, returns and the
  ledger**): about four whole-practice disposals of a practice-year at one
  file a document. Past it the ledger step fails and keeps none, and a release
  must raise the limit (the replay's one-shot has 768 MiB; its reading of a
  16 MiB ledger peaks under 90 MiB) before a ledger can be kept again. Until
  then, never restore the database from a backup older than its newest
  disposal: no ledger could destroy that data again.
- Release 1's front door (A1) starts with the spec's numbers (D5), sized on a
  copy before the live publish, the sign-in and the upload raised for an office
  behind one address: every request 30 r/s with a burst of 120 per client, the
  sign-in 60 r/min (burst 40: everyone signs in again at once after the switch
  signs them out; B1 is the guessing control), writes 5 r/s (burst 30), uploads
  60 r/min (burst 60: 20 people each uploading a document every 2 minutes are
  never refused; the application's per-member limit is the fine control),
  report exports 6 r/min (burst 6); 40 connections and 20 byte downloads at
  once per client, of which 4 may carry a body over 64 KiB (an upload or a
  coding review's answers; 40 such at once in all) and 40 a smaller one. A
  client is an IPv4 address,
  or an IPv6 /64; this host's own probes are not counted. A practice behind one
  address shares them. A refusal is a plain 429. Upstream read and send time
  out after 60 s (gunicorn's own 120 s is unchanged).
- Memory at the edge (A3) is bounded. A request body is held in memory, its
  buffer reserved at the length the client declares, and each route admits
  the body it needs: the upload 20 MiB, a coding review's answers 1 MiB, every
  other request 64 KiB (sign-in, account, second factor, the JSON API's posts
  and the console, whose largest body is under 25 KB). A larger declared length
  is refused with 413 before any of it is read. So only uploads and answers
  can declare more than 64 KiB, and at most 40 such bodies are read at once in
  all - under 800 MiB however many clients send. A body of 64 KiB or less
  counts per client only, 40 at once: under 2.5 MiB a client, with no global
  cap. A body whose length is not declared is refused with 411 when it is
  chunked or a POST, PUT or PATCH (every browser declares it); any other (an
  HTTP/2 stream by another method) is cut off at 64 KiB read. At most 24
  downloads (each up to 24 MiB of response buffers) are relayed at once in
  all - under 576 MiB. A sender that stalls 15 s between two reads is cut off;
  one that trickles a byte every few seconds holds its slot. So uploads and
  answers can still be held up by slow trickles from ten or more clients (ten
  /64s with four slow senders each fill the 40) until they stop, and then get
  429; sign-ins cannot, nor can any other request: a body of 64 KiB or less
  never takes one of those 40.
- The edge log (A2) holds about 250 bytes a request on the shared root disk;
  the host's nginx rotation keeps it (about two weeks: D7). The error log's
  request line can carry a query string; today's query parameters hold no
  patient detail (`view`, `next`, `workspace`, `kind`, `result`, `before`).
- The TLS policy (A4) is CPT's 443 block's, and CPT is not this shared
  listener's default server: once SNI has chosen CPT's block, `ssl_protocols`,
  the TLS 1.3 `Ciphersuites` and `ssl_prefer_server_ciphers` stay the default
  server's, so TLS 1.3 ChaCha20 is accepted (measured by the edge refutation on
  nginx 1.24 with this host's libssl 3). `https-vhost` and `verify` probe what
  negotiates (`openssl s_client` against 127.0.0.1:443) and record it - a suite
  outside the policy is a finding, never an undo (D27); the fix is CPT's own
  nginx on the new server.
- The application's logs (A13) are kept ids only and on this host; between
  deploys Docker's own rotation still drops a running container's oldest lines,
  so the edge log is the longer record of requests until the new server ships
  logs off the host (TEC-11 (5)).
- The converter (A7) converts one Word file at a time; a converter that is down
  fails every Word round as busy (it never falls back to converting inside the
  worker), and a replacement leaves a few seconds in which a conversion fails as
  busy and can be retried.
- No switch-back starts an earlier pair with a live legacy provider (A8): Corti,
  Astra, the earlier Fable participant and the earlier interpreter have no BAA,
  so `--provider-mode`, `--astra-mode`, `--fable-mode` and `--interpreter-mode
  live` are refused (D21, an accepted capability loss); their key copies stay
  untouched until the owner deletes them.
- Everyone is signed out once at the release-1 switch (the session cookie gets
  its `__Host-` name, B6) and again after any switch-back; the vhost sets the
  flags of both names, so either revision's web serves behind it. The
  installer ends the sessions themselves, not only the browsers' cookies: at
  `app`'s S2 (or its swap) from a revision before release 1's session policy,
  and at a `switch-back`'s B4 to one, every `django_session` row is deleted
  with one SecurityEvent `sessions.ended_at_install` (a count and the two
  revisions). An `app` or `switch-back` between two revisions that both have
  the policy ends none. A sign-in on the older web in the seconds between S2's
  end and the end of S5's drain (refutation round 1, rollback-3's window) keeps
  its row: it signs nobody in on release 1 (its cookie's name is not read), and
  release 1's sign-out everywhere cannot find it (it reads only the rows
  release 1 linked to the account: refutation round 2, sessions-2). Every way
  back to the older web through this installer ends it first: a `switch-back`
  at B4, and `rollback-app` (sessions-2) - in the S4 keep layout before it
  switches the upstream back, and in its removal of this revision's pair before
  the pair is removed, when the parked pair has no session policy or none is
  parked (what runs next is then not known) - with the same receipt fields
  (`sessions_ended`) and SecurityEvent. A failed end is never skipped: the keep
  layout's new web keeps serving, the removal leaves the pair stopped and not
  removed, and `rollback-app` is run again. Left: an `app`'s own undo at S3 or
  S4 returns the older web within seconds of S2's end without ending them
  again, and `rollback-app` in the back layout (which such an undo can leave)
  finds the older web already serving and ends none; a sign-in made on it in
  those seconds stays valid there until its own 8-hour limit. So does one under
  an older revision that its own installer puts back over release 1 without
  `rollback-app` (it predates the policy).
- Release 2's web (R2-5 to R2-8) is four sync processes forked from one
  master that loads and warms the application before its first fork. Each
  process keeps one database connection, checked at the first query of each
  request, until `CONN_MAX_AGE` in `cptstudio/settings.py` has it replaced: the
  database shows four idle sessions of the web (up to eight while a switch runs
  two webs), and a changed database setting that needs a new session reaches
  the web only as its connections are replaced. The worker and the one-shots
  keep release 1's short-lived connections, with no check: only the web's own
  entry point (`cptstudio/wsgi.py`) sets `CPT_STUDIO_WEB`, and the installer
  gives it to no container.
- A worker that hangs before its first heartbeat - while it opens its
  connection at start, against a database that accepts the connection and
  never answers - is not timed out by gunicorn 23, which times a worker out
  only after its first heartbeat; the web's own connect timeout
  (`cptstudio/settings.py`) ends the wait, and the worker then serves while
  `/health/` reports the database.
  A database that refuses the connection, or is gone, fails it at once.
- Release 2's search (`POST /api/encounters/search`, R2-20) matches text in
  PostgreSQL's builtin `pg_c_utf8` collation, which PostgreSQL 17 introduced:
  the database must stay PostgreSQL 17 or newer - on this host (17.11) and on
  the new server - and CI runs its tests on `postgres:17`.
- Release 2's front door (R2-27): the documents' search
  (`POST /api/encounters/search`) is a read sent as a POST, so its words stay
  out of every address and log; it counts in the every-request zone alone,
  never in the writes', so an office searching at once cannot get a
  colleague's decision or answer refused. No zone's name, size or rate
  changed. The vhost is republished by `cert` and `https-vhost` before `app`,
  as any change under `deploy/nginx/` is (blue/green residual 10).
- Release 1b, not in this release: least-privilege database roles (A10; the app
  connects as the bootstrap superuser), the weekly dependency scan (A12), the
  malware scan's phase (D5) and stored-file encryption's installer side (F1:
  gunicorn runs no Django system checks, so F1's key check, `studio.E101`,
  would not stop the web container - the installer must check the key itself
  when F1 is switched on).
- The worker has no Docker health check; `app` and `verify` check that it is
  running and not restarting.
- The application uid is 10150, not 10001: 10001 already runs a co-tenant's
  containers here, and RLIMIT_NPROC (which a bounded child process may set from
  its container's own task count) is accounted per host uid. `preflight` and
  `verify` refuse if any task outside CPT Studio runs as 10150.
- The installer reads the coder's credentials by key NAME only (`secrets`) and
  through the application's own loader, offline (`app`); whether the key works
  is known only from the first live send - there is no access check. A refused
  key shows as the first document's coding failing; an authentication,
  permission, billing or quota refusal holds the coding stage until an operator
  releases it.
- The scan that keeps credential values out of receipts and logs matches each
  value as written, unquoted and without an inline comment, and does not match
  values under 8 characters (they would match by chance), nor a value
  transformed (encoded, or partly printed). It reads only the file of the
  holder whose output it scans (in an `app`, the coder's Anthropic file).
- The worker's stop timeout (3,600 s; the Fable coding build) covers its one
  stage: the document's preparation (a Word file's conversion, at most 60 s in
  its bounded child), the reader's send and the checker's, one after the other,
  each a stream of up to 96,000 output tokens at effort max (about 1,000 s at
  the slowest rate measured), on each of the worker's
  `CPT_STUDIO_CONCURRENT_DOCUMENTS` threads at once - a worker asked to stop
  lets each thread finish its job and claims nothing new. It is the coding
  job's stale-stage threshold too (`studio.jobs.CODE_STALE_SECONDS`): a stage
  still running when the 3,600 s pass is killed with the worker and settled as
  any stage cut short (a send in flight recorded unknown, never sent again; the
  stale sweep, or an undo's close). Parking or removing a worker that is inside a
  stage waits up to that long, so a stop in `app`, `switch-back` or
  `rollback-app` can take
  up to 60 minutes: let the queue drain (or Stop the encounters) first to
  avoid the wait. A worker of the pipeline before it (parked on the way in, or
  started by a `switch-back`) is stopped the same way and exits as soon as its
  own stage (1,588 s at the longest) ends. Raising the bound from round r3's
  1,800 s changed nothing else the installer times: the subprocess waiting on
  `docker stop` waits the bound plus 60 s, the availability record runs for as
  long as the switch takes, and no phase has a time limit of its own. In blue/green the site stays
  served meanwhile, and that wait is the processing pause: what members start
  is accepted and shown as queued.
- The coding stage's two figures (the build specification, sections 3.1 and
  3.2; DECISIONS D325 (3)'s rule: class d, the owner's figures - settings, never
  constants of the code). `CPT_STUDIO_DOCUMENT_CEILING_USD` bounds what one
  document's revision may cost over every round: a send whose worst case would
  pass it fails its round, never sent. `CPT_STUDIO_CONCURRENT_DOCUMENTS` is the
  number of documents the one worker codes at once (its threads, each holding
  one provider slot). The installer writes, into every container it starts, the
  defaults the revision's `cptstudio/settings.py` gives them (the
  specification's: 25 US dollars and 4), so a figure moves by a change of that
  file in a release; it writes `CPT_STUDIO_CODING_EFFORT` as `max`, the owner's
  setting. The question stage's figures (`CPT_STUDIO_QUESTION_*`) are no longer
  written: an earlier revision's pair that a `switch-back` starts reads its own
  defaults for them, the values installers before the Fable coding build wrote.
- Blue/green residuals (the declaration states them):
  1. A request an old nginx worker accepted before the reload but proxies only
     after the drain has ended - in practice a large upload it is still reading
     from a slow client (the upload's `client_max_body_size 20m`; nginx connects
     upstream once the body is read) - reaches the stopped old port and answers
     503. The drain waits for no shutting-down nginx worker up to 600 s; an old
     worker can also be kept alive by a co-tenant's long-lived connection
     (`nginx.conf` sets no `worker_shutdown_timeout`), and then the drain ends
     at 600 s with `bounded_out`.
  2. Static files are served by WhiteNoise under hashed names: a page whose
     HTML came from the old web just before the switch may ask for an old-hash
     file the new image lacks (404) and needs a reload.
  3. A tab opened before the switch keeps running the old `app.js` against the
     new API until it is reloaded; the new API's response shapes must stay
     tolerant of it for one release.
  4. Processing pauses for the old worker's remaining stage time (up to
     3,600 s; about a second when idle) plus the switch; uploads are accepted and
     shown as queued.
  5. `systemctl reload nginx` is host-global. It is graceful, and the switch's
     verification requires co-tenant routing and app.quillmd.com unchanged
     from the preflight baseline - read before anything starts and again right
     before the vhost changes (and before `switch-back` closes anything), so a
     co-tenant deploy since `preflight` refuses the phase rather than failing
     the switch after nginx moved: run `preflight` again. A deploy inside the
     switch's own seconds still fails it, and is undone. The app phase therefore
     runs the two `sudo -n` nginx commands, which the declaration must say.
  6. The vhost file changes on every install (its sha256 alternates with the
     port), so declarations name the expected sha256 instead of listing
     `quillmd-cpt` under "must not change".
  7. During the drain the new web lists the stored states as the old revision
     derived them; they are recomputed once the old web has stopped.
  8. The undo of S3 and S4, and `switch-back`'s second close, close every
     coding job still open, whichever web queued it (a job carries no record
     of the web that queued it): a member's upload on this revision's web in
     those seconds or minutes is closed with the installer's note - its round
     reads stopped, and a Resume continues it once this revision serves again.
     A stage a member started on the earlier web in that window is of a kind
     the earlier worker runs, and is left to it (before the Fable coding build
     every stage queued in the window was failed and had to be started again).
     Nothing is sent wrongly; over-closing is the safe side.
  9. An installer older than this one knows only port 9150: its `app` stops the
     web and starts the next one on 9150, and its `verify` expects the 9150
     rendering. A first blue/green install moves 9150 to 9151 and its
     `switch-back` returns to 9150, which an older installer can follow; after a
     second one (9151 to 9150), a `switch-back` lands the previous revision on
     9151, and that revision's own `app` would then take the site down (the
     vhost names 9151, its new web listens on 9150) - install forward with a
     blue/green installer instead.
  10. A `deploy/nginx/` change between revisions cannot ride the switch: `app`
      refuses it. Since release 2 of the admin move the republish is
      `https-vhost`'s in-place replace between two stages that both name
      admin.quillmd.com, so nothing is taken down; a change that would stop
      naming admin cannot be published so (it would need its own two-file act,
      as `ingress-rollback` is).
  11. Which configuration nginx runs is read from `/proc`: the host master's
      worker processes (its pid file names it). An undo that cannot read them,
      or cannot prove a reload applied, treats nginx as possibly running the
      switched file, keeps both webs and parks the worker (half way) rather than
      remove a web nginx may route to; a same-revision switch whose new workers
      are not seen fails S3. A worker that nginx respawns after a crash, inside
      the seconds of a reload it refused, would read as applied.
  12. A record only a revision since the core repair writes (a member's
      answer, a chosen modifier) that was written after an undo's first close -
      in the seconds before the switch back's reload, or in a request the
      incoming web finished during the drain - is handed to the old web, which
      shows it wrongly, if it is a revision before the core repair, until this
      revision is installed again: the second close, which comes after the
      incoming web has stopped, names it and holds the old worker.
      `switch-back`'s B7 likewise.
  13. Which web wrote a member's answer or a chosen modifier is not recorded.
      An undo holds the old worker for one written in its window even when the
      old revision is one since the core repair, which reads it as this one does
      (and whose own web may have written it after the switch back): over-holding
      is the safe side, and the receipt says so and how to release it.
      `rollback-app` in the back layout holds for every one, whenever written:
      it did not run the install, and cannot tell whether the old worker ran
      beside one before it.
