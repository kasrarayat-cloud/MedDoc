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
- Repo root — `twin-*.docx`, `diag-*`, `visit-*.pdf|docx`.

Use `shred -u -n 3 -z`, not `rm`. Root-owned artifacts need the documented
root-via-docker path; a silent "Permission denied" from `shred` leaves the file
exactly where it was.

**Report paths, never contents.**

### And check the data invariants that nothing else watches

Scratch is not the only thing a session can leave behind. Some defects write a
COLUMN, and no sweep of the filesystem will find them.

```bash
bash scripts/check-imaging-em-artifacts.sh    # READ-ONLY. 0 = clean, 1 = found, 2 = off-host
bash scripts/assert-migrations-applied.sh     # READ-ONLY. 0 = all applied, 1 = UNAPPLIED, 2 = off-host
```

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
| `apps/transcribe-md/tests/e2e/fixtures/**` | committed E2E fixtures |
| `apps/transcribe-md/src/**/__tests__/__fixtures__/**` | committed unit fixtures |
| `apps/transcribe-md/src/**/__fixtures__/**` | committed unit fixtures |

Every one of these is BLANK or a sample input. **They must survive every future
sweep** — a sweep that eats the blank fixtures breaks the twin work, which is
why they are named here as carefully as what must not survive.

Adding a row here means adding the same row to the hook. If the two ever
disagree, the hook is right and this table is stale.

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
