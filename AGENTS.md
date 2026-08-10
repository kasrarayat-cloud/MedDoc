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

## A check whose TITLE is narrower than what it MEASURES

**Standing rule. Read a check's name as a claim, then go and confirm the
implementation makes exactly that claim — no wider, no narrower.** The failure is
not a bug in the logic; the logic is usually correct about something. It is
correct about the *wrong quantity*, and the name is what stops anyone noticing.

Both reference cases are T5's own ratchet, found within an hour of each other,
and both would have made the item's CLOSE CONDITION UNREACHABLE:

| The name said | It actually measured | What that cost |
|---|---|---|
| "**unscoped** request-context reads" | *every* clinical read, scoped or not | routing a call through the accessor left the number unchanged — **adoption could never lower it** |
| a count of reads **in code** | reads in code *and in comments* | the accessor's own doc-comment example counted, putting a permanent **floor of 1** under a ratchet whose whole purpose is to reach 0 |

Note what neither one was: neither ever produced a wrong answer *to the question
it was actually computing*. A test that passes and a test that measures the
wrong thing look identical from the outside, and a green ratchet that cannot
move looks exactly like a codebase with nothing left to fix.

Three questions that catch it, and they are cheap:

1. **If the work this check guards SUCCEEDED completely, what number would it
   print?** If the answer is "the same one", the check is not watching the work.
   (T5's non-vacuity floor did worse than not move — it went RED for the
   migration's success, because it summed only the buckets adoption was
   draining. **A check that fails when the thing it guards starts working is a
   check nobody keeps.**)
2. **Name every bucket the scan can sort an item into, and assert the total.**
   T5 ended with five — unscoped / scoped / personal / system / comment — and
   the total reconciles against the pre-adoption figure. Anything that doesn't
   fit a named bucket is the finding.
3. **Mutate toward SUCCESS, not just toward failure.** Everyone remembers to
   prove a guard can go red on a regression. Prove it also MOVES when the fix
   lands — otherwise the ratchet is a decoration.

## A gate's WATCHED SET is diffed against the spec's NAMED set

**Sibling of the section above, not a duplicate — and the difference is the
whole point. That one measures the wrong QUANTITY over the right universe. This
one measures the right quantity over the WRONG UNIVERSE.** A check can be
flawless at counting a set that does not contain the thing you were asked to
protect, and its zero is then perfectly true and completely worthless.

> **Before any gate's zero is believed, diff what it WATCHES against what the
> item's acceptance criteria NAME.**

**Reference case — `doctor_edit_patterns`, 2026-08-06.** T5's spec said, in as
many words: *"the guard must also catch `doctor_edit_patterns` (DISCOVERY §B.4),
which is the table a source grep is most likely to miss and the one that LEAKS
WHOLE NOTES."* The table was absent from the guard's `CLINICAL_MODELS` through
all three adoption tranches, so **the ratchet reached zero having never looked at
it** — and `doctor_edit_patterns` stores `originalSoap` and `editedSoap` as full
text, making an unscoped read of it a LARGER disclosure than an unscoped read of
a visit row.

⚠️ **NOTHING WOULD EVER HAVE SURFACED IT.** Both of its reads happen to be
correct. No test failed. No sweep complained. There is no observable difference
between "the guard watched it and found nothing" and "the guard never watched
it" — which is precisely why the spec named the table by hand instead of trusting
whoever built the model list.

It was found by **re-reading the item's own acceptance criteria while writing the
close-out row** — not by any check, and after the gate had already been declared
met. So the discipline is a step, not an instinct:

1. **List what the gate watches.** Literally: the model list, the path globs, the
   route set, the table names. If you cannot enumerate it, that is the finding.
2. **List what the spec names.** Its acceptance criteria, its DISCOVERY
   references, the tables and surfaces it calls out by hand.
3. **Diff the two, in writing, before claiming the gate is met.** Anything the
   spec names and the gate does not watch is an open item, however green the run
   was.

**"The gate passing is not the gate covering what was asked."** A spec is a
checklist, and the most confident-looking zero in a programme is the one produced
over a universe nobody re-checked.

## NOTHING REACHES `main` OUTSIDE A PR — DOCS INCLUDED

**`main` is what deploys. A commit that arrives outside the gate is a commit
nothing verified**, and "it's only documentation" is the reasoning that makes the
exception, every time.

⚠️ **AND THE COST IS NOT HYPOTHETICAL, IT IS IMMEDIATE.** On 2026-08-07 a
docs-only commit was pushed straight to `main` while the merge-commit citation
for the deploy was still running. GitHub cancels in-flight runs on a new push to
the same branch, so the push **destroyed the citation it was waiting for** —
`CI`, `e2e` and `a11y-ci` all went `cancelled` — and restarted the clock by
~45 minutes. The commit was two markdown files.

The second cost is subtler and worse: for a few minutes `main` carried a commit
with no citation at all, and a deploy taken in that window would have shipped
something no gate had seen. The content being harmless is luck, not a property
of the process.

#### THE RECOVERY PATTERN, when it happens anyway

**Do NOT re-run the cancelled past.** The cancelled runs describe an ancestor
commit, and re-running them proves something about a tree that is no longer
`main`.

> **Cite the DESCENDANT — a full citation on the exact commit that will
> deploy.**

That is strictly stricter than what was lost: the new head contains everything
the merge commit did, so its citation covers the same code *plus* the stray, and
it certifies the thing that actually ships rather than its parent. Wait for it in
full; do not deploy the parent's evidence.

## THE LIST IS THE DRIVER, NOT THE CONTEXT

**When a sweep produces an enumeration, the fixing pass ITERATES THE LIST.** Each
entry is marked fixed or not-applicable **with its evidence**, and completion
means *the list is exhausted* — never *"the other signals went quiet."*

This is the operational form of **"naming a class is not enumerating it."** That
rule catches the case where the list was never built. This one catches the case
where it was built, printed, read — **and then not used.**

⚠️ **REFERENCE CASE, 2026-08-07 — five enumerated, zero fixed.** A by-table sweep
for `note_templates` printed `noteTemplate — 5 ORM creates`. The fixing pass then
followed two OTHER signals: the raw-SQL grep (4 helpers) and whatever `tsc`
surfaced (2 sites). The five fell between them — invisible to `tsc` because the
shared client is `any`, and not raw SQL either. Both signals went quiet, the work
felt done, and CI failed on a CHECK constraint in the T1 seed.

    A LIST THAT IS PRODUCED AND NOT WORKED FROM IS A COMMENT.

The shape that prevents it:

    for each entry in the enumeration:
        fix it, or record why it is not applicable
    assert: every entry accounted for

**"The errors stopped appearing" is not a completion criterion** — it is a
statement about your detectors, and detectors have coverage. The list is the
contract; the detectors are a convenience.

## EVIDENCE IS ONLY EVIDENCE ON THE TREE IT DESCRIBES
### A count inherited from another report, then incremented by assumption

**Same family, arriving through arithmetic instead of a command.** A number
carried forward from somebody else's write-up is inherited evidence: it
described *their* tree at *their* moment. Adding to it without re-measuring
manufactures a figure that was never observed by anyone.

> **"A count carried forward from another session's report and then incremented
> by assumption is a fabricated number, however small the increment."**
> — FOUNDATION session 04, 2026-08-10, catching it in its own draft

The instance: a row was drafted saying `nightly-tests` had failed **four**
nights and filed a **fourth** issue. The previous session's report had already
counted the 08-10 run; this one assumed a new failure had appeared overnight and
added one. Re-measured before committing —
`gh run list --workflow nightly-tests.yml` gives **3** failures after 3
successes, and `gh issue list` gives exactly **three** issues.

⚠️ **It was caught in the drafting, not by a check, and nothing would have
caught it later** — a plausible count in a ledger row is indistinguishable from a
measured one once it is committed. **Re-measure any number you did not observe
yourself, in the same pass that you write it down.**


**Every verification chain guards on the state transition it assumes — a rebase's
or merge's exit code, a clean `git status` — BEFORE its numbers count.**
Measurements taken mid-rebase, mid-merge or on a dirty tree are **fabricated by
accident**: they are real outputs of a real command describing a tree that does
not and will not exist.

> **The mechanism is almost always an `&&` chain that does not guard the
> transition.** `git rebase … | tail -1` swallows the failure, the next command
> runs anyway, and its numbers look exactly like success.

⚠️ **REFERENCE CASE, 2026-08-07.** A rebase reported *"Could not apply"*, the
chain continued, and `tsc`/`vitest` printed **"0 errors / 3194 passed" from a
half-merged tree with conflict markers in it.** The push that followed was
harmless — during a rebase the branch ref still points at the original commits,
so the remote received the un-rebased branch — but the EVIDENCE was worthless
while looking authoritative. Re-measured after resolving: the same numbers, now
meaning something.

The shape that prevents it:

    git rebase origin/main || { echo "REBASE CONFLICT — stop"; exit 1; }
    git status --porcelain | grep -q . && { echo "DIRTY — stop"; exit 1; }
    # only now do measurements count

**And when it happens, say so.** Numbers printed from a broken tree must be
withdrawn explicitly, not quietly re-run — a reader who saw the first pair has no
way to know the second replaced them.

## A PUSH IS CHECKED FOR IN-FLIGHT RUNS **BY COMMIT *AND* BY BRANCH**, BEFORE IT HAPPENS

**GitHub cancels in-flight runs when a new commit lands on the same branch.**
That is not a bug to work around, it is the mechanic — so a push is a decision
about somebody's evidence, and it must be made deliberately.

> **Before pushing to any branch with required runs, take BOTH views:**
>
>     gh run list --commit "$(git rev-parse HEAD)"                    # full 40 chars
>     gh run list --branch "$(git rev-parse --abbrev-ref HEAD)"
>
> **Believe a zero only when BOTH are empty.** Then either WAIT, or state in the
> log that the cancellation is deliberate.

⚠️ **FOURTH OCCURRENCE — AND THE SECOND OF THE *PR-BRANCH* SHAPE IN NINETEEN
HOURS.** The third is why this is a RULE and not a lesson; the fourth is why the
rule needed its BLAST RADIUS explained.

| when | what was destroyed |
|---|---|
| 2026-08-07 | a docs-only push to `main` cancelled the merge-commit citation it was waiting for — `CI`, `e2e` and `a11y-ci` all `cancelled`, ~45 minutes lost, and for a few minutes `main` carried a commit no gate had seen |
| 2026-08-08 | merging one PR seventeen minutes after another cancelled the first's `e2e`, leaving a **3-of-4** citation on a deployed commit |
| 2026-08-09 | a feature-branch push mid-run cancelled three runs and restarted the clock |
| 2026-08-09 | **the same shape 19h later, again on a PR branch** — PR #568's docs commit, pushed 2m45s after the PR opened, cancelled `CI`, `a11y-ci` and `e2e`; only `secrets-scan` escaped, having finished 2m12s earlier |

Note the second one especially: it arrived through a **legitimate PR merge**, not
a stray push. "Nothing reaches `main` outside a PR" does not protect you here —
the merge *is* the push.

⚠️ **AND EVERY OBVIOUS TOOL FOR THIS CHECK LIES — THREE OF THEM NOW, ALL IN THE
DIRECTION THAT COSTS A RUN.**

| surface | lies how |
|---|---|
| `gh pr checks` | reports `pending` for a run already `completed/success` — waits for nothing, or calls a finished citation incomplete |
| `gh run list --commit <SHORT-sha>` | returns **`[]`** for **ANY** abbreviated SHA, whatever the runs are doing — exit 0, no warning, no *"ambiguous"* |
| `gh run list --commit <FULL-sha>` | returns **`[]`** in the propagation window right after a push, while the runs exist and sit `pending` |

⚠️ **THE THIRD ONE DEFEATS THE FIX THE SECOND ONE PRESCRIBED.** Measured seconds
apart on the same full SHA (RELAY, 2026-08-09): `--commit` returned `[]`,
`--branch` returned three runs `pending` on that very SHA, and moments later
`--commit` returned four. **And its window is exactly when the check gets run** —
the rule exists to stop a push destroying somebody else's evidence, and the
moment that risk is highest is immediately after *they* pushed, which is
precisely when `--commit` under-reports. A session queries, sees `[]`, pushes,
and destroys four queued runs while its audit trail shows the check was
performed correctly.

⚠️ **AND IT IS INTERMITTENT — WHICH IS THE TRAP SET FOR WHOEVER TESTS IT NEXT.**
A deliberate reproduction attempt, made on the very commit that added this
paragraph, **did NOT observe the divergence**: polling both views every 3s across
a PR open, they agreed at every sample — `--commit 0 / --branch 0`, then
`--commit 4 / --branch 4`. **That is not a refutation and must not be read as
one.** A race sampled coarsely is a race missed, and the window depends on queue
conditions that vary run to run. Two consequences, and the second is the
important one: a clean two-view check is **not a guarantee** either, and **one
tidy test is not grounds to delete this rule.** The two-view form is strictly
better than one view, and that is the entire claim being made for it.

⚠️ **AND NO POSITIVE CONTROL CATCHES IT** — which is why it survived a rule that
already demanded one. The standing control asks whether the instrument works;
this instrument works perfectly. It is answering, correctly, about a set the
server has not finished populating. **That makes it the WATCHED-SET failure, not
the broken-instrument failure: the right question asked of the wrong universe,
a few seconds too early.** The two sections above name both shapes; this is the
one where the check is flawless and the universe is wrong.

> **THE RULE, TIGHTENED TWICE, AND THE SECOND TIGHTENING IS THE LOAD-BEARING
> ONE: TAKE TWO VIEWS.** `--branch` is the view that is right first. A citation
> is still taken from `--commit`, because that is what binds evidence to a SHA —
> but **a zero from `--commit` is not a fact until `--branch` agrees.**

⚠️ **AND IT APPLIES TO A PR BRANCH EXACTLY AS IT APPLIES TO `main` — INCLUDING
WHEN THE ONLY RUNS YOU CAN CANCEL ARE YOUR OWN.** The third and fourth rows above
are the same shape nineteen hours apart — #557 on `feat/b1a-vendor-request-id`,
then #568 — and that is the argument: **the class recurred within a day of the
rule being written down.**

**Reference case, 2026-08-09 — PR #568.** The PR opened at `20:28:09Z` and four
runs were created at `20:28:12Z`. The docs commit was pushed at `20:30:54Z` —
**2m45s after the PR opened** — and cancelled three of them: `CI` at 2m58s,
`a11y-ci` at 3m04s, `e2e` at 3m07s. Only `secrets-scan` survived, and only
because it had already succeeded at `20:28:42Z`.

⚠️ **AND "JUST BATCH IT" WAS NOT AVAILABLE HERE — WHICH IS THE PART WORTH
LEARNING.** The docs commit **did not exist** when the PR was pushed: it was
authored at `20:30:22Z`, two minutes *into* the run it went on to cancel. So the
habit that would have prevented this is not *combine two commits already sitting
there*; it is **hold the first push until the session's remaining commits are
written**. That is the harder rule, and it is the one this case actually teaches.

⚠️ **THE BLAST RADIUS IS YOUR OWN RUNS, WHICH IS EXACTLY WHY IT FEELS HARMLESS.**
Every workflow groups per-ref under its own prefix (`ci-`, `e2e-`, `a11y-`,
`secrets-scan-`) with `cancel-in-progress: true`, so one push cancels your
in-flight run of **each** of them — and only yours. Nobody else is inconvenienced,
nothing turns red, and the habit therefore never gets corrected by consequence.

**The recovery was CORRECT and is not what is being corrected.** The citation was
taken on the descendant, which contains everything the parent did, so nothing was
certified that no gate had seen. **The cancellation was avoidable; the response
to it was right.**

**Price the class by its worst instance, not its cheapest.** #568 discarded
**~9 runner-minutes across three concurrent runs** (2m58s + 3m04s + 3m07s) and
re-ran four jobs that had already passed, because the second commit landed about
three minutes of wall clock into the run. The identical mistake at minute forty
discards the whole gate — the 2026-08-07 row above, at ~45 minutes of wall clock.
**The cost is set by HOW LATE the second push lands; the habit is identical
either way, so do not read the cheap instances as evidence that the class is
cheap.**

**The cheap habit that avoids all of it: BATCH.** Most of these cost a cycle
because two pushes were made minutes apart where one would have done. And when a
second push genuinely must happen, it is gated by the **two-view check at the top
of this section** — both views, the full 40-character SHA, and a zero believed
only when both are empty.

## A MERGE IS A PUSH — WAIT FOR THE MERGE COMMIT, OR DECLARE THE BATCH IN ADVANCE

**Ratified 2026-08-10, and it supersedes "batch and declare at merge time".**
The push-side rule above is about *your* stray push. It does not reach the case
where one actor merges a QUEUE of legitimately separate PRs back to back — there
is no stray push to avoid and nothing to batch into one.

> **After merging, WAIT for the merge commit's runs before merging the next PR.
> Or DECLARE THE BATCH IN ADVANCE — in the log, BEFORE the first merge — so any
> other actor waiting on a run can be accounted for.**
>
> **"Declared at merge time" is not a declaration. It is a narration.**

The descendant-citation recovery stays the cure when it happens anyway; it is
not a licence to plan around.

⚠️ **REFERENCE CASE — FOUND BY THE FOUNDATION LOOP'S SESSION 04, AUDITING
SOMEBODY ELSE'S MERGES WHILE WAITING ON ITS OWN GATE.** Three pairs inside two
hours, each merged about four seconds apart:

| pair | merged | what died |
|---|---|---|
| #576 → #578 | `05:15:24Z` → `05:15:28Z` | #576's **four** runs, cancelled at 5–7s |
| #580 → #581 | `06:52:42Z` → `06:52:46Z` | #580's `e2e`, cancelled at 7s |
| #583 → #584 | `07:26:06Z` → `07:26:10Z` | #583's four runs — **and `afabbaf1`'s `e2e` at 34 minutes** |

**The third row is the argument.** Session 04 had read the two views, seen
`afabbaf1`'s runs in flight, and **deliberately chosen to wait** — exactly as the
rule prescribes — specifically so that green would discharge #580's cancelled
`e2e`. The next pair cancelled that run at **33m39s**. *The rule was followed
correctly by one party and defeated by another*, which is why it has to be a
**merge-side** habit and not only a push-side one.

Everything was discharged: `51751c0e` came back 4 of 4 and contains all four
PRs. **But it worked by luck of ordering, not by design** — and a recovery you
cannot schedule is not a plan.

## AN EXEMPTION'S REASON IS PROSE, AND PROSE DECAYS SILENTLY

**A gate can keep an exemption PRESENT. It cannot keep it HONEST.**

An exclusion list — exempted files, allowlisted paths, "known acceptable"
findings — carries two things: an entry, and a REASON. A check can assert the
entry still exists and still matches the shape it was written for. It cannot
assert the reason is still true, because the reason is a sentence about code
somewhere else.

> **Re-read an exemption's justification BY HAND whenever the code it describes
> is touched.** Nothing else will.

⚠️ **REFERENCE CASE, 2026-08-10 — B4 vs the metering gate.**
`gate-mock-suite-stubs-the-db.test.ts` exempted `embed-mock.test.ts` with the
reason *"embed.ts:72 returns mockEmbed() under mock, ABOVE the logApiUsage calls
at :123/:162 — the meter is never reached."* True when written. **B4 moved that
mock boundary below the meter, and the sentence became false** — while the gate's
stale-exemption arm stayed green, because the file still existed and still named
the flag. Both of the things it checks remained true.

The removal was caught by the session doing B4, reading the exemption because it
was touching the code it describes — not by any check. This is the watched-set
rule (§"A gate's WATCHED SET is diffed against the spec's NAMED set") pointed at
an EXCLUSION list instead of an inclusion one, and it is the more dangerous
direction: an exclusion that goes stale removes coverage silently, and the gate
keeps reporting zero.

## LEDGER AND SCHEMA CONFLICTS RESOLVE AS UNIONS

**Unless one side is provably wrong, a conflict in `RELAY.md`, `RULINGS.md`,
`SPEC.md` or `schema.prisma` is a UNION, not a choice.** These files accumulate;
they do not supersede. "Resolve by taking theirs" silently drops a landed item's
ledger row or a landed migration's relation — and the loss is invisible, because
the file still parses and the tests still pass.

⚠️ **REFERENCE CASES, 2026-08-07 — both from one rebase:**

| Conflict | Wrong resolution | Correct |
|---|---|---|
| `model Practice` — T8's `inviteCodes` vs T7's nine back-relations | either side alone | **both**; each has a migration already applied |
| `RELAY.md` — T5-W's CLOSED row vs F-TYPE's ordering | either side alone | **both**; one records finished work, the other schedules work |

Taking "theirs" on the second would have deleted the ledger row of an item that
was **already merged and deployed** — and nothing would have failed.

**The tell:** if both sides describe things that ACTUALLY HAPPENED (a migration
that ran, an item that closed), the answer is always both. A conflict is only a
choice when the two sides make incompatible CLAIMS about the same fact.

## A FIX IS PRICED BY THE ASSET BEHIND THE SYMPTOM, NOT BY THE SYMPTOM'S VOLUME

**Standing rule for every backlog row, follow-up and "🟢 nice to have".** When
you set a severity, name the thing that breaks if the item is never done — then
price *that*. A symptom's loudness is a fact about the symptom, and it is
routinely inverse to the value of what sits behind it: the quietest failures are
the ones where nothing is in an error state.

> **Ask "what is this a symptom OF?" before "how annoying is this?"**

⚠️ **REFERENCE CASE — THE 65-DAY 🟢, 2026-08-07.**
`docs/qa-reports/site-down-20260603.md` §9.5, follow-up 5 of 6, priority 🟢:

> **🟢 Caddy ACME noise** — Caddy still retries LE every ~10 min and now never
> needs to. Add `tls internal` to the quillmd Caddy blocks.

Every word of that is true. The severity is wrong by the width of the system.
The item was titled by its symptom — **log spam** — and priced accordingly. The
asset behind the symptom was **the certificate on the only path from the
internet to the application**. Sixty-five days later that certificate expired,
its storage was cleaned, a reboot dropped the in-memory copy, and every public
hostname served `502` for six hours and fifteen minutes. `/login` was 0 of 30.

The same report had already written the deadline down and nobody carried it
forward: §6.2 recorded *"Certs aren't expired (~46 days left), so this is latent,
not the outage."* **Forty-six days is a due date wearing a reassurance's
clothes.**

Three things generalise:

1. **A "noise" item that touches an expiring credential, a certificate, a token
   or a lease is not a noise item.** Rename it after the asset. `tls internal on
   the ingress hop` gets triaged; `Caddy ACME noise` gets skipped forever.
2. **"Latent, not the outage" needs a DATE and an owner, or it decays.** An
   unanswered question becomes "probably fine" through nothing but repetition —
   the same decay that left the May audit PDF tracked and unlisted for eleven
   weeks.
3. **Priority set from the symptom is unfalsifiable later.** Nobody re-reads a
   🟢 to ask whether it was priced right; the colour *is* the reason it is not
   re-read. So the pricing has to be right when written, which means it has to
   be written against the asset.

⚠️ **AND THE DOCUMENT THAT DESCRIBED THE INTENDED STATE MADE IT WORSE.**
`DEPLOYMENT_RUNBOOK.md` §5.6 had asserted since 2026-07-28 that Caddy *"sits
behind it on `127.0.0.1:8443` with its own internal certs and is not involved."*
That sentence was **false for two months**. It described what the topology was
*supposed* to be, in the present tense, and every reader took it as a statement
about the running system — so the gap between intent and reality was invisible
to anyone consulting either document.

> **A stated invariant is a WISH until something asserts it. Write the check, or
> write the sentence in the future tense.**

That is why the fix shipped with `scripts/check-ingress-tls.sh` rather than with
a corrected paragraph.

## A DEPLOY DECLARES ITS EXPECTED DELTA BEFORE IT RUNS

**Standing part of the deploy standard — `docs/DEPLOYMENT_RUNBOOK.md` §2.5.**
Capture a baseline first; for a migration-carrying deploy also write down what
MUST change and what must NOT; judge the post-deploy comparison against that
declaration. A code-only deploy's declaration is one line: **"nothing but the
image ids."**

**A post-deploy check written afterwards is unfalsifiable.** Every number has a
story available to it, and a migration supplies a ready-made excuse for *any*
movement — *"the migration touched that table"*. Declaring first removes the
excuse: the comparison has one correct answer, fixed before the evidence existed.
Same discipline as *no evidence before the event*, pointed the other way.

**A difference that is not in the declaration is THE FINDING**, whatever its
explanation sounds like after the fact. And the clinical-count row is never
omitted — a deploy that moves a visit, patient or signature count has done
something nobody asked for, and the only way to know is to have written the
numbers down while they were still true.

## A CONSTRAINT IS SWEPT BY ITS PREDICATE, NEVER BY THE ORM METHOD

**Standing rule for every CHECK, NOT NULL, unique or FK you add.** The universe
to sweep is *"every write that can produce the forbidden state"* — which is a
statement about BEHAVIOUR. `create` / `upsert` / `update` are API verbs, and the
set of verbs is the wrong universe. This is the coverage-vs-criteria class
arriving at the write layer: the sweep is flawless over a set that does not
contain the offending write.

> **Write the constraint's predicate down in words, then find every site that
> can make it false.** If you catch yourself listing method names, you have
> already substituted a proxy for the question.

⚠️ **REFERENCE CASE — T6's `users_active_member_has_practice_role`, 2026-08-07.**
The predicate is *"an ACTIVE user WITH a practice HAS a role"*. Two distinct
errors, both mine, in one sweep:

**(a) The verb filter — 9 sites vs 24.** I swept
`user.(create|upsert|createMany)` and found 9. There are **24** user write
sites; the other 15 are `update`. An `update` setting `isActive: true` on a row
with a practice and no role violates the CHECK just as a `create` does —
**reactivation is a write that can produce the forbidden state**, and no `create`
sweep will ever see it. It surfaced a real latent bug: a user deactivated BEFORE
the backfill carries a practice with a NULL role, because the backfill
deliberately skips deactivated rows, so reactivating them fails with an error
naming the CHECK and not the cause.

**(b) The inventory was taken ONE LAYER ABOVE THE FIELDS.** My scan extracted the
balanced argument of each `prisma.user.upsert(...)` and read its keys.
`seed-qa-user.ts` passes a payload built by an EXTRACTED FUNCTION, so the call
site holds a *variable* — the scan reported `practiceId=False` and I believed it.
CI failed on that exact seed. This is the costume already named in the write-path
section above, worn again: **the thing lived one layer down.**

    A sweep over call sites cannot see fields that are assembled elsewhere.
    Sweep the FIELD (`practiceId:` in any object that also carries user-shaped
    keys), not the CALL — or read every payload builder by name.

**The corollary rule, from the fix:** *no-downgrade applies to reactivation too.*
Restore `OWNER` **only where the row has a practice and no role** — never
unconditionally, which would overwrite a real CLINICIAN or TECH assignment with
an owner's rights the moment somebody was un-suspended.

## A FIRE-AND-FORGET WRITER IS PROVED ONLY BY A TEST THAT READS IT BACK

**Standing rule for audit rows and every other side effect written with `void`,
`.catch(() => {})`, or a detached promise.** If nothing awaits it and nothing
reads it, its failure is invisible by construction — and that is usually
deliberate, because an audit write must never break a clinical action.

> **A gate that claims "and the refusal is audited" has not been tested until
> something queries the row.** Otherwise the claim is a comment.

⚠️ **REFERENCE CASE — THE SAME DEFECT THREE TIMES.** `AuditAction` values live in
three places, and each layer looks sufficient from the one above it:

| Layer | Passes when the layer below is missing? |
|---|---|
| the TypeScript union in `audit.ts` | ✅ `tsc` is happy |
| the Prisma enum in `schema.prisma` | ✅ `prisma validate` is happy |
| **the Postgres enum** — needs its own `ALTER TYPE … ADD VALUE` migration | ❌ the write throws at runtime |

- **2026-08-03** — a sign refusal shipped whose audit row silently did not: the
  union was updated, the Prisma enum was not. Banked then as *"the TS union is
  not the database"*.
- **2026-08-06, attempt 1** — an edit landed in `audit.ts` only, because the
  `schema.prisma` anchor missed on indentation. Caught by an occurrence
  assertion (see the section below).
- **2026-08-06, attempt 2** — landed in **both** and still not in the database,
  because a Prisma enum VALUE requires its own migration. `prisma validate`
  passed, `tsc` passed, **3192 unit tests passed**, and the refusal fired
  correctly with a 403. The app logged
  `invalid input value for enum "AuditAction"` and swallowed it.

**Only an E2E that queried `audit_logs` for the row caught it.** So:

1. **Adding an enum value is THREE edits**, and the third is a migration. Check
   `pg_enum` after applying, not `prisma validate`.
2. **Every audited gate asserts the ROW**, by action and target — not the status
   code. The status code is written by the branch you can see; the row is
   written by the part that fails silently.
3. **Do not "fix" this by awaiting the audit write.** The fire-and-forget is
   correct: a failed audit must not refuse a doctor's sign. The cure is a test,
   not a stricter runtime.

## "RESTORE FROM GIT" AND "RESTORE FROM BACKUP" ARE NOT THE SAME OPERATION

**Standing rule for every mutation proof.** Before the FIRST mutation, copy
**every file the proof will touch** to scratch, and assert the copies exist. The
restore step then reads from those copies — never from git.

> **`git checkout -- <file>` restores the file to HEAD. On a dirty tree that
> DELETES uncommitted work, silently and unrecoverably.**

⚠️ **REFERENCE CASE, 2026-08-08 — B0-a, mid-proof.** Three files were backed up
to scratch and restored from there. A fourth, `anthropic.ts`, carried the
session's entire uncommitted rewire and was restored with
`git checkout -- packages/ai/src/anthropic.ts`. It reverted to HEAD; three
rewired call sites and two markers vanished. Nothing errored — the command
succeeded, which is exactly what it was asked to do.

The tell that it happened at all was a test count: the suite went from 4 passed
to 3 failed on a "restore" step. **Had the mutation under test been one that
leaves the suite green, the loss would have been silent** and the branch would
have been committed missing its own feature.

Two things generalise:

1. **The backup list is the file list, not the interesting files.** The three
   backed up were the ones the mutations targeted. The one lost was merely *the
   file being tested* — not obviously part of the proof, and the only one that
   mattered.
2. **Assert the backups before mutating**, the same way a scripted edit asserts
   its occurrence count. A restore that reads a file that was never written is
   a second silent failure stacked on the first.

## WAR-ROOM RULINGS ARE RECORDED BY THE RECEIVING SESSION, IN ITS FIRST COMMIT

**A ruling that exists only in a session transcript is not a ruling.** The
session that receives one writes its row into `docs/foundation/RULINGS.md` in the
first commit it makes — before building anything that depends on it.

> **AND NO BRIEF'S CLAIM ABOUT RULINGS STATE IS TRUSTED. GREP IT.**
> "They're all there" is a claim about a file, and claims about files are
> verified here like every other claim.

⚠️ **REFERENCE CASE, 2026-08-08.** A brief instructed: *"per the recorded rulings
(grep RULINGS.md, they're all there)."* They were not. Four rulings had been made
in the war room — mocked `ai_calls` suppression, the provenance-default rule,
usage rows mirroring calls, the content-sensitive mock — and **none had been
written down**. Only an unrelated fifth was present.

The instruction was right to say *grep it*, and the grep is what found the gap.
Had the session built from its memory of the conversation instead, the code would
have encoded four decisions with no durable record — and the next session,
finding nothing in `RULINGS.md`, could have reached the opposite conclusion just
as confidently. **That is the CONTRADICTION failure the file exists to prevent,
arriving through the one channel nobody guards: the ruling that was made
correctly and simply never landed.**

The rule is therefore about the RECEIVING end, deliberately. The war room states
the ruling; the session that acts on it is the one that must leave the artifact,
because it is the one holding the evidence that the ruling was made.

## A scripted edit PROVES ITS OWN APPLICATION

**Every `.replace()` / `sed` / regex-rewrite pass states the number of
occurrences it expects and asserts the number it actually changed. A mismatch
aborts.** Files with `assert count == N` before writing; sweeps by printing
`expected N / measured N` per file and failing on any zero.

Why: **`.replace()` on a non-match is a silent no-op that returns the original
string, and the script then reports success.** On 2026-08-06 an edit script
matched `where: { id: visitId },` at six-space indent against two files that
use four. The import landed, the **author check was removed**, and the practice
predicate never applied — leaving `loadVisitExportData` and `nativePdfExport`
returning **any visit to any authenticated caller**. Every other file in the
same pass was fine, the script printed a clean table, and `tsc` was silent.

⚠️ **A partial application is more dangerous than a total failure.** A script
that changes nothing is obvious in the diff. A script that applies half of a
two-part edit — remove the old guard, fail to add the new one — leaves code that
compiles, passes review as "the migrated shape", and is wide open. Prefer edits
that cannot half-apply: assert the occurrence delta, and where the two halves
must move together, make them one replacement rather than two.

This is the same family as **"a script that prints a number it does not act
on"** — the output describes an intention, and nobody checks it against the
effect. Here the number was never printed at all, which is worse.

*Corollary, earned in the same pass:* **a rename does not protect when the types
are identical.** `loadVisitExportData(visitId, userId)` had its second parameter
renamed to `practiceId`; **nine call sites kept passing a user id** and `tsc`
accepted all nine, because both are `string`. It failed closed — a user id
matches no practice — but the compiler should have caught it and could not.
Contrast, same commit: `captureEditPattern({ … practiceId })` broke **loudly at
every call site**, because a required NAMED property cannot be confused with a
same-typed neighbour. **When changing what a positional parameter MEANS, change
its shape (named property, branded type), not only its name.**

## PROSE IS NEVER A SHELL ARGUMENT

**Any command carrying human prose — a PR body, a review comment, a commit
message, issue text — is passed by `--body-file`, `-F`, or stdin. NEVER as a
quoted argument.** Backticks in prose are command substitutions waiting for a
shell, and prose is exactly where backticks live: every time you write
`` `npm ci` `` to name a command, you have written an instruction to run it.

⚠️ **REFERENCE CASE, 2026-08-10 — AND IT RAN.** A PR description was passed as
`gh pr create --body "…"` inside double quotes. The body named commands the way
this file does, in backticks. Bash evaluated them:

- `` `npm ci` `` **executed, to completion, in the FOUNDATION loop's live
  working tree** — `exit 0`, `info ok`, `node_modules` rewritten while an
  unattended session was mid-item.
- `` `landing-monolith/deploy/deploy-staging.sh` `` — a path named in a
  *sentence* — was **invoked as a command**. It failed with `Permission denied`
  only because that file is not executable. **That is luck, not a control.**

The tree survived: the lockfile was unchanged, so `npm ci` reinstalled exactly
what was locked, `sharp` and its six `@img` binaries came back, and the five
workspace symlinks were intact. None of that was by design. A prose mention of
a *deploy* script came one file-mode bit away from running it.

**The rule is mechanical, so obey it mechanically:** write the body to a file,
pass the path. `gh pr create --body-file`, `gh pr comment --body-file`,
`gh pr edit --body-file`, `git commit -F`. If a heredoc is unavoidable, quote
the delimiter (`<<'MSG'`) so the shell expands nothing.

### And a reassurance check needs a POSITIVE CONTROL like any other

The same incident, second half. Asked whether the accidental `npm ci` had
touched anything, the first check was
`find node_modules -newermt '30 minutes ago'` → **0**, read as an all-clear.
It was wrong. `stat -c '%y'` on the same directory said `06:20:48`, one minute
earlier — the install had rewritten it.

**A check run to prove nothing happened is the one most likely to be believed
without scrutiny, and the least likely to be controlled.** It is the emptiness
test from §"positive-control every zero", arriving at the moment you most want
a clean answer. Before believing an all-clear: run the same matcher against
something you KNOW is present, or answer with a second, independent tool. Two
tools disagreeing is a finding; one tool agreeing with your hope is not
evidence.

## The substring trap — fourth sighting, same family

`'practice-scope' in source` — an import-insertion guard — matched the word
**"practice-scoped"** in a comment written moments earlier, so two imports were
silently skipped and `tsc` named the missing symbol instead of the real cause.

The family, so the shape is recognisable rather than re-derived each time:

| Sighting | The trap |
|---|---|
| `'dashboard'` contains `'board'` | a flag-ON assertion passed on the flag-OFF label — asserted nothing |
| `backgroundColor` ends in `color` | a matcher-shape census miscounted its own negative control |
| `'practice-scope' in source` matches `"practice-scoped"` | an idempotence check satisfied by PROSE, so a required import was skipped |

**The rule stands and is now cheap to state: prefer `toBe` over `toContain`
whenever the expected value is knowable; when a substring genuinely is the right
shape, check the two candidates are not substrings of each other; and for
"is this already present" checks, match the EXACT token that would be present —
`from '@/lib/practice-scope'`, never the bare word.** Prose is not a proxy for
code, and a file's comments are the one place where the words you are grepping
for are guaranteed to appear.

## Multi-session programs have relay ledgers — READ THEM FIRST

A relay ledger is the contract between sessions. It says what is built, what is
next, and what proof exists. **Nothing in this file used to point at one, which
is how a session can open, do good work, and duplicate or contradict a ruling
made three sessions ago.**

| Program | SPEC (what to build) | RELAY (what is built, what is next) |
|---|---|---|
| **Rounds** — the shipped skin | `docs/rounds/SPEC.md` | `docs/rounds/RELAY.md` |
| **Foundation** — teams → billing → admin | `docs/foundation/SPEC.md` | `docs/foundation/RELAY.md` |

⚠️ **AND BEFORE DECIDING ANYTHING RULING-SHAPED, GREP
`docs/foundation/RULINGS.md`.** It is a one-line index of every war-room
decision — date, verdict, pointer — and it exists because a session
rediscovered a standing ruling on 2026-08-06 and wrote a fresh argument for a
question already answered two days earlier. That instance cost nothing; the
failure mode is not duplicated effort but **CONTRADICTION**, because a session
that cannot see a ruling can reach the opposite conclusion just as confidently
and ship it. **Rediscovery is a process smell, not a virtue.** New rulings append
a row in the same commit that records them in full.

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
bash scripts/assert-migrations-applied.sh --qa # READ-ONLY. same, against the QA stack
bash scripts/check-qa-mock-posture.sh         # READ-ONLY. 0 = severed, 1 = LIVE KEYS, 2 = stack down
bash scripts/check-minio-encrypted-mount.sh   # READ-ONLY. 0 = encrypted, 1 = DRIFT, 2 = can't tell
bash scripts/check-pg-encrypted-mount.sh      # READ-ONLY. 0 = encrypted, 1 = DRIFT, 2 = can't tell
bash scripts/check-ingress-tls.sh             # READ-ONLY. 0 = all SNIs OK, 1 = 502ing, 2 = can't tell
bash scripts/check-composite-fk.sh            # READ-ONLY. 0 = intact, 1 = ABSENT/RESHAPED, 2 = can't tell
bash scripts/check-bind-mount-agreement.sh    # READ-ONLY. 0 = agrees, 1 = DIVERGED, 2 = can't tell
```

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
