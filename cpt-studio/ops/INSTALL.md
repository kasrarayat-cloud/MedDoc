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
otherwise one that runs extract, analyze, predict and assess only. If the stages
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
  is handed - a bounded second review's response refused whole, or a second
  review left unread (**second_review_refused**, **second_review_unread**,
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
failure path of `app` read them as it reads the rows):

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
- a stage of a kind it has no stage for (the second review), queued, running,
  or stopped as the latest: its worker ends on it.

`rollback-app` closes the last as failed, and refuses, naming the encounters,
while any of the first six exists. They are cleared on this revision's web:
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
revision stays installed. So,
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
above). Encounter list states stay as this revision last derived them until an
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
