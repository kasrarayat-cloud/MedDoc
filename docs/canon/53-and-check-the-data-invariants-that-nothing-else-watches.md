> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **115 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know ▸ Close-out hygiene — reap the scratch, every session**.
> Why the split: `docs/canon/README.md`.

### And check the data invariants that nothing else watches

Scratch is not the only thing a session can leave behind. Some defects write a
COLUMN, and no sweep of the filesystem will find them.

```bash
bash scripts/check-imaging-em-artifacts.sh    # READ-ONLY. 0 = clean, 1 = found, 2 = off-host
bash scripts/check-em-note-shape-artifacts.sh # READ-ONLY. 0 = clean, 1 = FOUND, 2 = can't tell
bash scripts/assert-migrations-applied.sh     # READ-ONLY. 0 = all applied, 1 = UNAPPLIED, 2 = off-host
bash scripts/assert-migrations-applied.sh --qa # READ-ONLY. same, against the QA stack
bash scripts/check-qa-mock-posture.sh         # READ-ONLY. 0 = severed, 1 = LIVE KEYS, 2 = stack down
bash scripts/check-minio-encrypted-mount.sh   # READ-ONLY. 0 = encrypted, 1 = DRIFT, 2 = can't tell
bash scripts/check-pg-encrypted-mount.sh      # READ-ONLY. 0 = encrypted, 1 = DRIFT, 2 = can't tell
bash scripts/check-ingress-tls.sh             # READ-ONLY. 0 = all SNIs OK, 1 = 502ing, 2 = can't tell
bash scripts/check-composite-fk.sh            # READ-ONLY. 0 = intact, 1 = ABSENT/RESHAPED, 2 = can't tell
bash scripts/check-bind-mount-agreement.sh    # READ-ONLY. 0 = agrees, 1 = DIVERGED, 2 = can't tell
bash scripts/check-hooks-installed.sh         # READ-ONLY. 0 = hooks live, 1 = INERT, 2 = can't tell
bash scripts/check-cotenants.sh               # READ-ONLY. 0 = expected, 1 = DIVERGED, 2 = can't tell
bash scripts/check-claude-cli.sh              # READ-ONLY. 0 = usable, 1 = BROKEN pair, 2 = can't tell
```

⚠️ **THE TWO E/M WATCHERS COVER TWO DIFFERENT AXES, AND NEITHER IS A WIDENING
OF THE OTHER.** `check-imaging-em-artifacts.sh` is `where specialty='ultrasound'`
— the SPECIALTY axis. `check-em-note-shape-artifacts.sh` (F12-g) watches the
NOTE-SHAPE axis, ruling #123's second axis, which is **entirely outside the
first's watched set**: a GI doctor does office visits AND colonoscopies under one
specialty id, so no specialty predicate can separate them.

> **The imaging watcher's 🟢 is TRUE and covers none of the note-shape rows.
> Measured 2026-08-19: it read `0 of 20` on the same day the note-shape watcher
> read `15`, and all 15 are `axis=note-shape`, `0` are `axis=specialty`.** The
> two do not overlap today, and that is a measurement rather than an assumption
> — the scan reports which axis suppressed each row precisely so the claim stays
> checkable.

The note-shape watcher runs the **shipped** `emAppliesToVisit`; it never
re-implements it. F12-g's own filing records the cost of the alternative: an SQL
re-implementation with the specialty axis approximated answered **19** where the
shipped predicate answers **15**, and the 19 reached a ledger row before anyone
caught it. It also never reads a note BODY — the extract emits only heading
lines, filtered by a strict prefix of `NOTE_SECTION_HEADING_RE`, and the scanner
asserts on every run that nothing else came through.

⚠️ **IT REPORTS; IT NEVER REMEDIATES, AND THE THREE CLASSES IT FINDS ARE NOT ONE
FINDING.** A computed `emScoredCode`, a DOCTOR-SET `cptCodes.em.override.code`,
and a FROZEN `signedCode` on a signed record need three different decisions —
clearing the second deletes somebody's recorded clinical judgement, and the
third is never touched. Remediation goes through
`scripts/run-ruled-mutation.sh` with its own §2.5 declaration; the disposition is
a war-room question.

⚠️ **AND THE LOOP CANNOT INVOKE IT BY NAME UNTIL AN OWNER GRANTS IT.**
`.claude/settings.json` names permitted scripts one by one and is protected from
the layer it governs, so the session that wrote the script **could not ship its
own grant** — canon's *"an entry that names an instrument verifies that
instrument's grant in the same commit"* is structurally unreachable from the
unattended side. The granted fallback is documented in the script's own header
and is the route the 2026-08-19 measurement actually used. **Do not tunnel the
refused file through `node -e` or `python3 -c`.**

⚠️ **`check-cotenants.sh` CARRIES AN EXPECTED STATUS PER HOST, AND ONE OF THEM
IS A `410`.** `pro.quillmd.com` is DELIBERATELY RETIRED — the `meddoc-pro` CRM
container was stopped with SIGTERM (`Exited (143)`) and Caddy answers Gone. It
went unwatched for eleven days, and when a post-deploy sweep finally saw the
410 nobody could say whether it was new; establishing it took reading container
state.

> **The cure for an unwatched surface is not "watch it" — it is "watch it WITH
> THE RIGHT ANSWER".** A check demanding 2xx/3xx would go red on a deliberate
> retirement; a check accepting anything would go green on a **502 wearing the
> retirement's place**. So the expected code is declared per host with its
> reason, and a change AWAY from 410 is the finding.

⚠️ **AND ITS DISCRIMINATION CONTROL IS DERIVED FROM THE TABLE, NOT A CONSTANT.**
The first draft hardcoded "at least 3 distinct codes", which is arbitrary: it
does not scale when a host is added and it cannot tell a legitimate
single-divergence from a flat ingress. **Mutation-proved it and the control did
NOT fire** — removing a host left 3 distinct codes and it passed. The floor is
now `distinct(expected) - 1`, so an ingress answering every host identically
exits `2` while one genuine divergence still exits `1` and is reported.

⚠️ **`--qa` IS A SEPARATE LINE BECAUSE A CAPABILITY NOBODY INVOKES IS
INDISTINGUISHABLE FROM ONE THAT DOES NOT EXIST.** `assert-migrations-applied.sh`
has accepted `[container] [db]` since it was written, so pointing it at QA never
needed a line of code — and for three months nothing ever did. The standing
check ran bare, bare means production, and the QA stack drifted **two**
migrations behind (`b1a_ai_calls_request_id`, `b3_price_table`) with every
session reporting `assert-migrations-applied 🟢`. The instrument was never
broken and never wrong; it was simply never aimed at half of what its green was
read to cover. **That green was true and worthless** — the watched-set failure,
arriving through a parameter default rather than a model list.

⚠️ **AND THE BARE INVOCATION STAYS PROD-ONLY, DELIBERATELY.**
`scripts/deploy-prod.sh:118` gates the production deploy on it. Folding QA into
that call would let a stale synthetic container **block shipping** — so the QA
arm is a flag, and the two callers keep their two different questions. *Diff the
callers before you widen a shared thing;* the widening that reads as obviously
harmless is the one with a deploy gate on the other end.

⚠️ **AND THE `--qa` GREEN COVERS THE DATABASE, NOT THE IMAGES — THE SAME FAILURE
ONE LAYER OUT, AND THE FIX FOR THE FIRST ONE IS WHAT HIDES IT.**

> **A green `--qa` migrations check says the QA DATABASE is current. It says
> nothing about the QA IMAGES, and the two drift independently.**

**Reference case, 2026-08-12 — B8's QA behavioural proof.** The QA worker image
was built `2026-08-11 03:46Z` and contained **none of the B5–B8 billing
programme**: zero of the six `packages/ai/src/billing-*.ts` files, and a
`worker.ts` with **0** occurrences of `admitVisitOrThrow`. B5's ledger migration
is timestamped `20260811070000` — *the image predated the table it was supposed
to exercise.* Meanwhile `assert-migrations-applied --qa` reported **100 of 100,
🟢**, and reported it correctly.

**The mechanism is the part to remember, because it is not carelessness.**
`db-migrate:qa` is a separate image with a separate build, and it gets rebuilt
whenever migrations are applied (`20:09Z` that day). The app and worker images do
not. So the migration runner is always fresh, the schema check reads *its* work,
and the services rot behind a green check that was added **specifically to stop
QA drifting.** The two service images were also **eleven hours apart from each
other** (`app 14:54Z`, `worker 03:46Z`) — the stack was not internally consistent
either, and nothing said so.

⚠️ **THE COST IS PAID BY WHOEVER TRUSTS THE STACK NEXT.** RELAY had recorded that
B8's proof would be *"cheap on QA — the stack's `ledger_entries` is also empty,
so a zero-balance refusal is its natural state."* True about the database, false
about the code: the flag could not do anything, because the seam it gates was not
in the image. A session that flipped the flag, saw every visit sail through, and
concluded *"admission does not block"* would have been reading a stale binary and
would have had a green schema check agreeing with it.

**So: before believing anything behavioural about QA, check the IMAGE, not only
the migrations.** `docker images | grep ':qa'` for the build dates, and confirm
the symbol you are about to exercise is actually present:

    docker exec meddoc-qa-transcribe-md-worker-1 sh -c 'ls /app/packages/ai/src | grep billing'
    docker exec meddoc-qa-transcribe-md-worker-1 grep -c admitVisitOrThrow /app/apps/transcribe-md/src/worker.ts

A zero there is the finding, and it is invisible to every standing check.

⚠️ **PRISMA OFFERS THE DELETION OF T3's TENANCY WALL AS TIDYING, AND THAT IS WHY
THE COMPOSITE FK HAS A GUARD.** `transcribe_visits_patientId_practiceId_fkey`
references `(patientId, practiceId) → transcribe_md_patients(id, practiceId)`,
which is what makes a visit whose practice differs from its patient's
**unrepresentable**. Prisma has no syntax for a composite FK, so the model
renders a SIMPLE one and `prisma migrate diff` reports a permanent difference
whose generated script says `DROP CONSTRAINT …patientId_practiceId_fkey` and adds
a single-column replacement. It reads like closing drift; it removes the wall,
because a simple FK checks only that the practice **exists** — which every wrong
practice id also satisfies. **Never apply that hunk.**

The guard checks **by name AND by definition**, and the difference is not
pedantry: mutation-proved on a throwaway database, a same-named single-column FK
passes a name-only check and fails this one. It also carries an opt-in
behavioural arm (`--attempt`) that is **fail-closed off any database without a
qa/test marker**, so F3's read-only-on-production default holds.

⚠️ **AND THE BEHAVIOURAL ARM SATISFIES EVERY UNRELATED `NOT NULL` FIRST.** An
earlier attempt-proof "passed" because `specialty NOT NULL` rejected the row
before the FK was ever consulted — proving nothing about the FK. **A refusal is
evidence only when you know WHAT refused**, so the arm matches the constraint
name in `SQLERRM` and pairs it with a positive control that inserts the same row
correctly scoped.
**A FILE BIND-MOUNT BINDS THE INODE, NOT THE PATH**, and three of this repo's
config files are bind-mounted into running containers out of the working tree:
`Caddyfile` (caddy), `infra/postgres-backup/postscript.sh` and
`infra/backup-offsite-sync.sh` (postgres-backup). Enumerated 2026-08-07 by two
independent methods that agreed — `docker inspect` over every container, running
and stopped, and the compose files.

Any editor that writes-then-renames — `git checkout` included — creates a NEW
inode, and the container keeps the ORPHANED original. Forever, and silently:
the host shows the edit, the container does not, `caddy reload` says *"config is
unchanged"*, **`caddy validate` says "Valid configuration" about the OLD file**,
and `docker compose up -d` declines because no config hash changed. Only
`--force-recreate` re-resolves the bind. **Assert the applied count INSIDE the
container, never on the host.**

The check has two arms because they answer different questions: **content**
(is it running what the repo says — RED) and **inode** (will the next edit even
land — a note, not a fault, since a branch switch re-arms it). It also carries a
**census arm** comparing the hand-kept watch-list against the binds that
actually exist, because hand-kept lists are wrong eventually and a bind nobody
listed is a bind nothing watches.
**A HEALTHY CONTAINER SAYS NOTHING ABOUT WHETHER ANYONE CAN REACH IT**, and that
sentence is a six-hour total outage on 2026-08-07. Every public hostname —
`app.quillmd.com` included — returned 502 while all twenty containers reported
healthy, migrations were 90/90, and every check above was green. They were green
correctly: **none of them looks at the ingress hop.**

nginx re-encrypts to Caddy on `127.0.0.1:8443` with `proxy_ssl_verify off`. That
flag is what made the failure unobservable: because nginx does not verify the
upstream certificate, an **expired** cert there works perfectly, so Caddy served
expired certs from its in-memory cache for weeks with nothing anywhere
complaining. A storage clean removed them from disk, a reboot dropped the cache,
and Caddy came back holding no certificate at all.

⚠️ **AND IT WILL PRESENT AS INTERMITTENT AND PATH-SPECIFIC WHEN IT IS NEITHER.**
nginx reuses upstream TLS sessions, so requests riding an already-resumed session
kept returning 200/307 in the *same second* that fresh ones returned 502 — which
is why the first read of the symptom was wrong. **Only a fresh handshake per SNI
answers the question**; a `curl` sweep measures your own session cache. The check
above forces one, and runs a bogus-SNI negative control first so that a probe
which cannot discriminate reports `2` instead of a green.

The fix was **filed 65 days earlier and priced by how annoying it was**, not by
what it was a symptom of: `docs/qa-reports/site-down-20260603.md` §9.5 recorded
"add `tls internal` to the quillmd Caddy blocks" as a 🟢 item titled *"Caddy ACME
noise"*. Meanwhile `DEPLOYMENT_RUNBOOK.md` §5.6 asserted the hop already used
"its own internal certs" — **a sentence that was false for two months**, read by
everyone as a description of the running system rather than of the intent.

> **A follow-up whose priority came from the loudness of the symptom rather than
> from what the symptom is a symptom OF is a defect with a due date nobody wrote
> down. And a document that states an intended state in the present tense will be
> read as evidence — so it has to be a check, or it is a wish.**

⚠️ **The Caddyfile is one member of the bind-mount class** — the inode trap that
made this fix fail to reach the container is described once, with the whole
class and its guard, above (`check-bind-mount-agreement.sh`). `--force-recreate`
is what re-resolves the bind, and it is the better proof anyway: it exercises
the cold start that is the failure mode.

**A mountpoint directory exists whether or not anything is mounted on it**, and
that sentence is the whole of a four-hour plaintext window on 2026-07-29. MinIO's
compose bind, its systemd unit and this runbook all named the LUKS volume; the
unit had only ever been `enabled`, never *started*, so the bind resolved to a
plain directory on `/dev/sda2` and patient-audio-bucket data rested unencrypted
while every artefact said otherwise. Health checks were green throughout —
nothing was in an error state. The check above asks the one question that cannot
be answered by a correct-looking config: **what device backs the directory the
live container is writing into?** `docker inspect .Source` cannot answer it — it
returns the same `/var/lib/docker/volumes/…/_data` string either way. Runbook §5.7.1.

**Both stores are now fail-closed**, and the guard is the same shape: bind a
path that exists ONLY on the encrypted filesystem (`…/data`, `…/pgdata`) via
`driver_opts`, which docker will not create if missing. **Never use compose's
short-form `- /host/path:/ctr` syntax for an encrypted volume — it auto-creates
the host path**, which is what made this silent. Postgres's version of the
failure is the worse one: an unmounted volume would have made the image `initdb`
a brand-new empty cluster onto plaintext storage and come up *healthy*, with the
real cluster sitting unmounted underneath. **Never `mkdir` one of those bind
targets by hand to "fix" a failed start** — on an unmounted volume that is
exactly how you convert a loud refusal into silent data loss.

**`--pid=host` is not enough for device-mapper work — add `--ipc=host`.**
libdevmapper syncs with udev through SysV semaphores, so a container with its own
IPC namespace waits forever on a cookie host udev signals elsewhere. The dm
operation *completes* and the process hangs afterwards, which is why it reads as
a storage problem rather than a namespace one. Better: don't run `cryptsetup` in
a container at all — `systemctl start <unit>` runs it as a host process and
returns in seconds.

**The QA stack must be incapable of reaching a vendor, and "incapable" needs two
conditions.** `MOCK_AI_CALLS=true` stops calls only while every code path
honours the flag; dummy credentials are what survives a code regression. The
check reads the **running containers**, not the compose file, because on
2026-07-28 the file read as safe and the containers were not:
`${MOCK_AI_CALLS:-true}` and `${ANTHROPIC_API_KEY:-mock-key-qa}` both inherit
from the shared `.env`, which sets them because PRODUCTION needs them. The
result was 298 real Anthropic calls and live Deepgram requests from the stack
whose header promised it could reach nothing — burning the same balance
production depends on. **A `${VAR:-default}` in `docker-compose.qa.yml` is a
bug until proven otherwise.**

An imaging report has no office-visit E/M level. That invariant is enforced in
the app's compute/store guards, in the review-doc E2E fixtures, and in
`seed-certified-twin.ts` — **none of which watch production.** Five prod imaging
visits acquired `emScoredCode` from a page render by a build that predated the
`specialtyLabel`-vs-`specialtyId` fix; no seeder wrote them, no test could see
them, and they sat there for two days. Remediated 2026-07-28.

**A deploy that says it migrated may not have.** `docker compose run --rm
db-migrate` runs whatever image was LAST BUILT, and `db-migrate` builds from the
app Dockerfile — so rebuilding only the app services leaves it stale. On
2026-07-28 it printed "79 migrations found / No pending migrations to apply" and
exited 0 while the repo had eighty. **Never read that message as proof.** Deploy
with `bash scripts/deploy-prod.sh`, which rebuilds db-migrate unconditionally,
asserts afterwards, and aborts before recreating anything. Runbook §2.

**The imaging script never mutates.** If it reports rows, classify before acting — a
computed baseline (`emScoredCode`), a doctor-set `cptCodes.em.override`, and a
frozen `cptCodes.em.signedCode` are three different findings and only the first
is a routine clear. Remediation is a deliberate transactional act with an
abort-on-mismatch guard and an audit row, never a side effect of a check.


---

## ⚠️ AND A RULING'S OWN DUE DATE IS A DATA INVARIANT NOBODY WAS WATCHING

**Appended 2026-09-05.** The list above watches for states that are WRONG. This
adds one that watches for a moment that has ARRIVED — and the argument is the
same, because both are invisible until something looks.

    bash scripts/check-icd-rederivation-trigger.sh  # READ-ONLY. 0 = not yet owed, 1 = DUE, 2 = can't tell

Ruling #185 fixes the ICD auto-accept threshold at **0.90** and labels it
SPECIFICATION-DERIVED — it comes from the L7a prompt's own *"0.9 or above =
explicit diagnosis statement"* clause, a statement about what the model was
ASKED to mean rather than a measurement of how often it is right. The ruling
then owes a **re-derivation after 50 real doctor decisions**, and on the day it
was written the T9 recon measured **zero** decisions against 58 visits.

**A due date with no watcher is a wish.** Nothing in the codebase would ever
have said *"the fifty are here."*

⚠️ **AND THE NUMBER THAT GATES IS NOT THE OBVIOUS ONE.** A re-derivation needs
`(confidence, outcome)` PAIRS. A decision whose code has left that visit's
proposals — the `orphaned` bucket in `lib/icd-decisions.ts` — is a real decision
a doctor really made and **cannot be paired with a confidence**, so counting it
toward fifty fires the trigger early and buys a re-derivation on fewer labelled
examples than the ruling asked for. The check counts PAIRABLE, prints all three
buckets, and refuses if the partition does not reconcile.
