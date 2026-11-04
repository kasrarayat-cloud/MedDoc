# Installing CPT Studio at cpt.quillmd.com

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
| database | container `cpt-studio-db` (postgres 17.11, pinned by digest), uid 70, all capabilities dropped, `127.0.0.1:55451`, volume `cpt-studio-pg` |
| web | container `cpt-studio-web`, gunicorn, read-only root, uid 10150, `127.0.0.1:9150` or `127.0.0.1:9151` → 8000: a fresh host starts on 9150, and each install after it starts the incoming web `cpt-studio-web-next` on the other port and switches to it (blue/green, **app**), so the port alternates |
| worker | container `cpt-studio-worker`, read-only root, stop timeout 600 s (above a participant phase's 540 s tool-loop deadline, and the stale-stage sweep's 600 s bound), the only holder of the Corti credentials (live mode only) and of each harness participant's (that participant live only) |
| network | `cpt-studio-net` (bridge). Web and worker reach the database as `cpt-studio-db:5432` |
| files | volume `cpt-studio-files` at `/var/lib/cpt-studio` (originals, reference copies) |
| secrets | `/etc/cpt-studio/` root 0700: `app.env`, `db.env` (root 0600), `corti-credentials.env` (10150:10150 0400), `initial-credentials.json` (root 0600), `operator-credentials.json` (root 0600, the human platform operator's login, **operators**) |
| participant credentials (optional) | `/etc/cpt-studio/openai-credentials.env` (Astra) and `anthropic-credentials.env` (Fable), 10150:10150 0400, each copied from `/etc/cpt-studio-provider-sources/{openai,anthropic}.env` (root 0600 in a root 0700 directory) when the owner placed it; never part of the three-file set above |
| passages | the CMS passage files the revision commits under `studio/reference/data/`, imported into `PassageSource`/`ReferencePassage` |
| agent login | `/home/claude/.cpt-studio/agent-credentials.json` (0600, agent account only) |
| operator accounts | `ops-agent` (automated agent) and `platform-operator` (human): no workspace membership, an operator grant (`manage grant_operator`); the agent's login `/home/claude/.cpt-studio/ops-agent-credentials.json` (0600, top-level `username` and `password`) |
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
| 2 | `secrets` | — | creates `/etc/cpt-studio/` and its three files, once; copies each participant credentials source the owner placed, once |
| 3 | `image` | — | builds `cpt-studio:<sha12>` |
| 4 | `db` | — | network, two volumes, database container |
| 5 | `app` | `--provider-mode live --authorization-ref docs/foundation/rulings/2026-10-23-cpt-studio-gi.md` (or `--provider-mode disabled`); optional `--astra-mode live`, `--fable-mode live` (each `disabled` when not given; live needs `--authorization-ref`) and `--access-check` | migrations; web and worker containers - on a served site blue/green: the incoming web on the idle port, the worker handed over, the vhost's upstream switched (`nginx -t`, a graceful reload: the two `sudo -n` commands), the old web drained and stopped, an availability record of the public `/health/` in the receipt; with `--access-check`, one access check per live participant: one real coding request for Corti (after the OAuth token request its adapter sends first), one run of the tool loop (one request per exchange, at most `PARTICIPANT_MAX_EXCHANGES`, 4) for Astra and for Fable |
| 6 | `reference` | `--pfs-zip <abs> --pfs-retrieved-at <ISO> --mue-zip <abs> --mue-retrieved-at <ISO>` | reference copies in the files volume; two `ReferenceSource` imports |
| 7 | `passages` | — | each committed `studio/reference/data/` file imported (`PassageSource`, `ReferencePassage`); idempotent |
| 8 | `license-note` | — | CPT Studio's own licence note on each imported reference source (`ReferenceSource.license_note`): exactly the old text replaced by the corrected one, nothing else; idempotent |
| 9 | `provision` | `--owner-username <name>` (optional `--agent-username`, display names, `--reset-passwords`) | GI workspace, owner and agent accounts; credentials files |
| 9a | `operators` | optional `--reset-passwords` | the two platform-operator accounts (no membership), their grants and credentials files |
| 9b | `reassess` | `--encounter <id>` (1 to 20), optional `--dry-run` | each named encounter re-assessed from its retained responses (`manage reassess_retained`; nothing is sent) |
| 10 | `http-vhost` | — | `quillmd-cpt` (HTTP stage) + symlink; nginx reload |
| 11 | `cert` | — | lineage `cpt.quillmd.com` |
| 12 | `https-vhost` | — | `quillmd-cpt` replaced by the HTTPS stage; nginx reload |
| 13 | `verify` | — | nothing |

`switch-back` returns to the pair this revision's last successful `app` replaced
(its receipt's `replaced`; images are never removed) by the same switch in
reverse, so the site is never interrupted: see **Switching back**.
`rollback-app` removes the web and worker containers - the site is down from
that moment until a pair is installed again; prefer `switch-back` after a
successful `app`. (In the S4 keep layout `rollback-app` acts on the right containers
instead, with this revision's image, and the site stays served: see **Recovery
notes**. With a `cpt-studio-web-next` in any other layout, or a web and a worker
of different images, it refuses and stops nothing: which web serves, and whose
records to read, cannot be told from the names.) It keeps the database,
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
this installer's) and reloads nginx; the certificate lineage is kept.

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
  images, the Corti credentials source, Let's Encrypt state by path (live
  names, renewal-config hashes, account ids — key material is never opened)
  and that the ACME webroot is writable. It also records whether each harness
  participant's credentials source is there: one that is absent is not a
  problem (that participant stays disabled), but a sources directory that is
  not root 0700, or a source that is not a root 0600 regular file, is.
  Any problem fails the phase.
- **secrets** generates the Django key and database password inside the root
  helper; the values never leave it. The Corti file is copied byte-for-byte and
  only its four key NAMES are checked. A partial or altered set is refused, not
  repaired. Then, separately from that set (adding to it would read every
  existing install as partial), each harness participant's credentials source
  the owner placed is copied once, unread, byte for byte, through the root
  helper: `/etc/cpt-studio-provider-sources/openai.env` to
  `/etc/cpt-studio/openai-credentials.env` (Astra) and `anthropic.env` to
  `anthropic-credentials.env` (Fable), 10150:10150 0400, then read back. The
  sources directory is mounted (read-only) only once it is seen to be a root
  0700 directory, and each source is opened without following a link and must
  be a root 0600 regular file of at most 32,000 bytes. Only key NAMES are
  checked: `OPENAI_API_KEY` (and optionally `OPENAI_PROJECT`), or
  `ANTHROPIC_API_KEY` (and optionally `ANTHROPIC_WORKSPACE_ID`), each once and
  nothing else. Only those expected names are ever reported: a line setting any
  other key is counted, never echoed, since a key pasted without its name would
  otherwise be printed as one. Every check runs before anything is written, and
  any problem writes nothing for either participant. A copy already there must
  be the 10150:10150 0400 file and equal its source; one whose source was since
  removed is reported `present` with its source `absent`. A missing source is
  `not provided`: that participant can only be installed disabled. The receipt
  names each participant's state, whether its source is there and the expected
  key names found; no value leaves the helper.
- **image** first reads the revision's migrations (with `ast`; nothing is
  imported or run) and refuses, before building anything, any migration after
  0005 that is not additive for a pair that does not know it. 0005 is the leaf
  of 057a7d39, the oldest revision a rollback goes back to; `app` migrates while
  the previous pair still runs, a failed replacement restores that pair on the
  migrated schema, `rollback-app` hands an older pair the rows, and nothing is
  reversed. Accepted: a new table; a column that is nullable, has `db_default`,
  or whose database default the same migration's SQL sets (an older pair's
  insert names no such column); Django's own (non-unique) index, or any index on
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
  passed. 0006, 0007 and 0008 pass: 0007 adds `endpoint`, `requested_model`,
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
  revision label, user 10150, the baked release, English OCR data, a working
  `pdftoppm`, `manage check`, and that the WSGI application loads as the
  image's own user on a read-only root (this is what catches unreadable static
  files, which `manage check` does not).
- **db** is idempotent; an existing container must be ours, on the pinned
  image, loopback-only, `unless-stopped`.
- **app** (live mode) first loads the Corti credentials with the
  application's own loader, in the worker's mount layout, with no network:
  a file the worker could not use stops the phase before anything changes.
  Each harness participant given `live` (`--astra-mode live`,
  `--fable-mode live`; both need `--authorization-ref`, as Corti's live mode
  does) is checked the same way before anything changes: its copy in
  `/etc/cpt-studio/` must be the 10150:10150 0400 file the secrets phase writes
  (a missing source leaves none, and the participant can then only be installed
  disabled), and the application's own loader
  (`studio.participants.credentials.load_openai_credentials` or
  `load_anthropic_credentials`) must read it in the worker's mount layout with
  no network and the participant itself disabled. A refusal's error output is
  kept in the receipt directory only once a root helper has found no value
  from that file in it. The new web and worker are both given
  `CPT_STUDIO_ASTRA_MODE` and `CPT_STUDIO_FABLE_MODE` (`disabled` unless given
  `live`) and, for a live participant, `CPT_STUDIO_OPENAI_CREDENTIALS_FILE=/run/cpt-studio/openai-credentials.env`
  or `CPT_STUDIO_ANTHROPIC_CREDENTIALS_FILE=/run/cpt-studio/anthropic-credentials.env`;
  only the worker mounts the file there, read-only, and only for a live
  participant (the web builds requests, which needs no credentials, as with
  Corti). Every one-shot runs with Corti and both participants disabled, but
  the opt-in access check below.
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
  It migrates with a one-shot container first and refuses, before replacing
  anything, while the queue holds a stage this revision's worker has no handler
  for (queued, running, or cancelled as its encounter's latest stage, which a
  Resume would run again): a worker that claims one ends.
  **Blue/green** (the site stays served throughout; the receipt's `steps` time
  each step): **S1** the incoming web `cpt-studio-web-next` starts on the idle
  port and must answer `/health/` = `{status ok, service cpt-studio, data_mode
  synthetic-only, database ok, release <revision>}` there and serve its own
  sign-in page and every static file that page names (read-only GETs) - the
  old web still serves everything; **S2** the old worker is parked (`docker
  stop --time 600`: its current stage finishes, nothing new is claimed) - the
  old web still serves, and what members start waits in the queue; **S3** the
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
  for `/health/` as above and a worker that stays up. Once the new
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
  remove the parked pair (`*-previous`) by hand if it is left, then rerun `app`,
  which recomputes them; if they were, only the parked pair is left to remove.
  An installer killed outright writes no receipt: rerun `app` (see **Recovery
  notes**).
  With `--access-check` (opt-in: it needs a live participant, and never runs
  without the flag, because it sends a real request), once the new pair runs,
  its states are recomputed and the parked pair is removed, each live
  participant in turn - Corti first when `--provider-mode live`, then Astra and
  Fable - is checked once by
  `manage participant_access_check --participant <corti|astra|fable>`: one
  coding request for Corti (after the OAuth token request its adapter sends
  first), and for Astra or Fable one run of the pipeline's tool loop,
  one request per exchange and at most `PARTICIPANT_MAX_EXCHANGES` (4), whose
  receipt counts its exchanges. Each runs in a
  one-shot with the worker's mount and network for that participant: its
  credentials file read-only at the worker's path, `cpt-studio-net`, that
  participant live under the same `--authorization-ref`, every other one
  disabled, bounded at 420 s (the participant send deadline is 330 s). The
  command takes the installation-wide provider lock and sends nothing while
  another request holds it, which fails the check: let the queue drain (or Stop
  the encounters) before `app --access-check`. It writes nothing to the
  database. What the container wrote is recorded - its JSON receipt in this
  phase's receipt (`access_checks`), its stdout and the last 8 KiB of its
  stderr in a log - only once a root helper has found no value from that
  participant's credentials file in it (key names only come back from that
  helper); otherwise nothing it wrote is kept and the check fails. A check that
  exits non-zero, does not finish (whether its request reached the vendor is
  then not known) or writes no JSON receipt fails the phase. For a non-zero
  exit the phase repeats what the check's output says: the error its JSON
  receipt gives, else the last non-empty line of its stderr, each only whole
  and only up to 300 characters, and otherwise names it, never cut; with
  neither, it says there is no text on its stderr, and no JSON receipt when
  there is none. The installer adds no cause of its own. The phase then says
  that the pair stays installed with those participants live, that this phase's
  receipt records each check under `access_checks` (its JSON receipt, if it
  wrote one, and the path of its log, where what it wrote was recorded), and to
  run `app` again with `--access-check` once the cause is known, or install
  that participant disabled.
  **A blue/green step that fails, or is interrupted (Ctrl-C), never stops the
  serving web**; the receipt says what is left (`failed_at`, `left`: the port
  the vhost names and every CPT Studio container's state, port and image):
  - S1 (the incoming web is not healthy, or does not serve its pages): it is
    stopped and removed; nothing else changed and nothing is closed - no
    customer request reached it.
  - S2 (the old worker could not be parked): it runs again (park starts it
    when its rename fails); the incoming web is removed.
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
    left running and the old worker parked (a switch that stopped half way:
    **Recovery notes**). Every stage queued, run or left resumable since the file
    was replaced, and every open stage of a kind the old worker cannot run, is
    closed as failed (the new web may have served seconds of requests; this can
    also close what a member started on the old web in those seconds), and
    closed again once it has stopped taking traffic (the incoming web, drained,
    finished the requests it had accepted), the list states the old revision
    labels otherwise are put back after each close, the incoming web is removed,
    and the old worker is put back and started - held, as in the swap below,
    while either close names records it would act on under its own rules, or
    records only this revision's web writes (a member's answer, a reviewer's
    chosen modifier - no worker makes either, and no revision before the core
    repair can, so the new web wrote them while it served: the old web shows
    them wrongly, and its worker's re-assessment would drop a chosen modifier).
    A state the old web would merely show wrongly that a worker made (a second
    review's, a harness participant's) is named in the receipt only: the old
    web never stopped showing it, and no new worker ran.
  - S4 (the new worker is not ready): it is stopped and what the new pair
    started is closed. When the close names a state the old web would show
    wrongly whatever it is handed (**second_review_refused**,
    **second_review_unread**, **participant**) and the old pair is another
    revision, the NEW web keeps serving (it shows them correctly), its worker
    stopped and the old worker parked: nothing is processed until a person
    decides (**Recovery notes**). Otherwise the states are put back and the
    upstream is switched back the same way (graceful reload, `/health/` = the
    old revision), the incoming web is drained, what the new web started is
    closed again once it has stopped taking traffic (it took every request until
    the switch back's reload, and finished those in flight during the drain),
    the states are put back again, the incoming web is removed with the new
    worker, and the old worker is put back and started - or held, while either
    close names records it would act on, or the second one a state the old web
    shows wrongly (the new web wrote it after the first close: a member's
    answer, a chosen modifier; the receipt names it). A close, put-back or
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
  alone holds the Corti credentials, so nothing can be sent - and the receipt
  names the encounters: install this revision again once its failure is fixed
  (its worker reads those records under its own rules). If the stages cannot be
  closed, or those states cannot be put back, the new pair is left stopped and
  the parked pair parked (the receipt says so): run `rollback-app`, then rename
  the parked pair back. Migrations already applied are not reversed.
- **Work in flight at the switch** (or the swap) is not frozen: a stage the
  previous pair queued or left running is finished by the new pair under the
  new rules, and nothing is sent that no member asked for. In blue/green the old
  worker stops (S2) before the new web takes traffic (S3) and the new worker
  starts only once it has exited (S4): no worker of the old code claims a stage
  the new web queued, and the two workers never run together. What members
  start between S2 and S4 waits in the queue (the old worker's remaining stage
  time, about a second when idle, up to 600 s), far inside the 30 minutes a
  queued stage waits. A predict the previous pair queued
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
- **provision** writes both credentials files only after the accounts exist
  with the generated passwords; an account that already existed (password
  unchanged) aborts and discards them unless `--reset-passwords` was given.
  Passwords travel as RAM-only files under `/dev/shm`, never argv or output.
- **operators** (after `app`; it needs the revision's operator grant, owner
  directive 2026-11-03 section 2, and refuses - creating no account and no file -
  unless `manage migrate --check` passes with this revision's image) creates the
  two platform-operator accounts
  as `provision` creates its own: passwords generated by the installer,
  travelling only as RAM-only files under `/dev/shm` into one-shots of this
  revision's image (never argv, output or receipts), the human's login staged
  and committed through the root helper. `ops-agent` (an automated agent: the
  verification tools' operator session) and `platform-operator` (a human) get
  NO workspace membership - an operator's access is its grant, never a role -
  and an account of either name that exists with another actor kind or holds
  any membership is refused, changing nothing. Once both accounts hold their
  passwords, `/home/claude/.cpt-studio/ops-agent-credentials.json` (0600,
  top-level `username` and `password`) and the root-only 0600
  `/etc/cpt-studio/operator-credentials.json` are committed; each account is
  then granted by the application's own command, `manage grant_operator
  --username <name> --reason-file <file> --by <who>` (the reason names the
  directive, the revision and the declaration; `--by` names this installer and
  the host login that ran it, given explicitly because the one-shot runs as this
  user's uid, which the image has no passwd entry for - the command's own
  default reads the login from the environment, else names the uid, and never
  looks it up), and read back: an active operator
  (`studio.operator.is_operator`) with no membership. Files already there
  refuse unless `--reset-passwords`, which rotates both. A grant that fails
  leaves the accounts and their files in place: rerun with `--reset-passwords`
  once it is fixed.
- **reassess** (after `app`) re-assesses each named encounter from what is
  already recorded: one one-shot per encounter (provider and participants
  disabled) runs the application's `manage reassess_retained --encounter <id>
  --tag <revision>`, which queues the re-assessment of the retained responses
  and never sends; `--dry-run` is passed through and queues nothing. It refuses
  unless this revision's migrations are applied and every named encounter
  exists. Each encounter's jobs are read before and after, so the receipt names
  the jobs that appeared (as measured, not as the command said), its states
  before and after, the command's JSON answer and its log; a dry run after
  which a job appeared fails the phase, and a command that fails stops the
  phase, naming the encounters it ran for before.
- **http-vhost / https-vhost / rollback-vhost** validate with
  `sudo -n /usr/sbin/nginx -t`, refuse any new nginx warning, reload with
  `sudo -n /usr/bin/systemctl reload nginx`, then probe with bounded retries
  (reloads are asynchronous). Any failed check restores the exact previous
  file state, validates and reloads again. Co-tenant routing and app health
  must equal the preflight baseline. A stage this installer writes is the HTTP
  stage or the HTTPS stage for either web port (`cert`, `rollback-vhost` and
  `verify` accept any of the three); `https-vhost` renders the HTTPS stage for
  the port the running `cpt-studio-web` publishes (9150 on a fresh host), and
  refuses an HTTPS stage for the other port.
- **cert** requires exactly one existing ACME account and passes it with
  `--account`; certbot gets no `--agree-tos` or e-mail, so it cannot register
  one. Other lineages' renewal configs must be byte-identical afterwards.
- **verify** compares everything with the preflight receipt and checks the
  deployed containers' hardening and the HTTPS headers, including that a
  request whose SNI is not `cpt.quillmd.com` is closed (444). `quillmd-cpt` must
  be this revision's HTTPS stage for the port the running web publishes (it
  alternates), and nothing an `app` parks or starts (`cpt-studio-web-next`,
  `*-previous`) may be left beside the pair. The containers'
  check (also run as each starts in `app`) includes their bind mounts: the web
  holds none, and the worker only the credentials files, read-only, at their
  worker paths.

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
and `verify` reports the vhost as different: republish with `rollback-vhost`,
`http-vhost`, `cert` (a no-op for a lineage not yet due for renewal; it records
the receipt `https-vhost` requires) and `https-vhost` under the new declaration
- which takes the site down between the removal and the HTTPS stage (see
**Known limits**).
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

`--phase switch-back --provider-mode <mode> [--astra-mode …] [--fable-mode …]
[--authorization-ref …]` runs under this revision's declaration and installer
(an older installer cannot switch: `check_tree` binds a phase to its own
revision) and returns to the pair this revision's last successful `app`
replaced - its receipt's `replaced`, whose image is still present - with the
modes given (the previous pair's, as its own `app` was given them; the
credentials files are checked with the previous image's own loaders). It
refuses, starting nothing, unless this revision's web serves the site through
its HTTPS stage, and while this revision recorded what an older revision would
act on, or show, wrongly (`rollback-app`'s check: **Reinstalling an older
revision**). Then, without ever stopping the serving web first: **B2** the
previous image's web starts as `cpt-studio-web-next` on the idle port and must
answer `/health/` with ITS revision and serve its pages; **B3** this revision's
worker is parked; **B4** every stage this revision's pair queued, ran or left
resumable since it was created, and every open stage of a kind the previous
worker does not run, is closed (as `rollback-app` closes them; let the queue
drain first), the switch-back refusing to go on while the close names a
record, and the list states the previous revision labels otherwise are put
back - and before that close, the baseline and this revision's records are read
again, so nothing is closed for a switch that cannot pass or would refuse;
**B5** the upstream is switched to the idle port (`/health/` = the previous
revision; a reload of the switched file that was asked for and then failed is
treated as applied, as in `app`: nginx is reloaded with this revision's vhost
again and must be proven to run it before the previous web is drained and
removed, and both webs are left running otherwise); **B6** this revision's web
is drained, stopped and parked;
**B7** the close runs again for what this revision's web started between B4 and
the end of its drain - which also closes what a member started on the previous
web during that window (**Known limits**) - and the previous worker is held
while it names a record (one only this revision's web writes - a member's
answer, a chosen modifier - was written by it before it stopped taking traffic:
the previous web shows it wrongly, and the receipt says so; `app` again comes
back to this revision); **B8** the previous worker starts; **B9** this
revision's parked pair is removed (its image is kept). Before B5 any failure
resumes this revision's pair (its worker started again, its list states
recomputed with its own derivation, the previous web drained when it took
traffic and removed); from B5 on the previous web serves and the receipt says
what is left. The availability record runs from B2 to the end. To come back to
this revision, run `app` again.

## Reinstalling an older revision

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
  gave it. Named, never handed over; the answer row stays.
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
  names the old web's port, nothing is routed to the incoming web: once it has
  no connection, stop and remove it, put the old worker back if it is parked
  (`docker rename cpt-studio-worker-previous cpt-studio-worker`, `docker
  start` it), and rerun `app`. If the vhost names the incoming web's port, the
  new web serves: start the new worker if none runs (`app` again does it all),
  or stop and remove what is left of the old web only once it has no
  connection. `app` and `preflight` refuse while a `-next` exists.
- An installer killed outright inside S3 writes no receipt and runs no undo.
  If it was killed after the file was replaced but before nginx reloaded, nginx
  still serves the old web on the old configuration - but the file names the
  incoming web's port, so the next reload by anyone (the TLS renewal deploy
  hook included) moves traffic there, possibly with the old worker parked and
  no new worker. Both webs are still running, so either way the site stays
  served; recover at once: read the file's port and the containers, then either
  complete (start the new worker: rerun `app` once the leftovers are resolved)
  or put the vhost bytes back (`rollback-vhost` is not for this: restore the
  rendering for the old port through the root helper, reload, and put the old
  worker back).
- An S4 failure whose close named a shown state leaves the S4 keep layout: the
  NEW web serving as `cpt-studio-web-next`, its worker stopped as
  `cpt-studio-worker`, the old worker parked and the old web running on the old
  port with no traffic. To keep this revision: fix the worker's failure, remove
  the old web and the parked worker, rename `-next` to `cpt-studio-web`, then
  rerun `app` (a same-revision switch, which starts the worker and recomputes
  the states). To go back: clear the named records on this web first
  (**Reinstalling an older revision**), run `preflight` again, then run this
  revision's `rollback-app`. In the S4 keep layout `rollback-app` acts on the
  right containers - this revision's web and worker, with this revision's
  image - and the site stays served: it refuses, changing nothing, while this
  revision recorded what an older revision would act on or show wrongly, or
  while the baseline no longer holds; otherwise it closes every stage this
  revision's pair started since its incoming web was created (and every open
  stage of a kind the old worker cannot run), stopping there if that close
  names a record, puts back the list states, switches the upstream back to the
  old web (graceful, `/health/` = its revision), drains this revision's web,
  closes again, removes this revision's web and worker, and puts the old worker
  back - held while a close names a record. Do not remove the old web by hand:
  it is what `rollback-app` switches back to.
- Staged `.initial-credentials.json.new` / `.agent-credentials.json.new` from an
  interrupted `provision`, or `.operator-credentials.json.new` /
  `.ops-agent-credentials.json.new` from an interrupted `operators`: delete them
  (no account uses their passwords unless the receipt says the accounts were
  created) and rerun.
- Rotating the two passwords: `--phase provision --owner-username … --reset-passwords`.
- Rotating a harness participant's key: the owner replaces its source; remove
  `/etc/cpt-studio/openai-credentials.env` (or `anthropic-credentials.env`) by
  hand (root), run `secrets`, which copies the new source, then `app` with the
  same modes: the running worker's mount holds the file it was started with.
  `secrets` refuses a copy that differs from its source rather than replace it.
- A staged `.openai-credentials.env.new` / `.anthropic-credentials.env.new` in
  `/etc/cpt-studio/` from an interrupted `secrets`: delete it by hand and rerun;
  `secrets` refuses while one exists.
- An `app` whose access check failed left the pair installed and running with
  those participants live (the receipt says so; what it could record of each
  check is under `access_checks`): rerun `app` with `--access-check` once the
  cause is known, or with that participant disabled.

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
- The installer reads a participant's credentials by key NAME only; whether a
  key works is known only from the opt-in access check (for each live
  participant: one real, paid coding request for Corti, and for Astra and for
  Fable one run of the tool loop, one real, paid request per exchange and at
  most `PARTICIPANT_MAX_EXCHANGES` (4)), or from the first live send. A check
  that fails leaves the pair installed: retrying it means running `app` again,
  which switches to a new pair beside the running one.
- The scan that keeps credential values out of receipts and logs matches each
  value as written, unquoted and without an inline comment, and does not match
  values under 8 characters (they would match by chance), nor a value
  transformed (encoded, or partly printed). It reads only the checked
  participant's file.
- The worker's stop timeout (600 s) covers a participant phase's whole tool
  loop (deadline 540 s: at most four exchanges; one send's deadline is 330 s)
  and equals the stale-stage sweep's bound (`STALE_RUNNING_SECONDS`, 600 s),
  not every whole stage: a stage still running when the 600 s pass is killed
  with the worker and settled as any stage cut short (the stale-stage sweep, or
  an undo's close). Parking or removing a worker that is inside a loop waits up
  to that long, so a stop in `app` or `rollback-app` can take up to ten
  minutes: let the queue drain (or Stop the encounters) first to avoid the
  wait. In blue/green the site stays served meanwhile, and that wait is the
  processing pause: what members start is accepted and shown as queued.
- Blue/green residuals (the declaration states them):
  1. A request an old nginx worker accepted before the reload but proxies only
     after the drain has ended - in practice a large upload it is still
     reading from a slow client (`client_max_body_size 20m`; nginx connects
     upstream once the body is read) - reaches the stopped old port and
     answers 503. The drain waits for no shutting-down nginx worker up to 600 s;
     an old worker can also be kept alive by a co-tenant's long-lived
     connection (`nginx.conf` sets no `worker_shutdown_timeout`), and then the
     drain ends at 600 s with `bounded_out`.
  2. Static files are served by WhiteNoise under hashed names: a page whose
     HTML came from the old web just before the switch may ask for an old-hash
     file the new image lacks (404) and needs a reload.
  3. A tab opened before the switch keeps running the old `app.js` against the
     new API until it is reloaded; the new API's response shapes must stay
     tolerant of it for one release.
  4. Processing pauses for the old worker's remaining stage time (up to 600 s;
     about a second when idle) plus the switch; uploads are accepted and shown
     as queued.
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
  8. The undo of S3 and S4, and `switch-back`'s second close, close what was
     started in their window whichever web started it (stages carry no record
     of the web that queued them): a member's upload in those seconds or
     minutes is failed with the installer's note and must be started again.
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
      refuses it and the republish (`rollback-vhost` … `https-vhost`) takes the
      site down between the removal and the HTTPS stage.
  11. Which configuration nginx runs is read from `/proc`: the host master's
      worker processes (its pid file names it). An undo that cannot read them,
      or cannot prove a reload applied, treats nginx as possibly running the
      switched file, keeps both webs and parks the worker (half way) rather than
      remove a web nginx may route to; a same-revision switch whose new workers
      are not seen fails S3. A worker that nginx respawns after a crash, inside
      the seconds of a reload it refused, would read as applied.
  12. A record only this revision's web writes (a member's answer, a chosen
      modifier) that it wrote after an undo's first close - in the seconds
      before the switch back's reload, or in a request it finished during the
      drain - is handed to the old web, which shows it wrongly until this
      revision is installed again: the second close names it and holds the old
      worker. `switch-back`'s B7 likewise.
