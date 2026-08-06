<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

<!-- BEGIN:preflight-gate -->
## Pre-flight health check

Before invoking ANY task matching the trigger criteria in the `preflight-health-check` skill, the lead agent MUST run that skill first. Treat its output as a gate:

- 🟢 **GO** — proceed silently (one-line confirmation only).
- 🟡 **FIX-AND-GO** — proceed, mention auto-fixes in final summary.
- 🔴 **BLOCK** — do not start the user's task. Report the blocker and ask the user how to proceed.

Trigger criteria (run preflight first):
- Task spawns 1+ subagents
- Task involves `next build`, `pnpm install`, `docker compose build`, or full-app `tsc --noEmit`
- Task references "Phase X", "Batch X", or "remodel"
- Task writes to multiple component files
- Task runs full test suites
- Task follows the `qa-clinician-remodel` skill

Skip preflight for: single-file reads, single-file edits (<50 lines), read-only queries, git status/log/diff inspection, and already-running QA reports.

Never bypass preflight on a major task. Never prompt the user "run preflight?" — just run it. Output is silent on GO, surfaced fully on FIX-AND-GO or BLOCK. Reports are always written to `docs/preflight-reports/preflight-<UTC-timestamp>.md` for the audit trail.
<!-- END:preflight-gate -->

## Production verification — standing law

**A real doctor's visit is never a smoke target.** Not to take a screenshot, not
to confirm a deploy, not "just this once". Signing, adopting into, or exporting
someone's actual clinical note to prove your own change works is not a test —
it is editing a medical record for your convenience.

Production verification is **structural**:

- container health, image digests, applied migrations
- the flag is inlined in the shipped bundle (grep the built chunk — a
  `NEXT_PUBLIC_*` read that survives at runtime means it was NOT inlined)
- co-tenant HTTP status
- DOM *presence* of the new surface on a route, without mutating anything
- full flows ONLY on the synthetic smoke-doctor account, cleaned to baseline
  afterwards, with the audit rows left in place

The **full clinical walk lives on QA**, against a build that is byte-identical
to the one promoted — same commit, same build args, separately tagged image.
QA is the isolated `meddoc-qa` stack (`127.0.0.1:9020`, synthetic DB, MOCK_AI).
It is localhost-only by design; reach it through an SSH tunnel. Never rebuild
prod's `:latest` to stage something — tag a separate image and point a compose
override at it.

If a flow genuinely cannot be exercised on QA, say so in the report and leave it
unverified. An unverified step named honestly is worth more than a green tick
bought with a patient's record.

## Tracked fixtures — a recorded decision

`WM IOV Template.docx` at the repo root is a **known, accepted tracked
fixture**. It is a customer's BLANK form — headings, dropdown content controls
and letterhead, no patient data — and the repository is private. It is the only
real-world template the Template Twin work can be exercised against, and a copy
lives at `apps/transcribe-md/tests/e2e/fixtures/sample-form.docx` for the E2E
packs.

Decided 2026-07-26. **Do not re-flag it** in audits or reports, and do not
rewrite history to remove it.

What this does NOT cover, and what remains forbidden: any **filled** document or
note. `twin-*.docx`, `diag-*`, and the other clinical artifacts at the repo root
carry PHI and are gitignored. A filled document is never a fixture.

## The Q1 backlog has ONE source of truth

`docs/backlog/q1-fixpack-retriage-20260728.md`. Nothing else.

The original triage (`docs/audit-reports/q1-fixpack-triage-20260506T190348Z.md`,
PR #171) carries a SUPERSEDED banner and is kept only as the historical baseline.
Do not work from it, and do not re-open items by reading it.

**A backlog that predates a rewrite is a list of guesses until it is
re-validated.** Six of sixteen findings had been closed by later work and nobody
had marked them; a seventh had shipped as a product feature under another name.
Every remaining row was re-checked against `main` by re-running its own evidence
query — do the same before acting on any of them.

Three shipped 2026-07-28: **N1** (a dictated CPT code reaches the note — the
allowlist was never the cause), **§07.1** (L6 polish sees the visit, as a
disambiguation source only — the fidelity gate still measures against the draft
alone), **§02.9** (ROS polarity as data).

The remaining six are **PARKED**, and the trigger is written down: *the pilot
roster confirms the specialty.* They are specialty-shaped, so building them now
is building them for a guess. Do not un-park on a feeling that there is time, and
do not let "safety-adjacent" alone promote §01.3 — L5 is advisory and does not
gate signing.

## Template Twin — the parked steady state

**Read this before concluding anything about Template Twin.** An audit in July
2026 raised 173 facts about it and **17 of 24 load-bearing claims were corrected
under challenge** — a 71% correction rate. That was the cost of illegibility, not
of anyone's carelessness. This paragraph is the cure: it is the deliberate steady
state, and none of it is a bug.

**PARKED 2026-07-28.** Verdict: absorb into the shipped `note_templates` pipeline.
The RETIRE column was executed (PR #442). The INTEGRATE column is **post-pilot
roadmap**. **Trigger to un-park early: a pilot doctor explicitly needs their native
form bytes back.** Nothing else.

What is true, and intended:

- **`NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX` stays ON in production.** It is not a
  half-shipped feature left switched on by accident. It gates the OOXML ingest +
  fail-closed security fork that runs on **every** `.docx` template upload
  (`note-template-parse/docx-to-text.ts:39` dynamically imports the twin ingest),
  and the shipped `pdf-native` feature imports twin storage. That code is
  **absorbed in place and load-bearing** — deleting it breaks working paths.
- **The per-visit fill step short-circuits `not_certified_twin` on every visit,
  by design.** `worker.ts` calls it; it declines because no CERTIFIED compiled
  version exists in production. That is the correct behaviour for a parked
  feature, not a failure to investigate.
- **The certification UI stays folded in production**
  (`NEXT_PUBLIC_SETTINGS_SIMPLE_ROW=true` renders `NativeTemplateManager` as
  null). There is therefore **no door in**, which is why prod has zero
  certifications while the flag is on. That is the explanation — stop looking for
  a broken gate.
- **`MAPPINGS_NOT_READY` is a deliberate refusal and stays strict.** Certification
  refuses until every field has a physician-confirmed mapping; on a real customer
  form that is 79 of 80. **Never weaken the gate to shrink the wall** — a
  certified twin that nobody confirmed is worse than no twin. The work, if the
  park is lifted, is the imaging concept registry and the confirmation flow.
- **The twin HAS worked end to end**, on QA, by hand: upload → compile (80 fields,
  1 table) → fill manifest (`VERIFIED`, `roundTripVerified=true`) → native DOCX
  export (`nativeTemplate=true`). Two earlier "never proven" conclusions were
  wrong: `template_twin_fill_manifests` read empty because its `visitId` FK
  cascades on fixture re-seed, and the "0 native exports ever" figure was
  prod-scoped while QA held ten.

Full evidence: `docs/qa-reports/template-twin-integration-verdict-20260728.md`
and `…-absorb-plan-20260728.md`.

## Rollback constraints — known, accepted, do not "fix"

A flag rollback is not always a clean inverse. Where it costs a capability, the
cost is recorded here so nobody rediscovers it mid-incident and starts building.

### `NEXT_PUBLIC_REVIEW_DOC_VIEW=false` → E/M is confirm-only, no override

**Decided 2026-07-28. Accepted.**

Rolling that flag back returns the legacy tabbed review view, where a doctor can
see the documentation level and confirm a change to it but **cannot set one**.
The override lives only in the read-only paper's gate stack (`<EmLevelCard>`);
`BillingCardC3`'s dropdown and the coding rail's were retired in the same change
because `POST /em-score/override` requires a reason and neither had anywhere to
collect one — they would 400 on every use.

**The gate does not weaken** — confirm-before-sign and the server-side refusal in
`POST /sign` are flag-independent. One capability is lost, temporarily.

**Acceptable for an emergency window. Revisit only if a rollback must live
long**, and then by giving `BillingCardC3` its own required-reason step — never by
restoring a reasonless caller, and never by fabricating a rationale to satisfy
the route. An audit row's "why" is the doctor's words or nothing.

Prefer the IMAGE rollback (`:pre-emrehome-20260728`) when the concern is the E/M
surface specifically — it has no such constraint. Full detail and the tag table:
`docs/DEPLOYMENT_RUNBOOK.md` §3.1–3.2.

## Shared components — diff the callers BEFORE you replace them

**A shared component must accept every context its predecessors carried.**
Before replacing per-caller code with one component, diff each call site's
props, params and query strings and check the new signature can express all of
them. Then the migration test asserts **both directions**: it carries the
context when given, and omits it when there is none.

Why this is written down: R4 spent a round on two defects that are the same
mistake in two shapes, both introduced by consolidations that were otherwise
right.

- **Context dropped.** R3.2 replaced `/patients/[id]`'s New-visit link — which
  carried `?patientId=…` — with the shared `RoundsNewVisitCta`, and that
  component hardcoded a bare `/visits/new`. On the one page where the patient is
  already known, the button dropped them into create-a-patient. ⚠️ **The
  empty-state link on the same page still worked**, so *"the patient page has a
  working New visit link"* was true and useless — a claim that survives a
  spot-check. **Fix (reference implementation): context as an optional prop**
  (`patientId`), swept across every entry point, with the test asserting the
  five surfaces that legitimately have no patient in scope still omit it. A
  component that appended a stale id everywhere would satisfy the positive
  assertion and be a worse bug.

- **Coverage assumed.** R3.4 wrapped ONE of `RxTab`'s **three** mount sites in
  the Rounds host and verified it there — correctly, and incompletely. The other
  two rendered the legacy cream panel on a Rounds route for two rounds.
  **Fix (reference implementation): the treatment lives ON the component**
  (`rx-tab.tsx`), not on its callers, so every present and future mount inherits
  it and the list cannot go stale.

The rule generalises: **a per-caller list is kept complete by hand, and hand-kept
lists are wrong eventually.** Put the behaviour where it cannot be forgotten —
on the component — and where that is impossible, make the missing case fail a
test rather than render quietly.

**Neither defect was visible to any sweep.** A class census finds classes; it
cannot see a missing query param or an unhosted third mount. If this shape
recurs, the answer is a contract test on the shared component — its accepted
context, and its mount count — not another sweep.

## A required column is a WRITE-PATH sweep, and the sweep is BY TABLE

**Standing rule for any migration that adds a NOT NULL column, or any constraint
that makes an existing shape illegal.** Enumerate every write path *before* the
column lands, not after CI finds them one at a time.

T3 added `practiceId` to `transcribe_visits` and cost **five CI cycles**. Four of
them were the same mistake at a different altitude:

| I enumerated | It lived in |
|---|---|
| `isSkinRounds` — the accessor | `next.config.ts`, reading the raw env var |
| flag consumers | a hardcoded **destination** in the command palette |
| three build-block keys | a fourth, `target: builder` |
| three models' required fields | a fourth model, `User.passwordHash` |
| `transcribeVisit.create` — the ORM method | `INSERT INTO transcribe_visits` — raw SQL |
| a named subset — *"every write that sets `signedAt`"* | **the other members of the subset I had just named** |

The first five are the same shape: **the inventory was taken at the layer I was
thinking in, and the thing lived one layer down.** The fifth was the worst of
those, because raw SQL has no type checker — a required column is invisible
until the database refuses the row at runtime.

⚠️ **THE SIXTH IS DIFFERENT AND IS THE ONE TO WATCH FOR. NAMING A CLASS IS NOT
ENUMERATING IT.** T4's commit message said, in as many words, *"the createdBy
sweep covered every CREATE; signedBy applies only to the SUBSET that sets
signedAt."* Having written that sentence I fixed exactly ONE member of the
subset — the one the database had already refused — and shipped. The other two
reddened CI on the next run.

The failure was not searching the wrong layer. It was **not searching at all**,
because the sentence felt like the work. So: **a named subset is swept by its
DEFINING PREDICATE, never by memory of which members were touched.** Here the
predicate is *"every write that sets `signedAt`"*, and the sweep classifies each
site by BEHAVIOUR — signs / never signs / clones — with an assertion that
`signs == names_signer` for every one. If you can state the rule, you can grep
for it; if you only state it, you have written a comment.

So the sweep has a fixed shape:

1. **BY TABLE, not by API.** Search the table name, then the ORM method. Both.
   `grep -rniE 'insert into ["\x27]?<table>'` **and** `<model>.(create|upsert|createMany)`.
2. **Clone and bulk paths are VERIFIED, not assumed.** `select * from <table>`
   carries new columns automatically — but confirm the source is the table
   itself. `INSERT … SELECT` from a narrowed projection does not.
3. **Type-check is decisive only for TYPED sites.** With the column required,
   `tsc` 0 errors proves every typed create satisfies it. Payloads typed `any`
   are invisible to it — read those.
4. **POSITIVE-CONTROL THE SWEEP'S OWN PATTERN before believing its zero.** Mine
   lied in both directions inside five minutes: first `0 sites` (shell escaping
   ate the pattern — a false all-clear that would have ended the search), then
   `3 MISSING` that were fine (a 40-line window could not see a value set on a
   spread object defined earlier). A sweep that reports nothing and a sweep that
   is broken produce the same output.
5. **MUTATE THE CODE, NEVER A LIVE DATABASE.** Proving a constraint-backed test
   can go red means changing the SOURCE (the assertion, the column name), or
   running against a throwaway database — never `ALTER TABLE … DROP CONSTRAINT`
   on a stack other tests share.

   ⚠️ This is written down because it cost real damage on 2026-08-05. A mutation
   dropped `transcribe_visits_signed_requires_signer`; the gate's own
   `UPDATE … SET "signedBy" = NULL` then SUCCEEDED, nulling 21 signers; and the
   re-`ADD CONSTRAINT` failed **because of the rows it had just created**. The
   database was left with unattributed signatures AND no constraint — the exact
   state that test exists to prove impossible.

   Two corollaries, both earned:
   - **Any write inside a gate that a constraint is supposed to refuse belongs
     in `BEGIN; … ROLLBACK;`.** Then the attempt is observable and never
     consequential, whatever state the constraint is in.
   - **NEVER pipe a repair or a re-add to `/dev/null`.** The silent failure is
     how "restored" became untrue for twenty minutes. Read the exit code, then
     re-verify the object exists.

6. **Prefer DERIVING the value in the query over threading a parameter.** T3's
   raw-SQL sites take
   `(select "practiceId" from transcribe_md_patients where id = …)`.
   A hand-passed value can only be correct or rejected; a derived one cannot
   drift.
7. **A RAW `CREATE INDEX` / `ADD CONSTRAINT` IS DECLARED IN THE SAME COMMIT, OR
   ITS INEXPRESSIBILITY IS DOCUMENTED IN PLACE.** A migration that adds an index
   in SQL and does not touch `schema.prisma` has created drift, and drift is
   invisible until something else trips over it.

   ⚠️ Written down because T3 and T4 both did it — the same programme that was
   *fixing* drift introduced two more instances (`transcribe_visits_practiceId_idx`,
   `transcribe_visits_signedBy_idx`), and they were only found by enumerating.

   Where Prisma genuinely cannot express the object — PARTIAL indexes,
   expression/GIN/GiST indexes, `NULLS NOT DISTINCT` — document it beside the
   model in the `schema.prisma:1700` style: name the index, give its real DDL,
   and say what a naive "fix" would break.

   ⚠️ **AND THE NAIVE FIX IS SOMETIMES WORSE THAN THE DRIFT.** `note_templates`
   carries a PARTIAL unique on `(doctorId, encounterType) WHERE status='active'`.
   Declaring `@@unique([doctorId, encounterType])` to "close the drift" would
   create a FULL unique — strictly stronger than the database enforces — and
   production already holds a row group that violates it. Check what the
   constraint actually says before declaring you are merely writing it down.

   **STANDING EXPECTATION: the drift enumeration reports UNDECLARED-PLAIN = 0.**
   Partial and expression indexes are the only permitted residue, and each is
   documented. Checkable at any time by comparing `pg_indexes` against the
   `@@index`/`@@unique`/`@unique` declarations in the schema.

8. **The migration ABORTS on any underivable row before `SET NOT NULL`.**
   `RAISE EXCEPTION` on a non-zero count. A partially-backfilled column that
   then takes NOT NULL is a migration that half-ran and reported success.

⚠️ **The one that mattered was production code.** `src/actions/visits.ts` is the
real visit-creation path; it would have failed for every doctor on the first
request after deploy, with `Argument \`user\` is missing` — an error that does
not even name the missing column. Finding it took enumerating rather than
patching what CI happened to surface.

## Multi-session programs have relay ledgers — READ THEM FIRST

A relay ledger is the contract between sessions. It says what is built, what is
next, and what proof exists. **Nothing in this file used to point at one, which
is how a session can open, do good work, and duplicate or contradict a ruling
made three sessions ago.**

| Program | SPEC (what to build) | RELAY (what is built, what is next) |
|---|---|---|
| **Rounds** — the shipped skin | `docs/rounds/SPEC.md` | `docs/rounds/RELAY.md` |
| **Foundation** — teams → billing → admin | `docs/foundation/SPEC.md` | `docs/foundation/RELAY.md` |

Foundation additionally has `docs/foundation/DISCOVERY.md` — evidence about the
system as it is today, with seven claims recorded **as corrected** after
adversarial re-verification. When SPEC and DISCOVERY disagree, that is a
finding, not a typo.

Read the relay's `## Rules` section before touching its program. The Rounds
rules (one item per session; merge-commit CI cited by SHA; no push mid-run; no
evidence before the event; say what would make the check fail, then make it
fail) apply to both and are not restated in the Foundation ledger.

## Branch cadence — standing rule

**Branch from `main`. Merge back promptly. No long-lived divergence.**

A feature branch is a short-lived thing. It exists to carry one change through
the gate and then it is retired. It is not a parallel trunk.

- Branch from `main`, not from another feature branch.
- Merge back **as soon as the change is green**, not when the next one is ready.
  A branch that ships to production is not "done" — it is done when `main`
  carries it.
- If a branch is deployed to production, `main` MUST be reconciled in the same
  session. Production running code that `main` does not have is the failure
  state this rule exists to prevent.
- Retire the branch on merge. Delete it locally and on the remote.

Why this is written down: `fix/twin-visit-export-harness` reached **78 commits
and 217 files** ahead of `main` while production ran from the branch. Nothing
was broken by it, but every guarantee `main` is supposed to give had quietly
stopped being true — `main` was not what shipped, a rollback to `main` would
have reverted weeks of live behaviour, and the required gate was measuring a
branch nobody could merge. The longer the divergence, the more the merge stops
being bookkeeping and starts being a risk of its own.

The gate still applies in full: no merge past a red required check, and no
override to get one green.

## Close-out hygiene — reap the scratch, every session

**A filled clinical export outside a sanctioned path is treated as PHI —
regardless of whether the patient is real or synthetic.** The posture does not
depend on knowing which, because by the time you are asking, the file already
exists somewhere it should not.

Before a session ends, destroy the scratch:

- `.playwright-mcp/` — browser downloads AND the `page-*.yml` accessibility
  snapshots, which carry the rendered note text of every page walked.
- `/tmp` — screenshots, `scratch-docx-*`, signed-preview PDFs.
- `~/.local/share/Trash/` — **deleting a file does not remove it here.** A
  filled twin export was found in Trash after its original had been cleaned.
- Worktrees and staging/evidence dirs under `~` — `*-output.docx` is a filled
  document by definition.
- **Directory SNAPSHOTS of the repo under `~`** — `release-witness/`,
  `reviewer-witness-*/`, `*/tracked-source-*/` and anything else that is a flat
  copy of the tree. These are a **liability class, not evidence**, and they are
  in scope forever. Reap them at the end of the session that made them.
- Repo root — `twin-*.docx`, `diag-*`, `visit-*.pdf|docx`.

Use `shred -u -n 3 -z`, not `rm`. Root-owned artifacts need the documented
root-via-docker path; a silent "Permission denied" from `shred` leaves the file
exactly where it was.

**Shred, then CHECK EXIT CODES, then escalate the failures — and only then
remove the directory.** Unlinking before the failures are resolved converts a
recoverable "Permission denied" into a permanent one: the file is gone, so it
can never be shredded, and the blocks stay on disk. This cost two files on
2026-07-30 (`docs/qa-reports/history-purge-smoke-exports-20260728.md`).

**Report paths, never contents.**

#### Session evidence trees are EXTRACT-THEN-SHRED, at session end

**Findings go into the repository; the raw tree is destroyed. An unowned
snapshot never persists.** This is not conditional on the tree being dirty.

The reasoning is the part to remember, because "it is clean, leave it" is the
intuitive answer and it is wrong: **a tree that is provably clean today has to be
re-proven clean by every future sweep, for as long as it exists.** The
verification cost is paid again and again, by people who did not create it and
cannot tell from the outside whether it matters. And the class is not
theoretical — the 2026-07-28 history purge missed six copies of two filled
exports because they sat in exactly this kind of tree, invisible to a stale-copy
scan that enumerated git repositories.

The shape:

1. **EXTRACT the reports** — `.md`/`.txt` summaries, findings, conclusions. Never
   source snapshots, build output, container ids, port files, temp paths or file
   manifests: those are the machine's leftovers, and keeping them is how the
   liability class reconstitutes itself. Land them under `docs/qa-reports/` and
   **commit and push before shredding anything** — extraction must be durable
   before destruction begins.
2. **Check admission harder than the sweep did.** A file entering the repo enters
   every future clone. Credentials by value AND by shape (`PGPASSWORD=`,
   `postgres://user:pass@`, generic `password|secret|token|api_key` assignments,
   `sk-`, `Bearer`, PEM headers, `AKIA`), negative-controlled against a canary
   carrying those shapes; plus a prose read of anything whose title implies a
   secret a pattern cannot see.
3. **Read what you are about to destroy.** The 2026-07-30 extraction found a
   document recording a service credential seen in a process command line, whose
   own disposition made rotation a **release blocker** — and nothing in the repo
   recorded that rotation happening. Shredding first would have destroyed the
   only pointer to an open security item.
4. **Then shred, per the rule above** — `chmod u+w` first (a mode-`0400` file is
   the known failure), unlink symlinks rather than shredding *through* them (a
   symlink is how a sweep destroys something outside its own boundary),
   escalate root-owned files via root-via-docker, and remove the directories
   **only** when the failure count is zero.
5. **Verify with a controlled sweep and state the boundary** — including the
   positive control, or the zero means nothing.

#### A history purge does not clear the filesystem

`docs/smoke-test-2026-05-04/phase-C/export.{docx,pdf}` were purged from every ref
on 2026-07-28. **Six copies were still on this host on 2026-07-30**, in three
plain directory snapshots dated 2026-07-21. The purge's own stale-copy scan was
`find / -name .git` + `git cat-file -e <blob>` per repo — and a snapshot **is not
a git repository**, so it had no `.git` to enumerate and no object database to
query. The scan was right for clones and blind to snapshots.

So a stray-export sweep is not optional after a purge, and it has a shape:

- **Search the CONTENT PATH, not only git objects** — basenames *and* the path
  fragment, not blob SHAs.
- **Unbounded depth.** A first pass at `-maxdepth 6` returned **4 of the 6** and
  read as complete; the other two sat at depth 7. A depth-limited sweep is a
  sample, never an inventory — the same defect as an emptiness test that passes
  on a set whose size it never established.
- **`-xdev`,** and say which device you covered.
- **State the boundary in the report** — roots, depth, filesystem, file count.
  A sweep that does not say what it looked at cannot be checked, and "I found
  nothing" is worthless without "here is where I looked".
- **Positive-control the traversal, not just the needle.** Confirming your
  matcher finds a secret's value in `.env` proves the *needle* works. It says
  nothing about whether the search ever entered the trees you named — and a
  traversal that silently covers nothing returns zero for every needle you try.
  Run the same matcher form against something known to be present in the
  haystack (`meddoc`, `transcribe`) and report the hit count beside the zeros.
  Without it, a clean sweep and a broken sweep are the same output.

  This is the *third* face of one defect — after §4's dead stack and the
  `-maxdepth 6` sample: **an answer about a set whose boundary was never
  established.** Whenever a check reports "nothing wrong", ask what it would
  have taken for it to say anything else.

### And check the data invariants that nothing else watches

Scratch is not the only thing a session can leave behind. Some defects write a
COLUMN, and no sweep of the filesystem will find them.

```bash
bash scripts/check-imaging-em-artifacts.sh    # READ-ONLY. 0 = clean, 1 = found, 2 = off-host
bash scripts/assert-migrations-applied.sh     # READ-ONLY. 0 = all applied, 1 = UNAPPLIED, 2 = off-host
bash scripts/check-qa-mock-posture.sh         # READ-ONLY. 0 = severed, 1 = LIVE KEYS, 2 = stack down
bash scripts/check-minio-encrypted-mount.sh   # READ-ONLY. 0 = encrypted, 1 = DRIFT, 2 = can't tell
bash scripts/check-pg-encrypted-mount.sh      # READ-ONLY. 0 = encrypted, 1 = DRIFT, 2 = can't tell
```

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

### What is NOT a stray, and must survive the sweep

- `WM IOV Template.docx` and its copies — the accepted BLANK tracked fixture
  (see "Tracked fixtures" above). Do not re-flag it.
- `colon_blank_answers.pdf` — likewise a committed blank form.
- `apps/transcribe-md/tests/e2e/fixtures/**` and `__fixtures__/**` — committed
  test fixtures.
- Anything under `/opt/meddoc-pro/backups/`.

The distinction is FILLED vs BLANK, not file type. A blank form is a fixture; a
filled one never is.

### A tracked clinical file means a HISTORY REWRITE, not `git rm`

Deleting a tracked artifact from the working tree does not remove it from
history. `docs/qa-reports/twin-real-visit-20260726.docx` — a filled document —
was committed in `9d65cbfa` and reached `main`. `git rm` left the blob
reachable on every clone and on the remote.

Clearing it cost a full `git filter-repo` rewrite across all refs, a force-push
over a **protected branch** (protection read, relaxed on one field, restored),
deletion of 22 scratch clones on the VPS, and deletion of two open dependabot
branches that had forked off the old `main` and pulled the blob straight back
after the first gc. Plus a permanently accepted residual: GitHub keeps
unreachable objects until its own GC.

#### `refs/pull/*` is the namespace the rewrite cannot reach

A force-push fixes branches and tags. It does nothing to `refs/pull/*`, which
GitHub owns and serves read-only. After the 2026-07-27 purge reported success,
a `git clone --mirror` of origin **still returned the blob** — from 11 pull refs.
Two distinct traps:

- **`refs/pull/N/merge` on an OPEN pr.** GitHub continuously recomputes a
  test-merge of every open PR *into the base branch*. Eight dependabot PRs that
  had never touched the file got merge refs carrying it, because GitHub merged
  them into a `main` that was still poisoned. **The poison arrives from the base
  side.** So "no open PR touched the file" is the wrong check and will clear a
  repo that is not clean — the right check is to enumerate every ref on origin
  and test each one. Closing the PR drops its `/merge` ref (verify against a
  closed PR as a negative control); dependabot regenerates it against the
  rewritten base.
- **`refs/pull/N/head` on a CLOSED or MERGED pr is permanent.** It cannot be
  pushed, deleted or expired, and because it is a *live ref* the object is
  reachable — GitHub's GC will never collect it. Only a **GitHub Support
  request** removes it. Budget for this: a rewrite is not finished when the
  push lands.

Verify with `git clone --mirror` and scan every ref, not with a plain clone —
a default clone does not fetch `refs/pull/*` and will look clean either way.
And shred the mirror afterwards; it is a blob-carrying copy.

`filter-repo`'s `commit-map` disappears with `.git/filter-repo/`, but GitHub's
**workflow-run history survives the rewrite** and still pairs pre-rewrite head
SHAs with commit titles — use it to repair dangling SHA references in docs.

**Filled exports never belong under `docs/`.** Nothing that renders a patient's
note belongs in the repository at all — not as evidence, not as a QA artifact,
not "just this once". Reference it by path in a report; do not commit it.

A pre-commit guard blocks added `.docx`/`.pdf` outside the fixture allowlist
(`scripts/hooks/pre-commit`). It installs itself — the root `prepare` script
sets `core.hooksPath` on `npm install`, because a guard that depends on every
future contributor remembering a setup command is a guard that is off.

It is a backstop, not the rule. The rule is the paragraph above.

#### The fixture allowlist is ONE list, and it lives in the hook

`scripts/hooks/pre-commit` is the single source of truth for what may be a
tracked `.docx`/`.pdf`. Nothing else gets a vote, and a sweep that "decides" a
file is fine without checking that list is guessing. As of 2026-07-28 it is:

| Allowed | Why |
|---|---|
| `WM IOV Template.docx` | the customer's BLANK form — recorded decision, see "Tracked fixtures" |
| `colon_blank_answers.pdf` | committed blank form |
| `docs/qa-reports/comprehensive-audit-20260514T030426Z.pdf` | **adjudicated 2026-08-03** — 17-page code/logic audit report, NO clinical content, predates the hook |
| `apps/transcribe-md/tests/e2e/fixtures/**` | committed E2E fixtures |
| `apps/transcribe-md/src/**/__tests__/__fixtures__/**` | committed unit fixtures |
| `apps/transcribe-md/src/**/__fixtures__/**` | committed unit fixtures |

Every one of these is BLANK, a sample input, or an adjudicated non-clinical report. **They must survive every future
sweep** — a sweep that eats the blank fixtures breaks the twin work, which is
why they are named here as carefully as what must not survive.

Adding a row here means adding the same row to the hook. If the two ever
disagree, the hook is right and this table is stale.

#### READ IT, THEN ADJUDICATE, THEN WRITE THE DECISION DOWN

**The standing pattern for any future stray.** The May audit PDF sat tracked and
unlisted for eleven weeks — not blocked (the hook only sees ADDED files, and it
predates the hook), not sanctioned either. Every sweep that met it re-derived the
same question and moved on, and an unanswered question decays: "unknown" becomes
"probably fine" through nothing but repetition.

So when a sweep finds a `.docx`/`.pdf` that is not on the list:

1. **READ IT.** Not the filename, not the directory, not who committed it — the
   CONTENT. `unpdf` / `unzip` take seconds. A filename is a claim, and
   `synthetic_`-style prefixes have already been rejected as evidence once
   (see the launch-readiness rulings: three files were non-PHI by OWNERSHIP,
   never by their names).
2. **ADJUDICATE.** Filled clinical content → it is PHI, and the remedy is the
   history rewrite above, not `git rm`. Blank form, sample input, or a report
   with no clinical content → it belongs on the allowlist.
3. **WRITE IT DOWN, IN THE HOOK,** with the date and what you actually read.
   A decision that lives only in a session transcript is not a decision; the
   next sweep cannot see it and will ask again.

**A stray nobody can read does not get the benefit of the doubt.** If it cannot
be opened, treat it as filled and escalate — that asymmetry is deliberate,
because the two errors are not symmetric.

#### A second purge, and what it cost — 2026-07-28

`docs/smoke-test-2026-05-04/phase-C/export.docx` and `export.pdf` were tracked
FILLED exports. The content was plainly synthetic ("Dr. Smoke Tester MD",
patient "Smoke TestPatient One"), and the ruling was that **it makes no
difference**: the close-out rule treats a filled clinical export as PHI
regardless, so there is no adjudication class and no argument to have at the
moment one is found. They were purged by `git filter-repo`. Do not re-add them;
the rest of `docs/smoke-test-2026-05-04/` is untouched and stays.

**It was ~200× the work of the first purge, for the same two files' worth of
content, purely because it had been sitting there longer.** The twin export was
four days old: one branch, ten tags, one commit pruned. These were committed on
2026-05-04 in PR #108, so by the time they were removed they were in **75 of
141 branches and tags**, 104 local branches, 31 stale clones on the box — and,
permanently, in **300 `refs/pull/*` refs**, one per PR opened since. That last
number is the one that does not come back down: `refs/pull/*` is GitHub-owned
and unpushable, so the residual grew by one ref per PR for every day the files
stayed. The cost of a tracked clinical file is not fixed. It compounds.
