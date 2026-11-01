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
| web | container `cpt-studio-web`, gunicorn, read-only root, uid 10150, `127.0.0.1:9150` → 8000 |
| worker | container `cpt-studio-worker`, read-only root, stop timeout 360 s, the only holder of the Corti credentials (live mode only) and of each harness participant's (that participant live only) |
| network | `cpt-studio-net` (bridge). Web and worker reach the database as `cpt-studio-db:5432` |
| files | volume `cpt-studio-files` at `/var/lib/cpt-studio` (originals, reference copies) |
| secrets | `/etc/cpt-studio/` root 0700: `app.env`, `db.env` (root 0600), `corti-credentials.env` (10150:10150 0400), `initial-credentials.json` (root 0600) |
| participant credentials (optional) | `/etc/cpt-studio/openai-credentials.env` (Astra) and `anthropic-credentials.env` (Fable), 10150:10150 0400, each copied from `/etc/cpt-studio-provider-sources/{openai,anthropic}.env` (root 0600 in a root 0700 directory) when the owner placed it; never part of the three-file set above |
| passages | the CMS passage files the revision commits under `studio/reference/data/`, imported into `PassageSource`/`ReferencePassage` |
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
| 2 | `secrets` | — | creates `/etc/cpt-studio/` and its three files, once; copies each participant credentials source the owner placed, once |
| 3 | `image` | — | builds `cpt-studio:<sha12>` |
| 4 | `db` | — | network, two volumes, database container |
| 5 | `app` | `--provider-mode live --authorization-ref docs/foundation/rulings/2026-10-23-cpt-studio-gi.md` (or `--provider-mode disabled`); optional `--astra-mode live`, `--fable-mode live` (each `disabled` when not given; live needs `--authorization-ref`) and `--access-check` | migrations; web and worker containers; with `--access-check`, one real request per live participant |
| 6 | `reference` | `--pfs-zip <abs> --pfs-retrieved-at <ISO> --mue-zip <abs> --mue-retrieved-at <ISO>` | reference copies in the files volume; two `ReferenceSource` imports |
| 7 | `passages` | — | each committed `studio/reference/data/` file imported (`PassageSource`, `ReferencePassage`); idempotent |
| 8 | `provision` | `--owner-username <name>` (optional `--agent-username`, display names, `--reset-passwords`) | GI workspace, owner and agent accounts; credentials files |
| 9 | `http-vhost` | — | `quillmd-cpt` (HTTP stage) + symlink; nginx reload |
| 10 | `cert` | — | lineage `cpt.quillmd.com` |
| 11 | `https-vhost` | — | `quillmd-cpt` replaced by the HTTPS stage; nginx reload |
| 12 | `verify` | — | nothing |

`rollback-app` removes the web and worker containers; it keeps the database,
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
otherwise one that runs extract, analyze, predict and assess only. Either way
the harness participants' stages (kinds `astra` and `fable`) are closed: no
revision before the harness (80df1831d168 and older) has a stage for them, so
they are closed like a second review's, as failed, with the installer's message
naming the revision (no web offers a Resume for them). If the stages
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
  `scripts/check-cotenants.sh`, containers, volumes, networks, ports 9150 and
  55451, DNS (A `147.189.172.8` only, no AAAA), the pinned helper and postgres
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
  insert names no such column); an index; a constraint on a new table; SQL that
  only sets column defaults. Anything else (a removed, renamed or altered column
  or table, a constraint on an existing table, `RunPython`, other SQL, a form the
  check does not read, a file in the migrations directory that is not a
  migration) is refused. The receipt records each checked migration and why it
  passed. 0006 and 0007 pass: 0007 adds `endpoint`, `requested_model`,
  `returned_model` and `response_id` to `studio_providerrun` and `participants`
  and `retrieval` to `studio_assessment`, each NOT NULL and each given a
  database default by the same migration's SQL, and creates `PassageSource` and
  `ReferencePassage`, tables no older revision reads. So the previous pair keeps
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
  It then migrates with a one-shot container and refuses, before replacing
  anything, while the queue holds a stage this revision's worker has no handler
  for (queued, running, or cancelled as its encounter's latest stage, which a
  Resume would run again): a worker that claims one ends. It then parks the
  current web/worker (`*-previous`), starts the new pair and waits for
  `/health/` = `{status ok, service cpt-studio, data_mode synthetic-only,
  database ok, release <revision>}` and a worker that stays up. Once the new
  pair runs - and before the parked pair is removed - every encounter's stored
  list state is recomputed with this revision's derivation (only a changed one
  is written; nothing is sent; the receipt names each that changed): the
  revision replaced may have derived it otherwise (an unreconciled unknown
  outcome it listed as reviewed is on this revision's review queue; a response
  refused whole it listed as 'No CPT codes proposed'), and an action on the
  encounter is otherwise the only thing that recomputes it. A provider outcome
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
  Fable - is sent ONE request by
  `manage participant_access_check --participant <corti|astra|fable>`, in a
  one-shot with the worker's mount and network for that participant: its
  credentials file read-only at the worker's path, `cpt-studio-net`, that
  participant live under the same `--authorization-ref`, every other one
  disabled, bounded at 420 s (the participant send deadline is 330 s). The
  command takes the installation-wide provider lock and sends nothing while
  another request holds it, which fails the check: let the queue drain (or Stop
  the encounters) before `app --access-check`. It writes nothing to the
  database. What the container wrote is recorded - its JSON receipt in this
  phase's receipt (`access_checks`), everything in a log - only once a root
  helper has found no value from that participant's credentials file in it
  (key names only come back from that helper); otherwise nothing it wrote is
  kept and the check fails. A check that exits non-zero, does not finish
  (whether its request reached the vendor is then not known) or writes no JSON
  receipt fails the phase, which then says the pair stays installed with those
  participants live: fix the credentials or the vendor account and run `app`
  again with `--access-check`, or install that participant disabled.
  On any failure before the new pair runs, the recompute does not run: the new
  pair is stopped and, before the parked pair is restored, every stage
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
- **Work in flight at the swap** is not frozen: a stage the previous pair
  queued or left running is finished by the new pair under the new rules, and
  nothing is sent that no member asked for. A predict the previous pair queued
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
  request whose SNI is not `cpt.quillmd.com` is closed (444). The containers'
  check (also run as each starts in `app`) includes their bind mounts: the web
  holds none, and the worker only the credentials files, read-only, at their
  worker paths.

## Reinstalling a new revision

Commit a declaration naming the new revision, then run `preflight`, `image`,
`app`, `passages`, `verify`. `secrets`, `db`, `reference`, `passages` and
`provision` are idempotent or refuse rather than repeat. A harness participant
credentials source placed since the last `secrets` is copied by running
`secrets` again (the three-file set reads `present`) before `app`. If `deploy/nginx/` changed between the revisions,
`verify` reports the vhost as different: republish with `rollback-vhost`,
`http-vhost`, `cert` (a no-op for a lineage not yet due for renewal; it records
the receipt `https-vhost` requires) and `https-vhost` under the new declaration.
`rollback-vhost` removes a stage an earlier successful vhost receipt recorded
(its digest), and a failed removal is restored to exactly the bytes that were
live. A reinstall must therefore use the receipts directory of the install whose
stage is live (or copy its vhost receipts into the new one): without the receipt,
the stage is not provably this installer's and `rollback-vhost` refuses. `verify` compares the other
Let's Encrypt lineages only; this domain's own lineage may already be in the
reinstall's preflight baseline.

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
- a stage of a kind it has no stage for (the second review; the harness
  participants' `astra` and `fable`, which no revision before the harness
  runs), queued, running, or stopped as the latest: its worker ends on it.

`rollback-app` closes the last as failed, and refuses, naming the encounters,
while any of the first seven exists. They are cleared on this revision's web:
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
stays installed. So,
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
`independent`) are no run of 80df1831d168's own (its run in use is a primary
run); 057a7d39 takes the newest finished run of any kind as its run in use, so a
participant run can be it: its metadata save then re-predicts, reusing Corti's
retained answer to an unchanged request (nothing is sent), and a failed request
it would send again is **outcome**, named above. An unknown outcome of a
participant run is **unknown**. The runs' endpoint, models and response id, the
assessment's participants and retrieval, and the passage tables are columns and
tables no older revision reads (migration 0007 gives each column a database
default). Encounter list states stay as this revision last derived them until an
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
- Staged `.initial-credentials.json.new` / `.agent-credentials.json.new` from an
  interrupted `provision`: delete them (no account uses their passwords unless
  the receipt says the accounts were created) and rerun.
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
  those participants live (the receipt says so): rerun `app` with
  `--access-check` once the credentials or the vendor account are fixed, or
  with that participant disabled.

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
- The installer reads a participant's credentials by key NAME only; whether a
  key works is known only from the opt-in access check (one real, paid request
  per live participant, Corti included), or from the first live send. A check
  that fails leaves the pair installed: retrying it means running `app` again,
  which parks and replaces the pair.
- The scan that keeps credential values out of receipts and logs matches each
  value as written, unquoted and without an inline comment, and does not match
  values under 8 characters (they would match by chance), nor a value
  transformed (encoded, or partly printed). It reads only the checked
  participant's file.
- The worker's stop timeout (360 s) covers a participant send (deadline 330 s),
  not every whole stage: a stage still running when the 360 s pass is killed
  with the worker and settled as any stage cut short (the stale-stage sweep, or
  an undo's close).
