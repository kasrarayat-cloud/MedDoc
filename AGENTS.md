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


## HOW THIS FILE IS ORGANISED — read this once

**This file is the LIVE INSTRUCTION SET. It is not the whole canon.**

On 2026-08-26 `AGENTS.md` was **243,023 characters** against a **150,000-character
tool read limit** — so a session could load a *truncated* rulebook and never be
told. A rule you cannot read is not a weaker rule, it is an absent one, and the
absence is silent. That is a stale-authority hazard, not a formatting problem.

The file was therefore **SPLIT, never trimmed**:

| where | what | authority |
|---|---|---|
| **this file** | standing authority, the doctrines a session executes (deploy/§2.5, push & merge, the clinical-generation gate, close-out, hygiene), and current-arc state | governs |
| **`docs/canon/`** | every canon entry's FULL body, verbatim and dated | **governs** |
| **the CANON INDEX**, at the end of this file | one row per archived entry: its title, its own stated tell, and a pointer | **pointer only** |

> **AN INDEX ROW IS A POINTER, NEVER THE RULE.** If a row and an archived body
> ever disagree, the body is right and the row is a defect — fix the row.
> Nothing in `docs/canon/` is rewritten: corrections are appended and dated, and
> superseded wording is kept, because in this programme the correction is the
> point.

**Citations still resolve.** Every archived entry keeps its exact title in the
index, so the existing references from `MASTER.md`, `RELAY.md`, `RULINGS.md`,
the runbooks and the reports still land — and now land on a pointer that says
where the body is.

**Adding canon:** a new entry's full body goes in `docs/canon/` and its one-line
row goes in the index, in the same commit. Do not grow this file back.

**The guard, so this cannot silently recur:**

```bash
bash scripts/check-agents-md-size.sh   # READ-ONLY. 0 = under budget, 1 = OVER, 2 = can't tell
```

It fails at **120,000 characters** — a deliberate floor well under the 150k read
limit, so the alarm arrives with room to act rather than after truncation has
already happened. CI enforces the same budget through
`gate-agents-md-size.test.ts`, which drives that script rather than
re-implementing it, so the two cannot drift.

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

## THE ADVERSARIAL PASS IS MANDATORY ON THE CLINICAL GENERATION PATH

**Standing 2026-08-14, and it is a gate, not a nicety.** For any change to the
clinical generation path — L4/L5/L6, the prompt builders, the assemblers, the
fidelity gates, anything that decides what text reaches a note — **a refutation
pass over the FINISHED DIFF runs before merge.**

> **Told to REFUTE, not to review.** "Find the counterexample; default to *this
> is broken*; report only what you can demonstrate with a concrete input → wrong
> output." A reviewer asked whether the code is good says yes to code that is
> good and wrong.

⚠️ **THE ARGUMENT IS ONE NIGHT'S EVIDENCE.** On 2026-08-14 the pass found
**fifteen** defects in a branch that had already been proven, pushed, and
CI-cited. Two would have deleted clinical content from a signed imaging report.
Neither was reachable by the suite, the mutation proofs, or the QA walk —
because all three shared the author's assumptions about which universe mattered.
**It was the only thing between a green branch and clinical harm.**

What makes it work is that it does not share the author's context:

- give it the CLAIMS, not the intent — "this asserts X; break X";
- give it **distinct lenses** (data loss, byte-identity, migration/schema,
  false-green-and-false-rejection), because redundancy finds one failure mode
  four times;
- require **FILE:LINE + a concrete input → wrong output**, and permit
  `NOTHING FOUND` — an invented finding is worse than none;
- **verify every finding yourself before believing it.** Two of the fifteen were
  confirmed against production before a line was changed, and one reframed a
  standing ruling.

⚠️ **AND THE COMPANION MOVE IS RECORDED WITH IT: MARK THE PR A DRAFT AT THE
MOMENT OF DOUBT.** Not after triage, not once severity is known — at the moment.
Converting takes one command and makes the branch unmergeable by anyone,
including a future you at 01:00 with the findings half-read. It is the cheapest
possible action and it is reversible; the state it prevents is not.

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
| `gh pr edit --body-file` | **fails outright, exit 1**, on `GraphQL: Projects (classic) is being deprecated … (repository.pullRequest.projectCards)` — this `gh` build queries a sunset field on every `pr edit`. ⚠️ **It prints as a deprecation NOTICE and reads like a warning; the edit does not happen.** Verified 2026-08-12: two attempts, body unchanged both times. **Use the REST API instead** — `gh api repos/<owner>/<repo>/pulls/<n> -X PATCH -F body=@<file>` (exit 0), which also keeps prose out of the shell. **Then re-read the body and confirm**: a correction you believe landed and did not is worse than one you never attempted |
| `gh pr merge --delete-branch` | **NOT ATOMIC — the merge succeeds and the branch deletions can half-fail, reporting only one of them.** Verified 2026-08-12 on PR #621: it merged, printed `failed to delete local branch … used by worktree`, and left the **remote** branch alive too — a failure it never mentioned. ⚠️ **Reading that error as "only the local one failed" leaves a merged branch on origin forever.** Retire with `bash scripts/retire-branch.sh <branch>`, which checks both sides and refuses to claim a success it did not earn — or delete each side by hand and CONFIRM with `git ls-remote --heads origin <branch>` |

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

⚠️ **AND ON 2026-08-27 IT WAS OBSERVED LIVE, WHICH PARTLY CLOSES THAT GAP.** The
FOUNDATION loop's session 02 (run `20260827-041645-b1`) reported, in its
close-out:

> *"I observed the `--commit` vs `--branch` **propagation-window divergence
> live** (by-commit empty, by-branch 4 runs, seven seconds apart, on a
> `git rev-parse`-verified SHA)."*

**GRADED PROVENANCE, STATED SO IT IS NOT READ AS MORE THAN IT IS.** This is a
**report of an observation** lifted from a session log — not raw command output.
The log carries the loop's own summary; the underlying two-view transcript did
not survive, and session logs are gitignored, so lifting it here is what makes it
a finding at all rather than a lost transcript. It is stronger than memory and
weaker than a captured terminal, and it is filed as such.

**What it changes:** the paragraph above says a deliberate reproduction attempt
did NOT observe the divergence, and that stands. The phenomenon now has **one
live observation with a verified input** beside **one failed reproduction** — so
the two-view form remains the practice for exactly the reason already given. One
clean test was never grounds to drop it; one sighting is not grounds to call it
reliable either.

⚠️ **AND A WITHDRAWN CLAIM STAYS WITHDRAWN.** A supervised session the same day
recorded this same divergence as observed and then withdrew it: its `--commit`
was empty because the SHA had been **fabricated from memory**, so the instrument
was answering correctly about a commit that does not exist. The loop's sighting
does not reinstate that claim — they are different events, and only the loop's
carries a verified input. Full account:
`docs/canon/61-a-documented-defect-is-the-most-convenient-suspect.md`.

⚠️ **AND NO POSITIVE CONTROL CATCHES IT** — which is why it survived a rule that
already demanded one. The standing control asks whether the instrument works;
this instrument works perfectly. It is answering, correctly, about a set the
server has not finished populating. **That makes it the WATCHED-SET failure, not
the broken-instrument failure: the right question asked of the wrong universe,
a few seconds too early.** The two sections above name both shapes; this is the
one where the check is flawless and the universe is wrong.

### THE RULE IS NOW A HOOK, BECAUSE FIVE OCCURRENCES SAID IT HAD TO BE

**Ratified 2026-08-12.** Everything above stayed true and kept not reaching
behaviour — the fifth instance was a session amending and force-pushing three
minutes into its own run, cancelling `CI`, `e2e` and `a11y-ci`. **A rule that
does not change what happens becomes mechanism**, the same move the §2.5
declaration made.

`scripts/hooks/pre-push` takes BOTH views on every pushed ref's current remote
head and **refuses** while any run there is not `completed`.

⚠️ **IT MECHANIZES THE PUSH SIDE ONLY — SAID HERE SO THE NAME DOES NOT READ WIDER
THAN THE WATCHED SET.** `gh pr merge` merges SERVER-SIDE and never invokes a
client hook, so a merge is invisible to this file. The **MERGE** side — the next
section, which has the worse record of the two — is guarded by
`scripts/merge-pr.sh`. Two doors, two guards, **one shared check** in
`scripts/lib/inflight.sh`, because a second copy of that logic would drift from
the first the day either is fixed.

- ⚠️ **IT IS FAIL-CLOSED ON CANNOT-TELL.** No `gh`, an unauthenticated `gh`, a
  failed query, or a remote sha that is not 40 characters all REFUSE. A broken
  instrument and a quiet branch produce the same zero, so the hook
  **positive-controls first** — it confirms the runs API answers for this
  repository at all before believing any zero it returns.
- **The legitimate override is a DECLARATION, not a bypass** — the batching
  rule's own path:

      DECLARE_CANCELLATION="merging #618 and #619 as one batch; #618's e2e is
      mine and I am discarding it knowingly" git push …

  The reason is echoed to stderr, which IS the log for an unattended session.
  ⚠️ **A bare `1`, `true` or `yes` is REFUSED, as is anything under 12
  characters.** A declaration wearing a token's clothes is a bypass, and an
  audit trail's "why" is somebody's words or nothing.
- ⚠️ **HOOKS DO NOT TRAVEL WITH A CLONE.** `core.hooksPath` is set by the root
  `prepare` script on `npm install`; a clone that never installed carries the
  hook FILES and runs none of them, and nothing anywhere would say so. That is
  why STEP 0 asserts it rather than assuming it —
  `bash scripts/check-hooks-installed.sh`. **A stated invariant is a wish until
  something asserts it.**
- ⚠️ **A HOOK CAN BE COMMITTED INERT — `core.fileMode` is `false` here.** Set the
  bit in the INDEX (`git update-index --chmod=+x`), and verify with
  `git ls-files -s scripts/hooks/`. Full trap in §"A scripted edit PROVES ITS OWN
  APPLICATION" — it is that class, not a hook-specific quirk.

### ⚠️ AND THERE IS A THIRD DOOR: `gh pr ready` FIRES WORKFLOW TRIGGERS

**Standing 2026-08-23. Found by the loop, on its own PR, one minute after
performing the two-view check correctly.**

Both mechanized doors are guarded at the point a **COMMIT** moves.

> **`gh pr ready` lands no commit and cancels runs anyway.** Converting a draft
> emits a `ready_for_review` event; any workflow listening for it starts a NEW
> run on the same ref, and `cancel-in-progress` resolves that by killing the one
> already running.

**MEASURED ON PR #812.** The push of `1e4e9807` was preceded by both views, both
empty, nothing destroyed. `gh pr ready` ran ~1 minute later:

| run | fate |
|---|---|
| `a11y-ci` `32652002368` (push-triggered) | **cancelled at ~1 min** |
| `a11y-ci` `32652059194` (ready-triggered) | started, later `success` |

⚠️ **THE TELL WAS ARITHMETIC, AND IT IS THE ONLY REASON IT WAS NOTICED:** the
branch view showed **five runs for four workflows**, `a11y-ci` twice. *ARITHMETIC
THAT DOES NOT RECONCILE IS A FINDING* caught a cancellation no rule was watching
for.

**WHY IT ESCAPES THE EXISTING GUARDS, and this is the generalisable half:**
`gh pr ready` reads as a **metadata flag** — it flips a boolean on the PR — so
nothing about it suggests *this is a push*. It is not denied, not hooked, and
was not mentioned anywhere.

> **ANY API CALL THAT EMITS AN EVENT A WORKFLOW SUBSCRIBES TO IS A PUSH FOR
> CANCELLATION PURPOSES** — `pr ready`, `pr reopen`, a label add where a
> workflow keys on `labeled`, a base-branch change.

**AND THE SUBSCRIBER LIST IS MEASURED, NOT ASSUMED** — which is also why exactly
ONE workflow moved rather than four:

    grep -n "ready_for_review" .github/workflows/*.yml
    -> a11y.yml:26   types: [opened, synchronize, reopened, ready_for_review]

**`a11y.yml` is the only subscriber today, and it also takes `reopened`** — so
`gh pr reopen` is a live second instance of this door right now, not a
hypothetical one. ⚠️ **POPULATION FACT WITH ITS RE-ARMING CONDITION:** one
workflow adding `ready_for_review`, `reopened` or `labeled` to its `on:` list
widens the blast radius from one run to N **with no change to any rule, script
or habit** — so that grep is the check, and it is one line.

**THE CHEAP HABIT: convert to ready BEFORE the push that carries the citation**,
or accept the cancellation knowingly and say so. Here the cost was ~1 minute of
one workflow and the fresh run superseded it, so the citation was still 4 of 4 —
⚠️ **but the cost is set by HOW LATE the event lands, exactly as the push-side
entry says, and the identical action at minute forty discards a 40-minute
`a11y-ci` with nothing flagging it.** Do not read the cheap instance as evidence
the class is cheap; that sentence is already in the push-side entry, and this is
its next costume.

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

### THE MERGE SIDE IS NOW MECHANIZED TOO — `scripts/merge-pr.sh`

**Ratified 2026-08-12.** The pre-push hook cannot see a merge: `gh pr merge`
merges server-side and never invokes a client hook. So the rule above stayed
rule-only while the PUSH side became mechanism — and **this side has the worse
record of the two** (a 3-of-4 citation on a deployed commit; a run killed at
33m39s that another session was deliberately waiting for).

> **`gh pr merge` is DENIED. `bash scripts/merge-pr.sh <pr>` is the only door.**

It takes the same two views — the shared check in `scripts/lib/inflight.sh`, not
a second copy — on the **PR's own base branch**, read from the PR rather than
assumed to be `main`, and refuses while anything there is running. The declared
batch is the legitimate override:

    DECLARE_CANCELLATION="merging #618 and #619 as one declared batch;
    the cancelled e2e is mine" bash scripts/merge-pr.sh 619

⚠️ **AND IT RE-READS THE PR AFTERWARDS RATHER THAN TRUSTING THE EXIT CODE.**
`gh pr merge --delete-branch` is already on record reporting one failure while
silently leaving another, so the wrapper only prints green when the PR actually
says `MERGED`. **Every refusal arm was proved to refuse BEFORE attempting the
merge**, asserted by recording whether `gh pr merge` was invoked at all.

⚠️ **Same honest limit as `retire-branch.sh`:** a deny matches the command the
agent RUNS, not what a script it runs does internally, so the wrapper is a hole
in its own deny by construction. Conservative on purpose; widening it is a
war-room question.

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

## THE SHARED TREE IS A DEPLOY SURFACE, NOT A WORKSPACE

**Standing 2026-08-14.** `/opt/meddoc-pro` stays on `main` and clean. **All
feature work happens in an isolated `git worktree`.** A session that checks a
branch out in the shared tree has moved a deploy surface, and that is now a
named hazard rather than a matter of taste.

> **Two sessions, one working tree, is a CLASS — not two incidents.**

⚠️ **BOTH HALVES OF THE HAZARD ARE REAL AND NEITHER IS OBVIOUS.**

**1 · `deploy-prod.sh` deploys the tree's HEAD, whatever it is.** It reads
`git rev-parse HEAD` from the tree it runs in and names its §2.5 declaration
after that SHA. Caught on 2026-08-14 with a deploy fully staged: the shared tree
had been checked out to another session's `feat/rc2-…` branch at the previous
commit, so the deploy would have shipped **the prior release without the change
being deployed**, under a declaration naming the wrong commit. **A declaration
naming the wrong commit is worse than no declaration, because it looks like
evidence.**

**2 · YOU CANNOT SIDESTEP IT BY DEPLOYING FROM A WORKTREE.** The obvious
workaround is the more expensive mistake. `docker-compose.yml` carries RELATIVE
bind mounts — `./Caddyfile`, `./infra/postgres-backup/postscript.sh`,
`./infra/backup-offsite-sync.sh` — so `docker compose up` from another directory
**re-points the ingress config bind at that directory**, and reaping the
worktree afterwards leaves it dangling. Verified the same night: the running
caddy container binds `/opt/meddoc-pro/Caddyfile` by absolute path. The
worktree route trades a wrong-commit deploy for a broken ingress.

**The two incidents that made it a class, both on 2026-08-14, both in one
night:**

| what collided | how it surfaced |
|---|---|
| one session's preflight report written beside another's uncommitted §2.5 declaration | noticed by hand; it could have muddied a `git status` cleanliness check mid-deploy |
| a feature branch checked out under a fully-staged deploy | noticed by hand, one command before `deploy-prod.sh` |

## A DEPLOY DECLARES ITS EXPECTED DELTA BEFORE IT RUNS

**Standing part of the deploy standard — `docs/DEPLOYMENT_RUNBOOK.md` §2.5.**
Capture a baseline first; for a migration-carrying deploy also write down what
MUST change and what must NOT; judge the post-deploy comparison against that
declaration. A code-only deploy's declaration is one line: **"nothing but the
image ids."**

### ⚠️ AND A RULED MUTATION GETS THE SAME GATE — STRICTER, BECAUSE IT CANNOT BE UNDONE

**Standing 2026-08-12.** `deploy-prod.sh` has refused to run without a
declaration since 2026-08-11. Ruled MUTATIONS had no such gate: the order lived
in a ruling and in whoever was executing.

> **`bash scripts/run-ruled-mutation.sh --declaration <path> -- <command…>` is
> the only door to an irreversible production act.**

⚠️ **AND "THE FILE EXISTS" IS NOT "THE FILE EXISTED FIRST" — WHICH IS THE WHOLE
FINDING.** The deploy gate asserted `[ -f "$DECL" ]`, and a file can be written
one second before the act. **Reference case, B7 step 3c's backfill: 175
irreversible rows landed at `22:50:16Z`; the declaration's only commit is
`22:52:13Z` — one minute fifty-seven seconds LATER.** All eight declared
quantities matched exactly and nothing suggests bad faith. **The record simply
cannot distinguish an honest declaration from one composed once the outcome was
known** — and that distinction was the entire product §2.5 was buying.

So the mutation gate requires the declaration to be **TRACKED, UNMODIFIED and
COMMITTED**. The act has not happened yet, so its commit timestamp provably
precedes the rows, and the runner prints both into the transcript — the commit
time and the start time bracket the act in the units the rows carry.

⚠️ **THE DEPLOY PATH IS DELIBERATELY LEFT AT `present`, NOT `strict`.** Strictness
is proportional to reversibility — ruling #96(b)'s logic. A deploy is answerable
by a rollback; requiring a commit there would refuse every deploy whose author
lands the declaration in the same PR, which is a real habit and would halt the
programme to fix the weaker case. The deploy records provenance **loudly** and
does not refuse on it. **Both call the same `scripts/lib/declaration.sh`** — one
implementation, two strictnesses, because a second copy drifts from the first.

⚠️ **AND FILE THE EVIDENCE WHERE GIT WILL TAKE IT: `docs/deploy-reports/` IS
TRACKED, `docs/deploy-logs/` IS GITIGNORED.** The two names are one word apart
in meaning and opposite in behaviour. Both sessions hit this on 2026-08-14 from
different directions — one had `git add` refuse (loudly, and caught), the other
had a `cp` into a citation PR silently contribute nothing (caught only by
reading what the commit actually contained, rather than trusting `git add -A`).
**A verification written to the ignored path looks committed and is invisible**,
which is the worst of both: the work was done and the record does not exist.

⚠️ **AND A DEPLOY CROSS-REFERENCES ITS RANGE AGAINST EVERY HELD DECLARATION,
BEFORE THE DECLARATION IS COMMITTED — `DEPLOYMENT_RUNBOOK.md` §2.5.** A held
declaration whose runtime files appear in the deploy range **BLOCKS the deploy**
until it is judged jointly or explicitly deferred **by name in the deploying
declaration**. ⚠️ **THE HAZARD IS CALLED *OVERTAKEN, NOT OVERRIDDEN*:** nobody
bypasses the hold — the hold is bound to a CHANGE, the deploy ships a TREE, and
both parties behave correctly while a clinical fix reaches production unjudged.
Reference case: F12-e, recovered retrospectively at
`docs/foundation/deploys/20260827-b439dcbb-F12E-RETROSPECTIVE.md`. **A
retrospective recovers the EVIDENCE, never the GATE.**

**A post-deploy check written afterwards is unfalsifiable.** Every number has a
story available to it, and a migration supplies a ready-made excuse for *any*
movement — *"the migration touched that table"*. Declaring first removes the
excuse: the comparison has one correct answer, fixed before the evidence existed.
Same discipline as *no evidence before the event*, pointed the other way.

### ⚠️ A DECLARATION IS BOUND TO A **CHANGE**. A DEPLOY SHIPS A **TREE**.

**Standing 2026-08-14, and neither session could have found it alone.**

> **When two changes reach `main` before either ships, the deploy discharges only
> the declaration whose author ran the comparison. The other is silently left
> unjudged unless somebody notices.**

**REFERENCE CASE.** R5 merged as `636e69a3`. The GI session then deployed
`2b527509` and judged it **16 of 16** — against its own declaration, which
covered an ICD-10 allowlist change. `636e69a3` is an ancestor, so **R5 went to
production inside that deploy.** Correct behaviour: they deployed `main`, which
is what `main` is for. But the payload was strictly larger than the
declaration's scope, and **not one of those sixteen rows could have detected an
R5 regression.** "16 of 16" was a true sentence doing misleading work.

**THE HABIT:** when more than one change is queued, either deploy them
separately so each declaration gates its own act, or write a declaration naming
the **FULL DIFF** being shipped. ⚠️ ***"I deployed `main`" is not the same claim
as "I judged what I deployed."***

**AND IF IT HAPPENS ANYWAY, THE UNJUDGED DECLARATION IS STILL WORTH RUNNING.**
R5's comparison was performed after the fact and every declared quantity
matched. The declaration's commit timestamp provably preceded the rows, so the
answer could not have been tuned to the outcome — that half of §2.5's product
survives. What is lost is the GATE, not the evidence, and saying which half you
have is the whole discipline.

**A difference that is not in the declaration is THE FINDING**, whatever its
explanation sounds like after the fact. And the clinical-count row is never
omitted — a deploy that moves a visit, patient or signature count has done
something nobody asked for, and the only way to know is to have written the
numbers down while they were still true.

## STANDING AUTHORITY — WHAT REACHES THE OWNER, AND WHAT DOES NOT

**Owner directive, 2026-08-22. This ENDS the copy-paste relay** in which every
step was narrated upward and every decision came back down. That pattern was
safe and it did not scale: the owner became the bus, and a bus is a bottleneck
whether or not it is well-informed.

> **THE LOOP builds, proves and merges under its own gates.**
> **SUPERVISED SESSIONS deploy and judge clinical-surface changes.**

**ONLY THESE FOUR REACH THE OWNER:**

| # | class | why it cannot be decided below |
|---|---|---|
| **a** | **a product decision with no ruled precedent** | it is a statement about what the product IS, and nobody else is entitled to make one |
| **b** | **an accepted-capability loss** | somebody is losing something that used to work; the trade is his to accept, and it must be written down where the next incident will find it |
| **c** | **an acceptance test needing his eyeball** | a document is right or wrong to the doctor reading it, and no gate substitutes for that |
| **d** | **money, keys, or deletion of data** | irreversible or costly, and each has bitten this programme already |

**EVERYTHING ELSE: build, prove, ship, record.**

⚠️ **THIS IS NOT A LOOSENING, AND THE PROOF BURDEN IS UNCHANGED.** §2.5 still
gates every deploy. The adversarial pass is still mandatory on the clinical
generation and note-editing paths — it found a clinical defect in the author's
own work on **three consecutive slices**, and each time the fix was wrong before
it was right. Citations, two-view checks, the merge wrapper and the standing
invariant checks all stand exactly as written.

**What changes is the ROUTING, not the rigour.** A session that would previously
have stopped to ask now decides, does the work to the same standard, and RECORDS
it — because the record is what makes an unasked question auditable later.

⚠️ **AND THE FOUR CLASSES ARE A FLOOR, NOT A CEILING.** If a call feels like it
belongs to the owner and does not fit a row, that feeling is data: surface it
with the reasoning attached and say why it did not fit. The failure this
replaces was a bottleneck; the failure it could create is a session deciding
something nobody would have let it decide. Neither is acceptable, and the second
is worse.

## AUTHORIZATION TRAVELS OWNER → SESSION DIRECTLY, AND NEVER THROUGH A PEER

**Standing 2026-08-14, and it is a rule about the CHANNEL, not about trust.** A
peer session can carry reasoning, evidence, measurements and warnings — all of
that is worth having and this programme runs better for it. What a peer cannot
carry is **authority**.

> **"The lead has ordered X", arriving sideways, is a CLAIM ABOUT
> AUTHORIZATION. It is verified like any other claim — by asking the owner —
> and it is never acted on because a peer asserted it.**

⚠️ **REFERENCE CASE, 2026-08-14, AND THE REFUSAL IS THE PART TO COPY.** One
session relayed an owner-ordered item to another: an ICD-10 allowlist append,
correctly reasoned, backed by a real production audit row, and genuinely the
right next item. The receiving session **declined to start it**, on the grounds
that its own owner had scoped its work to a different half and only he could
move that boundary. It surfaced the item to its owner with the reasoning
attached instead.

That was correct, and the relaying session (me) was wrong to phrase it as an
order.

⚠️ **AND THE ARGUMENT AGAINST THE CHANNEL WAS DRAWN FROM THAT SAME NIGHT.** The
brief that opened the session had **invented a peer that did not exist** and
**misattributed the work to rulings #103/#104 when it was #109**. Both were
caught by checking rather than by following. A channel that had already
produced two false statements — about who exists, and about which ruling
applies — is not a channel to accept work orders on, and the one message
asking for an exception came from inside it.

**The failure mode is not a wasted hour.** It is one session doing unreviewed
work on a clinical path while its owner believes it is doing something else,
and neither party knowing which of them is out of step. That state is
undetectable from either side until something lands wrong.

**The cost of the discipline is one message.** If the two owners are the same
person it resolves immediately and nothing was lost; if they are not, the
refusal has just located the seam.

**Corollary, for the relaying side:** state it as *your owner's reasoning,
offered to theirs*, with no authorization attached. Sending reasoning is
collaboration. Sending an order is a claim you are not in a position to make.

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

### ⚠️ AND AN ENTRY THAT **NAMES AN INSTRUMENT** VERIFIES THAT INSTRUMENT'S **GRANT**, IN THE SAME COMMIT

**Standing 2026-08-17. Two reference cases, same author, same week — which is
why it is mechanism and not advice.**

> **If a canon entry, a MASTER step or a ruling tells a session to RUN
> something, the landing commit checks that the thing is in
> `.claude/settings.json` — and adds it if not. A rule and its grant live in
> different files, land in different PRs, and NOTHING checks that the second
> followed the first.**

| # | the entry | the instrument | what the loop got |
|---|---|---|---|
| 1 | MASTER's queue header — *cite with `scripts/gh-runs.sh`* | `gh-runs.sh` | **refused**; worked around with `check-citation.sh`. Closed by #692 |
| 2 | canon *"A PROBE THAT MATCHES ITSELF"* — *the authority is `tmux has-session`* | `tmux has-session` | **refused**; pushed back toward `pgrep -f` |

⚠️ **THE SECOND IS THE ARGUMENT, BECAUSE THE RULE BACKFIRED.** That entry exists
*because* `pgrep -f` returned a false LIVE reading for three hours. An unattended
session obeying it hits a permission refusal and falls back to **exactly the
probe the rule forbids** — so the canon entry made the loop **less safe than no
entry at all.**

⚠️ **AND #692's OWN COMMIT MESSAGE HAD ALREADY STATED THIS LESSON** — *"a script
MASTER instructs the loop to run is not shipped until its GRANT ships with
it"* — written, merged, and violated in the next canon entry **by the same
author, days apart.** Naming a class is not enumerating it, and **writing a
lesson down is not obeying it.** That is precisely why this is a step in the
landing ritual rather than a thing to remember.

**The check is one line and it is cheap:**

    grep -c "<the instrument>" .claude/settings.json    # 0 = your entry is inert

⚠️ **AND IT APPLIES TO THIS ENTRY.** The commit landing it names
`scripts/push-with-cancellation.sh`, so it grants it in the same commit —
the rule's first application is to itself.

## LANDING INTO A LIVE LOOP — PREFER THE STOP FILE, AND OWN THE COST IF YOU DO NOT

### ⚠️ SUPERSEDED IN ITS PREMISE, 2026-08-30 — THE LOOP IS DECOMMISSIONED

**Owner directive 2026-08-30, recorded as ruling #161's sibling #160.** The
FOUNDATION loop **is not running and is not to be relit.** The product board is
executed directly by supervised sessions. Loop machinery — budgets, NO-PROGRESS
probes, F34, the queue-head ceremony — is **PARKED-INFRA**: left untouched, not
deleted.

> **Resumption is an OWNER decision, not a housekeeping one.** No session below
> the owner may relight it, and removing the halt switch is not a way to.

⚠️ **THIS AMENDMENT EXISTS BECAUSE THE DECISION HAD NO TRACKED RECORD, AND THAT
IS THE GENERALISABLE HALF.** For most of 2026-08-30 the decommission lived
**only** in `docs/foundation/STOP` — which is deliberately **untracked and
gitignored** (`06da801c`: *"the STOP file must never be tracked"*, because a
committed halt switch halts every clone) — and in a `~/.claude` paste cache at
mode 0600. Meanwhile **this file still asserted the opposite**, in the very next
paragraph, and `MASTER.md` said *"You ARE the unattended session"*. **A session
opening on the tracked canon would have relit a loop the owner had stood down,
and one `shred` of `~/.claude` would have erased the only surviving record of
the decision.**

> **A HALT SWITCH AND A DECISION ARE DIFFERENT ARTIFACTS ANSWERING DIFFERENT
> QUESTIONS** — *is the loop halted here and now* versus *was the loop stood
> down, by whom, and when*. The first is local by design and stays untracked.
> The second is canon and belongs in git. Conflating them is how a directive
> ends up depending on one machine's home directory.

**The paragraph below is KEPT, superseded, because the mid-cycle-landing
discipline it records still applies the moment any long-running unattended
actor exists again — and because its reference case is evidence.**

**Standing 2026-08-12, premise superseded 2026-08-30.** The FOUNDATION loop runs
unattended and continuously, so there is no idle window to wait for. A supervised session landing an owner
ruling therefore has two honest options, and the preferred one is cheap.

> **PREFER: `touch docs/foundation/STOP` → land at the batch boundary →
> `rm docs/foundation/STOP` and relight.** It costs one session's latency.

**Mid-cycle landing stays legal — and it carries the conflict it causes.**

⚠️ **REFERENCE CASE, 2026-08-12, and the cost fell on somebody else's work.** A
supervised session merged an owner-ruling PR while loop session 03 was mid-item.
Session 03's citation branch had forked before that merge and both had appended
to the end of `RELAY.md`, so the loop hit a conflict, resolved it correctly as a
union, and paid for a fresh `e2e`. **Nothing was lost and the resolution was
right** — which is exactly why the habit has to be written down rather than
rediscovered: a cost that lands on another actor and comes out fine is the kind
nobody corrects.

Two things that make either choice survivable:

1. **`RELAY.md` and `RULINGS.md` conflicts resolve as UNIONS** — see that
   section. Both sides describe things that actually happened. ⚠️ **Verify the
   union by `git diff --numstat` showing 0 REMOVED**, not by reading the merged
   file: a section that survived and a section that was re-added look identical,
   and only the removal count distinguishes a union from a silent overwrite.
2. **The STOP file halts the whole RUN, not one session.** A relight is
   `tmux new -d -s foundation 'bash scripts/foundation-loop.sh'` and the session
   budget starts over — say so in the log, or the next reader counts a budget
   that has already reset.

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

### ⚠️ AND ITS SIBLING: A MUTATION PROOF ASSERTS ITS **OWN** APPLICATION

**Standing 2026-08-14.** The rule above is about an edit you MEANT to keep. This
is the same defect in the edit you mean to THROW AWAY — and it is more
dangerous, because the whole point of that edit is to produce a test result you
will then believe.

> **An unapplied mutation yields a green that proves nothing — and it is
> indistinguishable from a guard that works.**

⚠️ **REFERENCE CASE — F3's proof, and I nearly recorded it as evidence.** The
mutation was meant to restore a plain `prisma.update` in place of the additive
review-state writer, to show the new guard would catch the shape that had
shipped. The anchor did not match, the script's assertion threw, **the file was
never touched** — and the suite then ran against UNMUTATED code and printed
`7 passed`. Read quickly, that is a guard confirming the fix. It is a guard
confirming nothing at all, on a proof that never happened.

Note what did work: the script's own `assert` fired, exactly as the entry above
requires. What was missing was the next step — **reading that failure as
invalidating the run that followed it.** The traceback and the green scrolled
past in the same output.

**The shape that prevents it, and it is one line:**

    open(p,'w').write(mutated)
    print('  mutation applied:', MARKER in open(p).read())   # ← before believing anything

Then re-run, and treat a `False` there as terminating the proof.

**Two corollaries, both earned the same night:**

- **MUTATE TOWARD THE REAL SHAPE.** A second F3-adjacent mutation *did* apply
  and still proved nothing, because it planted a marker as a COMMENT and the
  guard correctly strips comments before matching. A mutation aimed at the wrong
  form produces a green as empty as one that never landed.
- **A PROOF'S OUTPUT IS READ AS A WHOLE.** "Assertion error" followed by
  "N passed" is not a pass; it is a proof that aborted and a suite that ran
  anyway. If a mutation step can fail without stopping the run, it will
  eventually.

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

⚠️ **SECOND OCCURRENCE, 2026-08-21 — A COMMIT MESSAGE, AND IT RAN.** A `-m`
message containing `` `laterality` `` in backticks was passed as a quoted
argument. The shell evaluated it: **`laterality: command not found`**, and the
word was **deleted from the committed message**, which then read *"names a ␣
attribute"*. Harmless ONLY because that word is not a command — the same luck
that saved the `deploy-staging.sh` mention above, which was one file-mode bit
from executing.

**Two costs, and the second is the quiet one:** a substitution ran, and **the
artifact was silently corrupted**. Nothing errors when the shell eats a word
out of prose; the commit succeeds and the record is simply wrong. Amended via
stdin.

⚠️ **AND IT WAS WRITTEN BY A SESSION THAT HAD USED `-F` CORRECTLY ALL DAY.**
The rule does not fail when you disagree with it; it fails on the one message
you dashed off. That is exactly why it is mechanical.

**The rule is mechanical, so obey it mechanically:** write the body to a file,
pass the path. `gh pr create --body-file`, `gh pr comment --body-file`,
`gh pr edit --body-file`, `git commit -F`. If a heredoc is unavoidable, quote
the delimiter (`<<'MSG'`) so the shell expands nothing.

## Multi-session programs have relay ledgers — READ THEM FIRST

A relay ledger is the contract between sessions. It says what is built, what is
next, and what proof exists. **Nothing in this file used to point at one, which
is how a session can open, do good work, and duplicate or contradict a ruling
made three sessions ago.**

| Program | SPEC (what to build) | RELAY (what is built, what is next) |
|---|---|---|
| **Rounds** — the shipped skin | `docs/rounds/SPEC.md` | `docs/rounds/RELAY.md` |
| **Foundation** — teams → billing → admin | `docs/foundation/SPEC.md` | `docs/foundation/RELAY.md` |

⚠️ **AND BEFORE DECIDING ANYTHING RULING-SHAPED, GREP THE RULINGS — AND SINCE
2026-08-26 THAT IS TWO PATHS, NOT ONE:**

    grep -n '<what you want>' docs/foundation/RULINGS.md docs/foundation/rulings/*.md

**The head answers *which ruling and what status*; the archive answers *why*.**
The 2026-08-26 split moved every ruling BODY into `docs/foundation/rulings/`,
so a grep of the head alone finds the row and not the reasoning — and it
**returns zero rather than saying it looked in the wrong place.** Measured:
`grep -c laterality` scores **0** against the head and **3** across head +
archives — and ruling #127 is the one that forbids the model asserting it.

⚠️ **The example is deliberately NOT `#96(b)`, which this rule cited first.**
`RULINGS.md`'s own banner now explains the two-path route and names `#96(b)`
while doing so, so a head-only grep for it scores **1** — off the banner's
prose, not off a ruling. *A probe whose pattern appears in the searcher cannot
return false*, and an example that quietly stopped demonstrating its own point
is worse than no example.

`RULINGS.md` is a one-line index of every war-room
decision — date, number, STATUS, verdict, pointer — and it exists because a session
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


## CANON INDEX — every archived entry, one row each

**116 entries live in full at `docs/canon/`.**
Each row is a **POINTER, never the authority** — the archived body governs, and
it is verbatim. A row exists so that a grep for an entry's title still lands
here and tells you where the body went; the tell is that entry's OWN words.
Rows marked `↳` are subsections filed inside their parent's archive file.

### STATE & PARKED PROGRAMMES

- **Template Twin — the parked steady state** — PARKED 2026-07-28; 17 of 24 load-bearing claims were corrected under challenge, so treat any remembered Twin claim as suspect. The flag stays ON and is load-bearing; the wall is 80 of 80, never 79. → `docs/canon/01-template-twin-the-parked-steady-state.md`
- **Rollback constraints — known, accepted, do not "fix"** — A flag rollback is not always a clean inverse. Where it costs a capability the cost is recorded here, so nobody rediscovers it mid-incident and starts building. → `docs/canon/02-rollback-constraints-known-accepted-do-not-fix.md`
  - ↳ **`NEXT_PUBLIC_REVIEW_DOC_VIEW=false` → E/M is confirm-only, no override** — `REVIEW_DOC_VIEW=false` → E/M is confirm-only, no override. ACCEPTED. The gate does not weaken; prefer the image rollback `:pre-emrehome-20260728`. → `docs/canon/02-rollback-constraints-known-accepted-do-not-fix.md`
  - ↳ A PRE-DEPLOY SIGNED VISIT SERVES **STYLED** FOREVER — accepted 2026-08-21 — A visit signed before 2026-08-21 serves STYLED forever — accepted, no re-attestation path. "A null identity is DECLINED, never inferred." If a doctor sees the generic layout there, that is this entry, not a bug. → `docs/canon/02-rollback-constraints-known-accepted-do-not-fix.md`

### PROCESS, AUTHORITY & THE LOOP

- **⚠️ AND APPLY A NEW ENTRY TO ITS OWN LANDING** — "An entry you cannot apply to the commit that lands it is an entry nobody will apply later." Run a new rule once, immediately, on your own work. → `docs/canon/20-and-apply-a-new-entry-to-its-own-landing.md`
  - ↳ **4 · A RATIFIED CHANGE OF SCOPE LANDS BEFORE THE BUILD FINISHES, NOT AFTER** — "If a decision changes what 'done' means, it is not delivered until it is on `main`." `RELAY.md` is the builder's input; a transcript is not. → `docs/canon/20-and-apply-a-new-entry-to-its-own-landing.md`
  - ↳ **⚠️ AND THE SAME SHAPE IN A KILL SWITCH: IT HALTED A LOOP THAT WAS WORKING** — "A progress signal must be read where progress LANDS." Piping a command into a hasher discards its exit code and turns a FAILURE into a stable, plausible VALUE. → `docs/canon/28-a-gate-s-watched-set-is-diffed-against-the-spec-s-named-se.md`
- **A SPEC CAN BE FALSIFIED BY THE VERY RULING THAT WROTE IT** — "An order's QUANTITIES are a snapshot; its INSTRUCTIONS are the authority." #153 said *107→108, three labels*; its own required refusal audit made it **107→109, four**. ⚠️ The failure mode is OBEDIENCE — matching the measurement to the order produces a false declaration. → `docs/canon/66-a-spec-can-be-falsified-by-its-own-ruling.md`
- **THE LOOP DECLINED ITS SUPERVISOR'S FIX WITH BETTER REASONING, AND CI ENFORCED IT** — Supervision runs BOTH ways — the loop declined its supervisor's fix with better reasoning and CI enforced it. "I FILED IT" IS NOT "IT IS STILL OPEN." → `docs/canon/29-the-loop-declined-its-supervisor-s-fix-with-better-reasoni.md`
- **A FIX IS PRICED BY THE ASSET BEHIND THE SYMPTOM, NOT BY THE SYMPTOM'S VOLUME** — "Ask 'what is this a symptom OF?' before 'how annoying is this?'" A 🟢 "Caddy ACME noise" row was a certificate on the only path in — 65 days later, 6h15m down. → `docs/canon/40-a-fix-is-priced-by-the-asset-behind-the-symptom-not-by-the.md`
- **THREE ACTORS, ONE DIAGNOSIS — THE STANDING AUTHORITY'S THIRD-ACTOR PROOF** — "An authority boundary is only proven by the case where stopping is expensive." The loop classified an exhausted Actions budget as class (d) — money — and stayed dark four hours rather than spend. → `docs/canon/58-an-error-message-names-a-cause-not-the-cause.md`
- **⚠️ THIRD INSTANCE, 2026-08-23 — AND IT CAME FROM A `cd` IN AN EARLIER COMMAND** — "Before a deploy, resolve the shared tree BY ABSOLUTE PATH" — `git -C /opt/meddoc-pro rev-parse HEAD`. A relative check inherits whatever `cd` ran last. → `docs/canon/41-third-instance-2026-08-23-and-it-came-from-a-cd-in-an-earl.md`
- ⚠️ AND THE DISCRIMINATOR IS **DARK vs LIVE**, NOT THE SIZE OF THE FIX — The discriminator is DARK vs LIVE, not the size of the fix. Loop live → the tree is theirs; ask or wait. Loop dark → clearing an obstruction is maintenance. → `docs/canon/42-and-the-discriminator-is-dark-vs-live-not-the-size-of-the.md`
  - ↳ **⚠️ AND THE SECOND REFERENCE CASE IS THE LIVE ONE — ROUTINE SYNCING COUNTS** — `git merge --ff-only` on the shared tree is an act on a deploy surface, not housekeeping. The test is "is anyone standing there?", not "is this a change?" → `docs/canon/42-and-the-discriminator-is-dark-vs-live-not-the-size-of-the.md`
- A WORKTREE IS ISOLATED IN **FILES** AND SHARED IN **REFS** — "A worktree is isolated in FILES and shared in REFS." `git checkout` / `reset --hard` inside one moves the branch ref for every worktree sharing the repo. → `docs/canon/51-a-worktree-is-isolated-in-files-and-shared-in-refs.md`
  - ↳ **THE SAFE EXIT, AND THE REPAIR** — The safe exit is `git checkout --detach` before deleting a branch; establish what is TRUE before choosing a repair, and never reach for `git clean`. → `docs/canon/51-a-worktree-is-isolated-in-files-and-shared-in-refs.md`
- **A BLOCKING ROW NAMES THE ARTIFACT THAT WOULD DISCHARGE IT — AND THE POINTER RUNS IN THE READER'S DIRECTION** — "A LINK IN THE WRONG DIRECTION IS NOT A LINK." A blocking row NAMES the artifact that would discharge it, and the discharging artifact edits the row in the same commit. → `docs/canon/56-a-blocking-row-names-the-artifact-that-would-discharge-it.md`
- A TREE-RELATIVE INSTRUMENT ANSWERS ABOUT **ITS OWN** TREE, AND THE LOOP LIVES IN WORKTREES — A worktree has no `node_modules`, so `@meddoc/*` resolves up to the SHARED checkout, and tree-relative scripts answer about their own tree. → `docs/canon/57-a-tree-relative-instrument-answers-about-its-own-tree-and.md`
  - ↳ **THE PRACTICE** — `pwd` before you believe a number; run standing production checks from `/opt/meddoc-pro`; a `packages/*` change cannot be proven from a worktree. → `docs/canon/57-a-tree-relative-instrument-answers-about-its-own-tree-and.md`

### CI, PUSHES, MERGES & LANDING

- **GATE ON THE OBJECT THE GATE READS** — "`gh run list` reports the WORKFLOW RUN. Branch protection reads the CHECK RUN." Measure what the ENFORCER reads: `/commits/<sha>/check-runs`. → `docs/canon/11-gate-on-the-object-the-gate-reads.md`
- **WORK PRODUCED WHILE A CITATION RUNS IS STAGED, NEVER PUSHED INTO IT** — "Once a branch is pushed and its runs are in flight, that branch is CLOSED to this session." Stage further work; land it as its own PR. → `docs/canon/19-work-produced-while-a-citation-runs-is-staged-never-pushed.md`
- ⚠️ AND THE GENERAL FORM: AN IDENTIFIER IS QUERIED IN ITS **FULL** FORM, EVERYWHERE — "An ABBREVIATED identifier can return 'no matches' instead of 'ambiguous', with exit 0." Abbreviation is a display convenience, never a query key. → `docs/canon/37-and-the-general-form-an-identifier-is-queried-in-its-full.md`
  - ↳ **⚠️ FRESH INSTANCE, 2026-08-27 — I PADDED AN ABBREVIATION INTO A 40-CHARACTER STRING** — A fabricated sha passes every length check, exits a wait loop on a FALSE zero, and gets its emptiness blamed on a documented instrument defect. **Check your own input before you check the precedent.** → `docs/canon/37-and-the-general-form-an-identifier-is-queried-in-its-full.md`
  - ↳ ⚠️ AND THE THIRD: **FULL-LOOKING IS NOT FULL** — "FULL-LOOKING IS NOT FULL. A 40-character hex string is not a commit." Read it with `git rev-parse`; never pad or remember one. `gh-runs.sh` fails 2 = CANNOT TELL. → `docs/canon/37-and-the-general-form-an-identifier-is-queried-in-its-full.md`
- **AN EXTERNAL REACH IN THE BUILD IS REMOVED, NOT RETRIED** — An external reach in the build is REMOVED, not retried. `next/font/google` masks as a turbopack module-not-found in `layout.tsx` — it is the network, not your code. → `docs/canon/39-an-external-reach-in-the-build-is-removed-not-retried.md`
- **GREEN MUST NOT OUTRUN TRUTH** — "A fix that would turn a PR green while its siblings' promises stay false is WITHHELD." Ask what the green will MEAN once it lands; if you can name anything false, stage it and draft the PR. → `docs/canon/59-green-must-not-outrun-truth.md`
- **⚠️ AND THE SHELL IS NOT THE ONLY READER — A NEGATED MENTION STILL CLOSES THE ISSUE** — GitHub's linked-issue parser has no concept of negation: "it does not fix #603" closes it. Grep the body file for close/fix/resolve + `#N` before `gh pr create`. → `docs/canon/48-and-the-shell-is-not-the-only-reader-a-negated-mention-sti.md`

### EVIDENCE, CENSUSES & MEASUREMENT

- **AN UNFALSIFIABLE OBSERVATION IS NOT EVIDENCE, WHOEVER MADE IT** — "Ask what the observation would have looked like if it were false — then check the evidence could show it." The cost is direction, not effort. → `docs/canon/06-an-unfalsifiable-observation-is-not-evidence-whoever-made.md`
  - ↳ **⚠️ THE DOUBLE TAP — TWO INVARIANT CENSUSES, ONE SLICE, THE SECOND AFTER BEING CORRECTED FOR THE FIRST** — "STATE WHAT RESULT WOULD HAVE REFUTED THE CLAIM. If none could, it is a COUNT, not evidence." The tell is grammatical: a census counts a QUANTITY, the claim is about a KIND. → `docs/canon/06-an-unfalsifiable-observation-is-not-evidence-whoever-made.md`
- **⚠️ AND TWO MECHANISMS FOR ONE SYMPTOM, BOTH WRONG, IN ONE NIGHT** — "Read to form a hypothesis; RUN something to name a mechanism." A wrong mechanism in a source comment outlives the session that wrote it. → `docs/canon/07-and-two-mechanisms-for-one-symptom-both-wrong-in-one-night.md`
- **AN ERROR MESSAGE NAMES *A* CAUSE, NOT *THE* CAUSE** — "A vendor's error string is a HYPOTHESIS with authority attached." *"Artifact storage quota"* was a BUDGET throttle; 2.85 GB was freed and the symptom did not move. **A fix that provably lands and changes nothing is evidence about the DIAGNOSIS.** → `docs/canon/58-an-error-message-names-a-cause-not-the-cause.md`
  - ↳ **AND DO NOT LET A FIX TAKE CREDIT IT DID NOT EARN** — "When a fix ships alongside the real cure, say which one worked." Correct hygiene listed beside "and then it worked" implies a causal chain that did not exist. → `docs/canon/58-an-error-message-names-a-cause-not-the-cause.md`
- **AN ASSERTED NEGATIVE HALF NEEDS ITS OWN MEASUREMENT** — "A row that names a positive and then closes with 'and nothing else' is TWO assertions." The negative half is the one nobody checks. → `docs/canon/12-an-asserted-negative-half-needs-its-own-measurement.md`
  - ↳ **⚠️ AND THE MEASUREMENT THAT SEPARATES THEM IS THE IMAGE ID, NOT THE START TIME** — "TAGGING IS NOT CHANGING, AND ONLY AN ID COMPARISON TELLS THEM APART." A start-time check cannot see whether the image id moved. → `docs/canon/12-an-asserted-negative-half-needs-its-own-measurement.md`
- **ARITHMETIC THAT DOES NOT RECONCILE IS A FINDING** — "Make every enumeration reconcile against its own total." A partition that does not add up has an unnamed bucket, and that is where the finding lives. → `docs/canon/13-arithmetic-that-does-not-reconcile-is-a-finding.md`
  - ↳ **⚠️ AND THE PASS THAT FOUND IT ALSO CAUGHT A CITATION OF THIS FILE OVER-REACHING** — "CITING CANON IS A CLAIM, AND A CLAIM NEEDS EVIDENCE." Check the entry says what your argument needs, on the axis the argument is using. → `docs/canon/14-err-toward-the-edge-the-edge-has-a-fence.md`
- **A CENSUS IS ONLY AS AUTHORITATIVE AS ITS PREDICATE'S FIDELITY TO THE SHIPPED FUNCTION** — "DRIVE THE REAL FUNCTION, OR STATE THE APPROXIMATION AND HOW IT DIFFERS." A predicate that merely resembles the shipped one gave 670 for 441, and 25 for 9. → `docs/canon/15-a-census-is-only-as-authoritative-as-its-predicate-s-fidel.md`
- **A MEASUREMENT OF TODAY'S CORPUS IS A FACT ABOUT THE POPULATION, NOT A PROPERTY OF THE CODE** — A census answers "is this happening?", never "can this happen?". If it is a population fact, state what RE-ARMS the path in the same sentence. → `docs/canon/16-a-measurement-of-today-s-corpus-is-a-fact-about-the-popula.md`
- **THE MOST DANGEROUS WRONG NUMBER IS THE ONE THE PREDICTION EXPECTS** — "A wrong measurement that equals what you predicted cannot be caught by reconciliation — there is nothing left to disagree with." A stale tree read `1 unapplied` where the truth was **2**, and `1` was exactly what the standing hold predicted. **A confirmed prediction is not a control.** → `docs/canon/65-the-most-dangerous-wrong-number-is-the-one-expected.md`
- **A REFUSAL CAUSED BY MY OWN SUBSTITUTION IS EVIDENCE ABOUT MY SUBSTITUTION** — "When you supply an input to reach a code path, every result downstream of that input is a fact about YOUR INPUT until you re-establish it on evidence the substitution cannot touch." A blanket `exam.vascular` UPDATE forced `measurementRows` to zero, and the engine's correct refusal was nearly filed as a finding about a customer's document. ⚠️ **Declaring an input is not controlling for it** — and the refusal costume looks like rigour. → `docs/canon/71-a-refusal-caused-by-my-own-substitution.md`
- **RECORD A HYPOTHESIS *BECAUSE* IT WAS REFUTED** — "A refuted hypothesis, recorded with its measurement, converts a question somebody will re-ask into one somebody can look up." Its value does not depend on being right. → `docs/canon/17-record-a-hypothesis-because-it-was-refuted.md`
- **CONFIRM A FIGURE YOU WILL BUILD ON BY A SECOND, INDEPENDENT ROUTE** — "Re-derive by a route that does not share the first one's failure mode, then check the two RECONCILE — not merely that they agree." → `docs/canon/18-confirm-a-figure-you-will-build-on-by-a-second-independent.md`
  - ↳ **⚠️ THE THREE-LAYER ECHO — one lesson, three altitudes, one arc** — One lesson at three altitudes — editor, predicate, measurement: ask the thing that knows; do not classify what resembles. → `docs/canon/25-counting-tokens-instead-of-classifying-rows-and-the-detect.md`
  - ↳ **⚠️ AND THE AUTHORITY ANSWERS SOME OF YOUR QUESTIONS, NOT ALL OF THEM** — "ENUMERATE WHICH QUESTIONS THE AUTHORITY CAN ANSWER BEFORE ROUTING ANY QUESTION TO IT." It answers anyway — with a resemblance wearing an authority's credibility. → `docs/canon/25-counting-tokens-instead-of-classifying-rows-and-the-detect.md`
- **A BYTE-IDENTITY ROW NEEDS A BEFORE-HASH** — "A CONTENT claim needs a CONTENT baseline." A row required *any stored note's text — byte-identical* while only a row COUNT had been captured. Downgrade honestly to structural incapability, **so labeled** — never let a structural argument wear a measurement's clothes. → `docs/canon/69-a-byte-identity-row-needs-a-before-hash.md`
- **A CENSUS PROVES CONTENT, NOT REACHABILITY** — "A census answers *was anything LOST?*. It cannot answer *can anything still be FOUND?*" Every ledger split ships WITH its reader sweep; watched set = **head + archives**. → `docs/canon/60-a-census-proves-content-not-reachability.md`
- **EVIDENCE IS ONLY EVIDENCE ON THE TREE IT DESCRIBES** — Guard the state transition — rebase/merge exit code, clean `git status` — BEFORE any number counts; withdraw explicitly anything printed from a broken tree. → `docs/canon/36-evidence-is-only-evidence-on-the-tree-it-describes.md`
  - ↳ **A count inherited from another report, then incremented by assumption** — "A count carried forward from another session's report and then incremented by assumption is a fabricated number, however small the increment." → `docs/canon/36-evidence-is-only-evidence-on-the-tree-it-describes.md`

### INSTRUMENTS, PROBES & ZEROS

  - ↳ **⚠️ AND A DOCUMENTED-UNRELIABLE INSTRUMENT IS NOT A PERMANENTLY-WRONG ONE** — "A precedent about an instrument is a prior, not a verdict." Reaching for the precedent INSTEAD of the data is how a true report gets discarded — and it feels like rigour. → `docs/canon/11-gate-on-the-object-the-gate-reads.md`
  - ↳ **⚠️ THE COROLLARIES, EARNED IN THE SAME SESSION AS THE ENTRY ABOVE** — Four corollaries earned AFTER that entry was merged — the argument for them being mechanical rather than remembered. → `docs/canon/20-and-apply-a-new-entry-to-its-own-landing.md`
  - ↳ **1 · EVERY ZERO YOU PRODUCE IS YOUR INSTRUMENT UNTIL PROVEN OTHERWISE** — "A zero is a measurement only when it arrives with a control or a reconciliation." SELF-AUTHORED PROSE IS THE HIGHEST-RISK GREP TARGET. → `docs/canon/20-and-apply-a-new-entry-to-its-own-landing.md`
  - ↳ **2 · CHECK QUERIES PARTITION `status` FIRST, `conclusion` SECOND** — `conclusion != success` counts a RUNNING check as a failure. Partition `status` first: running / failed / passed, reconciling to the total. → `docs/canon/20-and-apply-a-new-entry-to-its-own-landing.md`
  - ↳ **3 · A WATCHER MATCHING ON CONTENT SEES ITS OWN AUTHOR** — A watcher matching on content fires on your OWN activity. Read every event for who filed it. → `docs/canon/20-and-apply-a-new-entry-to-its-own-landing.md`
- **A TASK'S EXIT CODE DESCRIBES ITS LAST COMMAND, NOT THE WORK** — "VERIFY THE WORK, NOT THE WRAPPER." Read the outcome from the system that owns it, and never re-run an irreversible act on a wrapper's say-so. → `docs/canon/22-a-task-s-exit-code-describes-its-last-command-not-the-work.md`
- **COUNTING TOKENS INSTEAD OF CLASSIFYING ROWS — AND THE DETECTOR THAT CAUGHT ALL FIVE** — Five instrument defects, one shape: counting TOKENS instead of classifying ROWS, each caught by an incoherent value left loud. Never normalise an impossible value. → `docs/canon/25-counting-tokens-instead-of-classifying-rows-and-the-detect.md`
- **A DETECTOR CAN BE BLIND TO THE THING IT MOST EXISTS TO WATCH** — "A detector that silently covers half of what its name implies is indistinguishable from one that works. The tell is the count that never moves." → `docs/canon/31-a-detector-can-be-blind-to-the-thing-it-most-exists-to-wat.md`
  - ↳ **⚠️ TWO MORE OF THE SAME FAMILY, FROM ONE RECON — F8, 2026-08-16** — "A grep that resolves a SYMBOL has not found its DATA" (barrel re-export → false zero); ask what SHAPE the data is before asking how much of it there is. → `docs/canon/31-a-detector-can-be-blind-to-the-thing-it-most-exists-to-wat.md`
  - ↳ ⚠️ TWO ZEROES WITH OPPOSITE MEANINGS IS **ONE BROKEN INSTRUMENT**, NOT TWO FINDINGS — "Zeroes for things that MUST be absent AND zeroes for things that MUST be present — stop reading the results and check the instrument. The contradiction is the finding." → `docs/canon/31-a-detector-can-be-blind-to-the-thing-it-most-exists-to-wat.md`
  - ↳ **⚠️ AND THE FOURTH MEMBER: A PROBE THAT MATCHES ITSELF** — "A search whose PATTERN appears in the SEARCHER cannot return false." `pgrep -f` called a dark loop LIVE for three hours. Ask the OWNER of the state — `tmux has-session`. → `docs/canon/31-a-detector-can-be-blind-to-the-thing-it-most-exists-to-wat.md`
  - ↳ ⚠️ AND A FIFTH: **ONE SUCCESS IS NOT RECOVERY, AS ONE ZERO IS NOT ABSENCE** — "A single successful probe during an outage is a BLIP, not a recovery." Require N consecutive successes and print when a streak BREAKS. → `docs/canon/31-a-detector-can-be-blind-to-the-thing-it-most-exists-to-wat.md`
  - ↳ **⚠️ A CONTROL AIMED WHERE THE ANSWER IS PREDETERMINED IS NOT A CONTROL** — "STATE WHAT THE CORRECT MACHINERY WOULD DO AT THAT TARGET." If you can predict the control's result from the target alone, it measures the target, not the instrument. → `docs/canon/31-a-detector-can-be-blind-to-the-thing-it-most-exists-to-wat.md`
  - ↳ ⚠️ AND A SIXTH — **TWO WEAK DEFECTS COMPOSED INTO A CONFIDENT FALSE GREEN** — Two weak defects composed into a confident false green — a short sha returning `[]`, plus `OK == T`, vacuous at zero. A success check needs a FLOOR, not a ratio. → `docs/canon/31-a-detector-can-be-blind-to-the-thing-it-most-exists-to-wat.md`
  - ↳ **⚠️ AND A THIRD MEMBER: A TREE THAT CANNOT RESOLVE ITS OWN IMPORTS** — "A number printed from a tree that cannot resolve its own imports is not a measurement." Report the CONTROLLED DELTA against a clean checkout. → `docs/canon/31-a-detector-can-be-blind-to-the-thing-it-most-exists-to-wat.md`
- **A DOCUMENTED DEFECT IS THE MOST CONVENIENT SUSPECT** — "When an instrument disagrees with you, CHECK YOUR OWN INPUT BEFORE YOU CHECK THE PRECEDENT." The mirror of *a documented-unreliable instrument is not a permanently-wrong one*: one reflex discards true reports, this one MANUFACTURES false ones. Carries the DENOMINATOR rule. → `docs/canon/61-a-documented-defect-is-the-most-convenient-suspect.md`
  - ↳ **⚠️ TWO ACTORS, SAME DEFECT, SAME DAY — WHICH MAKES IT STRUCTURAL, NOT PERSONAL** — Four fabricated-identifier instances across two independent actors in one day. **A property of the WORK, not the worker** — so the cure must be MECHANICAL: an identifier reaches a command from `rev-parse` in the same breath that uses it. → `docs/canon/61-a-documented-defect-is-the-most-convenient-suspect.md`
- **A DENY MATCHES THE AGENT, NOT THE SCRIPT** — "'X is in the deny list' is a fact about a FILE; 'X cannot happen' is a claim about BEHAVIOUR." A row said `retire-branch.sh`'s remote leg *can never succeed*; the deny entry is real, the script works, and the gap between them was one command nobody ran. **Before recording that something is denied, RUN it** — a refusal is loud, instant and free. → `docs/canon/64-a-deny-matches-the-agent-not-the-script.md`
- **A SCANNER'S `incomplete` IS NOT A PASS** — it is the set the tool ADMITS it could not judge, and the worst violations hid there: axe reported 5 contrast failures while the true worst, at **1.16:1**, sat in `incomplete`. An a11y claim on a clinical surface needs that bucket **resolved to zero or independently measured**, and reports BOTH numbers. → `docs/canon/67-a-scanner-s-incomplete-is-not-a-pass.md`
- **And a reassurance check needs a POSITIVE CONTROL like any other** — "A check run to prove nothing happened is the most likely to be believed and the least likely to be controlled." `find -newermt` said 0; `stat` disagreed. → `docs/canon/49-and-a-reassurance-check-needs-a-positive-control-like-any.md`

### GATES, GUARDS, SWEEPS & MUTATION PROOFS

- **A check whose TITLE is narrower than what it MEASURES** — Read a check's name as a claim, then confirm the code makes exactly that claim — no wider, no narrower. Mutate toward SUCCESS as well as failure. → `docs/canon/08-a-check-whose-title-is-narrower-than-what-it-measures.md`
- **A WELL-CHOSEN FIXTURE DISGUISES A WRONG UNIVERSE** — "A pipeline proof runs in the PRODUCTION UNIVERSE: production's FLAG SET and ROUTES." A fixture from the right domain is not a route. Count the production rows the proof covers. → `docs/canon/09-a-well-chosen-fixture-disguises-a-wrong-universe.md`
- **THREE FALSIFICATIONS OF ONE RULE, EACH A LAYER DEEPER, IS DATA ABOUT THE INSTRUMENT** — "When a deterministic heuristic is doing SEMANTICS, the next counterexample always exists; the fail-closed answer IS the rule." One rule formulated three times — print the value / print the quote / print it when the quote self-negates — each falsified by measurement, each fix correct, each moving the failure one layer down: entity → quote → clause. ⚠️ **The gate was green with the harm live at every layer.** ⚠️ **ESCALATE INSTEAD OF BUILDING LAYER FOUR** — ratified by name as the correct behaviour, not a failure to finish. And the fail-closed answer DELETES the machinery rather than gating it, or the next reader repairs it instead of questioning it. → `docs/canon/75-three-falsifications-is-data-about-the-instrument.md`
- **A SUBSTRING CHECK PROVES NOTHING WAS MANUFACTURED — IT CANNOT PROVE NOTHING WAS DESTROYED** — "When a rule says print the doctor's own words and compose nothing, a subset check is NECESSARY and HALF THE ANSWER." Four denied sentences rendered into a signed document with their negation stripped — `Not taking: warfarin, aspirin, or clopidogrel.` printed as an anticoagulant LIST — and every output was a strict SUFFIX of the doctor's own quote, so the composition assertion passed on all four. ⚠️ The tell: **your assertion constrains only ONE DIRECTION of the edit.** Any rule about faithfulness forbids REMOVING too. ⚠️ And the second property must not be drawn from the same list the code uses — that is [canon 31](docs/canon/31-a-detector-can-be-blind-to-the-thing-it-most-exists-to-wat.md)'s predetermined control, one layer inside the fix. → `docs/canon/74-a-substring-check-cannot-prove-nothing-was-destroyed.md`
- **A PER-BRANCH INVARIANT IS NOT A MERGE INVARIANT** — "Nothing a single branch can assert about itself catches a collision that exists only in the UNION." Three branches each added canon entries; two claimed 69 and two claimed 70. **Git merges all four cleanly** — different slugs, no conflict — and the numbering silently stops meaning anything. ⚠️ All four branches reconciled INDIVIDUALLY, so the one watching instrument reported green four times. The gate must live on `main`, where the union first exists. ⚠️ And measure the population first: the obvious "unique numbers" arm reds `main` on arrival. → `docs/canon/73-a-per-branch-invariant-is-not-a-merge-invariant.md`
- **A MUTATION PROOF THAT EXERCISES THE COMPLETE INVERSE HAS PROVED THE TIDY CASE** — "The failure that ships is a HALF-LANDED fix." Mutate to each PARTIAL application of your own fix; a present-but-empty fallback makes one invisible. → `docs/canon/10-a-mutation-proof-that-exercises-the-complete-inverse-has-p.md`
- **OVERLAPPING GUARDS MUST NOT LAUNDER AN UNPROVED ARM** — "Caught by a DIFFERENT guard than the one you were proving? The arm is still unproved — and the red run is the most convincing possible evidence that it works." APPLICATION IS NOT EXERCISE. Re-mutate to the minimal shape the arm can see; ask whether the failure message names YOUR arm. → `docs/canon/62-overlapping-guards-must-not-launder-an-unproved-arm.md`
- **FIX BY GROUND, NOT BY HIT** — "A fix covers the MECHANISM'S CLASS, not the nodes the measurement happened to exercise." `icd-empty` was fixed having failed in no scan, in either state, because it sits on the same wrong side of the same boundary. ⚠️ And the inverse binds too: the passing cards were left untouched. → `docs/canon/68-fix-by-ground-not-by-hit.md`
- **A CHECK'S REMEDIATION ADVICE IS WRITTEN FOR ITS COMMON STATE** — "In a HELD or STAGED state, following a check's printed advice can bypass the gate the state exists to protect." Establish WHY it is red first. → `docs/canon/21-a-check-s-remediation-advice-is-written-for-its-common-sta.md`
- A MUTATION-PROOF BACKUP CAPTURES THE STATE YOU WANT TO **RETURN TO** — "A PRE-CHANGE BACKUP TURNS 'RESTORE' INTO 'UNDO MY WORK'." Copy AFTER the change; assert the marker landed before believing a result; on restore assert BOTH marker-gone and change-survives. → `docs/canon/23-a-mutation-proof-backup-captures-the-state-you-want-to-ret.md`
- **A SHARED NOUN IS NOT A SHARED SURFACE** — "ENUMERATE READERS BY CALL SITE, NEVER BY VOCABULARY." A shared noun — "the model", "the export" — is a vocabulary inventory, not coverage. → `docs/canon/24-a-shared-noun-is-not-a-shared-surface.md`
- **A CAPABILITY IS UNREACHABLE UNTIL THE ACTOR THAT INVOKES IT IS TOLD** — A capability is unreachable until the actor that invokes it is TOLD — and a MODEL is wired by its PROMPT. A JSDoc constraint on a schema field never reaches the wire. → `docs/canon/26-a-capability-is-unreachable-until-the-actor-that-invokes-i.md`
  - ↳ **⚠️ AND THE ARM THAT NAMED THE INVARIANT WAS BLIND TO THE NEW FIELD** — "A guard's watched set does not grow when you add a field." A new carrier for an existing concept means widening the guards that name it, in the same commit. → `docs/canon/26-a-capability-is-unreachable-until-the-actor-that-invokes-i.md`
- **⚠️ WRITE THE UNTESTED CLAIM DOWN BEFORE THE PASS RUNS** — Before the adversarial pass, the author writes one sentence: "the claim I have NOT tested is ___." If it cannot be written, that is the finding. → `docs/canon/27-write-the-untested-claim-down-before-the-pass-runs.md`
- **A gate's WATCHED SET is diffed against the spec's NAMED set** — "Before any gate's zero is believed, diff what it WATCHES against what the acceptance criteria NAME." List both, in writing, before claiming the gate is met. → `docs/canon/28-a-gate-s-watched-set-is-diffed-against-the-spec-s-named-se.md`
- A SWEEP IS DEFEATED BY AN INCOMPLETE **TOKEN LIST** AT LEAST AS OFTEN AS BY A MISSING **FORM** — A sweep dies on an incomplete TOKEN LIST as often as a missing FORM. A composed identifier has no literal in source — enumerate tokens from the CONSUMERS. → `docs/canon/30-a-sweep-is-defeated-by-an-incomplete-token-list-at-least-a.md`
  - ↳ **⚠️ AND THE SAME SHAPE WHILE VERIFYING A DEPLOY — A `NOT FOUND` THAT WAS MY SEARCH** — Three of four tokens from ONE component resolved in the bundle and the fourth did not, reading like a partial deploy. The id was composed; the prefix was in both chunks. **A `NOT FOUND` measures your PATTERN before it is a fact about the artifact.** → `docs/canon/30-a-sweep-is-defeated-by-an-incomplete-token-list-at-least-a.md`
  - ↳ **THE DISCIPLINE, AND THE FIRST ITEM IS THE ONE USUALLY SKIPPED** — The full form list one sweep actually had to touch — test id, class family, ARIA name, element id, text, `data-*`, query-param value, enums, fixtures, project names. "A four-item checklist reads as complete and is not." → `docs/canon/30-a-sweep-is-defeated-by-an-incomplete-token-list-at-least-a.md`
  - ↳ **⚠️ FRESH SELF-APPLICATION, 2026-08-20 — I SEARCHED FOR THE FIX I IMAGINED** — "When checking whether something is DONE, search for the PROBLEM, not for your solution to it." A grep for your own fix tests your memory, not the file. → `docs/canon/30-a-sweep-is-defeated-by-an-incomplete-token-list-at-least-a.md`
- **THE LIST IS THE DRIVER, NOT THE CONTEXT** — "A LIST THAT IS PRODUCED AND NOT WORKED FROM IS A COMMENT." "The errors stopped appearing" describes your detectors, not completion. → `docs/canon/35-the-list-is-the-driver-not-the-context.md`
- **AN EXEMPTION'S REASON IS PROSE, AND PROSE DECAYS SILENTLY** — "A gate can keep an exemption PRESENT. It cannot keep it HONEST." Re-read the justification by hand whenever the code it describes is touched. → `docs/canon/38-an-exemption-s-reason-is-prose-and-prose-decays-silently.md`
  - ↳ **⚠️ SO WRITE THE EXEMPTION WITH ITS RETIREMENT CONDITION IN THE SAME SENTENCE** — Write the exemption WITH the condition that retires it, so checking is a LOOKUP not a judgement. Name a TESTABLE EVENT; "for now" never becomes false. → `docs/canon/38-an-exemption-s-reason-is-prose-and-prose-decays-silently.md`
- **"RESTORE FROM GIT" AND "RESTORE FROM BACKUP" ARE NOT THE SAME OPERATION** — "`git checkout -- <file>` on a dirty tree DELETES uncommitted work, silently." Back up every file the proof touches to scratch, and assert the copies exist first. → `docs/canon/45-restore-from-git-and-restore-from-backup-are-not-the-same.md`
- **⚠️ AND WHEN THE ARTIFACT IS GENERATED: THE GENERATOR MUST DELETE WHAT IT REPLACES** — A regeneration that PREPENDS and never deletes leaves a file holding every value you assert, syntactically dead. Assert a generated file's STRUCTURE, bound to code. → `docs/canon/46-and-when-the-artifact-is-generated-the-generator-must-dele.md`
- **⚠️ AND THE SAME SHAPE OUTSIDE `.replace()`: AN OPERATION THAT SUCCEEDS AND DOES NOT LAND** — `core.fileMode` is false here: `chmod +x` succeeds and the file still enters the index 100644. Set the bit in the INDEX; verify with `git ls-files -s`. → `docs/canon/47-and-the-same-shape-outside-replace-an-operation-that-succe.md`
- **The substring trap — fourth sighting, same family** — The substring trap: `'practice-scope' in source` matched "practice-scoped" in a comment. Prefer `toBe`; for is-it-present checks match the EXACT token. → `docs/canon/50-the-substring-trap-fourth-sighting-same-family.md`
- **PIN PROPERTIES, NOT SPELLINGS** — "A source-text gate that asserts an exact SPELLING can lock a defect in place." Three same-week specimens; the middle one **demanded the unscoped cross-tenant read** and reported green for it, while `gate-practice-scope`'s ratchet caught it in CI. ⚠️ The leaked count was **spoken to the doctor** in a refusal string — cross-tenant data in a UI string is the weight. The tell: *if somebody IMPROVED this code, would my gate fail?* → `docs/canon/72-pin-properties-not-spellings.md`

### WRITE PATHS, MIGRATIONS & CONSTRAINTS

- **A required column is a WRITE-PATH sweep, and the sweep is BY TABLE** — Sweep a NOT NULL column BY TABLE, not by API: the table name AND the ORM method; positive-control the pattern before believing a zero; a named subset is swept by its DEFINING PREDICATE, never by memory. → `docs/canon/05-a-required-column-is-a-write-path-sweep-and-the-sweep-is-b.md`
- AN OVER-PERMISSION FIX'S DECLARATION ASSERTS **ABSENCE** ROWS — An over-permission fix declares ABSENCE rows: "a presence-only declaration cannot detect over-admission." It passes just as happily on the broken version. → `docs/canon/32-an-over-permission-fix-s-declaration-asserts-absence-rows.md`
- **TEXT PRESENCE IS NOT MEMBERSHIP** — "`grep` answers a question about a FILE. Membership is a question about a DATA STRUCTURE." Assert THROUGH the structure, plus a non-vacuity row. → `docs/canon/33-text-presence-is-not-membership.md`
- SPLIT-FAMILY COVERAGE PINS **BOTH** DIRECTIONS — Adding the missing half of a pair pins BOTH directions — mutation-prove by deleting the side that was ALREADY there, the direction a new-side-only test is blind to. → `docs/canon/34-split-family-coverage-pins-both-directions.md`
- **A CONSTRAINT IS SWEPT BY ITS PREDICATE, NEVER BY THE ORM METHOD** — "Write the constraint's predicate down in words, then find every site that can make it false." Reactivation produces the forbidden state and no `create` sweep sees it. → `docs/canon/43-a-constraint-is-swept-by-its-predicate-never-by-the-orm-me.md`
- **A FIRE-AND-FORGET WRITER IS PROVED ONLY BY A TEST THAT READS IT BACK** — A fire-and-forget writer is proved only by a test that READS THE ROW BACK. An enum value is THREE edits and the third is a migration. → `docs/canon/44-a-fire-and-forget-writer-is-proved-only-by-a-test-that-rea.md`

### PRODUCT SURFACES, DELETIONS & ERROR DIRECTION

- A DELETION IS SCOPED BY WHAT THE COMPONENT **DOES**, NOT BY WHAT THE RULING **CALLS** IT — "Before deleting a named surface, enumerate everything the component actually renders. Anything the ruling does not name is a decision you are making, not one you were given." → `docs/canon/03-a-deletion-is-scoped-by-what-the-component-does-not-by-wha.md`
  - ↳ **⚠️ AND THE RESTORE HAD THE SAME DEFECT ONE FIELD DOWN, WHICH IS THE HALF WORTH REMEMBERING** — "An absent field is content the doctor did not see. A WRONG field says the opposite of the record being signed." Restoring a surface can introduce the second while fixing the first. → `docs/canon/03-a-deletion-is-scoped-by-what-the-component-does-not-by-wha.md`
  - ↳ **THE GUARD IS A BICONDITIONAL PLUS FIELD PARITY, AND PRESENCE IS NOT ENOUGH** — Presence is not parity: the guard stayed green through the action defect. State it as a biconditional PLUS field parity, and assert the card is actually mounted. → `docs/canon/03-a-deletion-is-scoped-by-what-the-component-does-not-by-wha.md`
  - ↳ **HONEST LIMITS, RECORDED SO THE GATE IS NOT READ WIDER THAN IT IS** — That gate's honest limits — one of three medication emitters, a mount leg defeated by a conditional render, a mirrored condition that is not byte-faithful. → `docs/canon/03-a-deletion-is-scoped-by-what-the-component-does-not-by-wha.md`
- **Shared components — diff the callers BEFORE you replace them** — "A shared component must accept every context its predecessors carried." Diff every call site first; put the behaviour ON the component, never on a hand-kept caller list. → `docs/canon/04-shared-components-diff-the-callers-before-you-replace-them.md`
- **A VIEW SWITCH THAT UNMOUNTS DESTROYS LOCAL STATE — AND THE GATE IT WAS HOLDING** — "The obvious two-view switch is a ternary, and a ternary UNMOUNTS." F8-S2: switching to Coding and back would have destroyed the in-session E/M confirm and silently re-blocked Sign — no error, no log line, nothing to click. HIDE, and hide **twice** (`hidden` + inline `display:none`), because `hidden` is a UA-stylesheet rule any author rule defeats silently. → `docs/canon/63-a-view-switch-that-unmounts-destroys-local-state.md`
  - ↳ **⚠️ AND THE ASSERTION IS A MOUNT COUNT — "STILL IN THE DOM" IS SATISFIED BY A REMOUNT** — The obvious presence check **passes on the exact defect it was written to catch**. When the property is IDENTITY OVER TIME rather than presence at a moment, count the transitions, not the occupants. → `docs/canon/63-a-view-switch-that-unmounts-destroys-local-state.md`
- **ERR TOWARD THE EDGE — THE EDGE HAS A FENCE** — "When an indexed clinical write can err, err toward the EDGE — the edge has a fence." Over-shoot fails closed to a visible blank; under-shoot silently reads the neighbour. → `docs/canon/14-err-toward-the-edge-the-edge-has-a-fence.md`

### HYGIENE, PHI & PURGES

- **AN EXONERATION IS A CLAIM TOO** — "Clearing your own deploy needs the same scoped instruments as indicting it." A glob swept unrelated migrations and returned **5** write verbs against my own deploy; scoped by NAME it was **0**, positive-controlled at 7. ⚠️ The exonerating direction is the dangerous one — **a clean result ends the enquiry.** → `docs/canon/70-an-exoneration-is-a-claim-too.md`
- **⚠️ A DESTRUCTION LIST IS A CLAIM** — "A destruction list is a CLAIM." Verify before executing — `git worktree list`, `gh pr list`, `git ls-files` — and afterwards assert what must SURVIVE, not only what is gone. → `docs/canon/52-a-destruction-list-is-a-claim.md`
  - ↳ **Session evidence trees are EXTRACT-THEN-SHRED, at session end** — Session evidence trees are EXTRACT-THEN-SHRED at session end: land the reports first, check admission for credentials by shape, READ what you are about to destroy. → `docs/canon/52-a-destruction-list-is-a-claim.md`
  - ↳ **A history purge does not clear the filesystem** — A history purge does not clear the filesystem — a directory snapshot has no `.git`, so a blob scan is blind to it. Unbounded depth, `-xdev`, and state the boundary. → `docs/canon/52-a-destruction-list-is-a-claim.md`
- **And check the data invariants that nothing else watches** — The standing READ-ONLY invariant checks (0/1/2) and what each green does NOT cover — the two E/M watchers' separate axes, `--qa` covering the DB and not the IMAGES, the composite-FK wall Prisma offers to delete as tidying. → `docs/canon/53-and-check-the-data-invariants-that-nothing-else-watches.md`
- **`refs/pull/*` is the namespace the rewrite cannot reach** — `refs/pull/*` is the namespace a rewrite cannot reach: `/merge` on an OPEN PR is recomputed from the poisoned base; `/head` on a closed PR is permanent. → `docs/canon/54-refs-pull-is-the-namespace-the-rewrite-cannot-reach.md`
- **A second purge, and what it cost — 2026-07-28** — The second purge cost ~200× the first for the same content, purely because it had sat longer. "The cost of a tracked clinical file is not fixed. It compounds." → `docs/canon/55-a-second-purge-and-what-it-cost-2026-07-28.md`
