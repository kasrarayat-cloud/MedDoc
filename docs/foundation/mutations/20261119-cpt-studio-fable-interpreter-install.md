# Prospective declaration: CPT Studio's Claude Fable 5.2 interpreter with round r3's question stage at cpt.quillmd.com (c2e53f8e7d33 to e426c747c7b7), installed blue/green with the demo kept serving, migrations 0014 and 0015 applied, the question stage at effort max under a 25 US dollar per-document ceiling and 4 requests at once, nothing re-assessed

Authority: the owner's directive of 2026-11-09 ("replace the legacy semantic interpretation engine with Gemini"; a
shadow-only result is not done: done is installed on cpt.quillmd.com and verified, with the site kept up and records
preserved), as the owner amended it since, each recorded verbatim in docs/foundation/rulings/2026-10-23-cpt-studio-gi.md
with this programme's interpretation and a RULINGS.md row: 2026-11-12 (Gemini owns the open-ended clinical
interpretation: design v2, DECISIONS D178-D182; the funding authority, D183; the automatic recheck after a save,
AMENDMENT-1, D184 and D208); 2026-11-15 (the interpreter is Claude Fable 5.2, D275; accuracy fixes are general rules,
D276; paid testing one short and one realistic note at a time, D277; AMENDMENT-2 adopted, D279); 2026-11-16 (no approval
stop on the test spend, a protective ceiling of 120 US dollars, a minimal walk, D293); 2026-11-17 (Fable judges the
readings, with located proof and an agreeing cross-check, D306; one calibration item per question request, D319; "build
it and then install the whole update on live website" and "Keep on the max and go live", D320; and the owner's "i
approve" of the install's accepted-capability loss and of the cost per note at effort max, D321 - which the build
narrows, D329 (3)); and 2026-11-18 (the live site's cost ceiling: 25 US dollars of question worst case per document and
4 requests at once, the owner's "ok", D326 - counted per version of a document, D329 (4); and his direction "dont worry
about the api budget ill take care of it by my self jsut focus to relase and i wanna walk live and try my docs as soon
as possible", D331: the Anthropic account is his to manage). `landed in fe6ba4eb0 (int7) and present on 394f1c1e3148 by grep: docs/foundation/rulings/2026-10-23-cpt-studio-gi.md's sections for D306, D319, D320, D321 (with D329 (3)'s narrowing), D326 (with D329 (4)'s correction) and D331, and their six RULINGS.md rows dated 2026-11-17 and 2026-11-18. The owner's directions of 2026-11-19 - D344 (round 7 the last round, then the paid test, its results, then the walk), D347 (the paid test started beside round 7's checks over the preflight's load line) and D349 (go live now on this revision; no more patch rounds; Fable to judge the codes completely as the next change) - are recorded verbatim with their RULINGS.md rows by the commit that lands this file`.
The integration and deployment owner is session `738699b2`.

The install is also governed by the 2026-10-23 directive cited in docs/foundation/mutations/20261023-cpt-studio-install.md
(a protected synthetic demonstration; provider credentials server-side; app.quillmd.com and unrelated services
preserved). CPT Studio stays standalone. No purchase, agreement, new key or payment change is part of this act: the
interpreter uses CPT Studio's existing Anthropic credential (D275), and any top-up of the Anthropic account is the
owner's own act (class d), outside this declaration. D3 to D5 stay open, D7 stays off, and decision (m), checklist item
4.6 and the questions Q1 and Q2 stay the owner's `not raised again with the owner before this act; none of his directions since (D331-D349) touches them`.

Revision to install: `e426c747c7b73996d7f9fb4d598517aa0bc4d89a`, the merge commit of PR #1495 (branch feat/cpt-studio-gemini-interpreter-20261109,
head `394f1c1e3148f98c766c97b83170a4b3079796cd`; the merge commit's tree under cpt-studio/, scripts/run-ruled-mutation.sh and scripts/lib/
equals the head's: `git diff --quiet 394f1c1e3148f98c766c97b83170a4b3079796cd e426c747c7b73996d7f9fb4d598517aa0bc4d89a -- cpt-studio scripts/run-ruled-mutation.sh scripts/lib` exit
0). It contains origin/main as of the merge (`56b70eb5fc41217da7b9975c94a6963e3d91ff9b`). Image tag
cpt-studio:`e426c747c7b7`. Its citation, on the revision: `CI 44608115734, secrets-scan 44608115880 and cpt-studio 44608115747 on e426c747c7b73996d7f9fb4d598517aa0bc4d89a, started at the merge (2026-11-19T20:22:58Z) and in progress when this file was committed; each must have completed with success, read in both views (by commit and by branch), before the first phase runs (checked at J0; a run that is not success is a stop). The merge commit's whole tree equals the PR head's (`git diff --quiet 394f1c1e3148 e426c747c7b7`: exit 0), so its cpt-studio run repeats the head's, which passed: system check no issues and no missing migration ("No changes detected"); the Django suite with tests.v2, 13,103 tests OK (13 skipped); ops 878 OK (1 skipped); ops/verification 69 OK; the browser verifier's 154 node tests pass; the dependency audit "No known vulnerabilities found" with pypdf 6.21.4`.
The PR head carries the same tree and citation: `CI 44591685599 success, secrets-scan 44591685615 success and cpt-studio 44591685716 success on 394f1c1e3148f98c766c97b83170a4b3079796cd (completed 2026-11-19T20:21:55Z)`.
cpt-studio is not a required check.

It replaces the live revision c2e53f8e7d33732d5badd4ce9b681f274eb5c471 (image cpt-studio:c2e53f8e7d33, id
sha256:02a99d53026f..., its web on 127.0.0.1:9150 since that install's switch from 9151), installed 2026-11-08 under
docs/foundation/mutations/20261108-cpt-studio-structure-round-install.md (landed by PR #1490 as 09c4eab2). That image is
kept as the rollback image. That declaration and its receipts stay as they are.

Execute each phase separately through scripts/run-ruled-mutation.sh with
`python3 -B cpt-studio/ops/install.py --phase PHASE --revision e426c747c7b73996d7f9fb4d598517aa0bc4d89a --receipts /home/claude/cpt-studio-install-20261023`.

Phases, in this order: preflight; image; app (with `--provider-mode live --interpreter-mode live --astra-mode live
--fable-mode live --authorization-ref docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`, no `--access-check`);
passages; license-note; verify. `--interpreter-mode live` installs the interpreter live (without it every upload's
reading pauses, which verify reports); live needs `--authorization-ref` and /etc/cpt-studio/anthropic-credentials.env,
the Fable participant's file, which the worker alone binds read-only, once, for the participant and the interpreter
(ops/INSTALL.md "Phases"; AMENDMENT-2 1.11). `--astra-mode live --fable-mode live` keep the harness participants live,
as the c2e53f8e7d33 pair runs them (OPEN-QUESTIONS L2: no participant is lost). **Every container the installer starts -
the web, the worker and each one-shot - is given the question stage's two figures as settings, read from the revision's
cpt-studio/cptstudio/settings.py defaults: `CPT_STUDIO_QUESTION_DOCUMENT_CEILING_USD=25` and
`CPT_STUDIO_QUESTION_ROUND_CONCURRENCY=4` (ops/install.py question_figures and runtime_env; DECISIONS D326: "The install
writes both, and its declaration names them").** No monthly spending threshold is written:
`CPT_STUDIO_QUESTION_PROVIDER_CAP_USD` stays unset, so the Anthropic account's own limit is the only monthly bound, as
before round r3 (a figure only the owner sets, class d).

Run them from a clean, detached checkout of the merge commit that lands this declaration. That commit must be a
descendant of the revision that changes nothing under cpt-studio/, scripts/run-ruled-mutation.sh or scripts/lib/ (the
installer's check_tree): so nothing under cpt-studio/ (HARNESS.md included) is edited in the declaration's PR. Read
each receipt before the next phase. The receipts directory is the live install's own (it holds the live vhost's
receipts, which rollback-vhost needs); no receipt there is changed: each file is created once. Each phase runs under
the door's watchdog (scripts/lib/run-watched.sh: wall-clock ceiling RULED_ACT_MAX_SECS, 3,600 s by default); the app
phase with an idle old worker takes minutes, and an installer killed by that ceiling inside S3 writes no receipt and runs
no undo (ops/INSTALL.md, Recovery notes), which is a stop.

Not run: secrets (the three-file set and both participants' copies exist; the interpreter reads the Fable participant's
copy, made under docs/foundation/mutations/20261102-cpt-studio-participant-credentials.md; `both present at the structure round's preflight (2026-11-08T22:52Z: astra and fable present; /etc/cpt-studio-provider-sources/openai.env and anthropic.env root-owned 0600), and this act's preflight receipt must read both present and unchanged`),
db, reference, provision, operators, reassess, http-vhost, cert, https-vhost, rollback-vhost, rollback-app and
switch-back. Their objects exist and do not change, and nothing in this revision asks for them. reassess is never run by
this install: FINAL-V2 6.2 and D16 - the install re-assesses nothing, and a re-assessment of a legacy revision reads the
document again and sends. rollback-app (ops/install.py PHASES; the Recovery notes' remedy for an undo that stopped half
way) runs only by a decision recorded under this declaration; install-r3/act_f.sh refuses it. switch-back is the incident
path (below), run only by such a decision, after a fresh preflight.

Between c2e53f8e7d33732d5badd4ce9b681f274eb5c471 and the revision, these are byte-identical
(`exit 0 on 394f1c1e3148 (read 2026-11-19T20:11Z; re-measured on the act checkout at J3)`): cpt-studio/deploy/ (Dockerfile,
entrypoint, gunicorn, nginx templates, .dockerignore); cpt-studio/studio/reference/data/ (the three CMS passage files);
scripts/run-ruled-mutation.sh, scripts/lib/ and scripts/check-cotenants.sh. These change, and are named here: everything
the delta below lists - among them cpt-studio/requirements.txt (the pypdf line alone: 6.21.2 to 6.21.4),
cpt-studio/requirements.in and the dev requirements (hypothesis and mypy, test-only), cpt-studio/cptstudio/settings.py and
urls.py, cpt-studio/studio/models.py and migrations 0014 and 0015, cpt-studio/studio/jobs.py, the customer page (studio
static app.js and styles.css; the client contract customer-2026-11-03 to customer-2026-11-13), and the installer itself
(cpt-studio/ops/install.py, ops/INSTALL.md, ops/rollback_check.py): this act runs this revision's installer.

Before preflight the operator runs, in the act's checkout:
- `git diff --quiet c2e53f8e7d33732d5badd4ce9b681f274eb5c471 HEAD -- cpt-studio/deploy cpt-studio/studio/reference/data scripts/run-ruled-mutation.sh scripts/lib scripts/check-cotenants.sh`, exit 0;
- `git diff --name-only c2e53f8e7d33732d5badd4ce9b681f274eb5c471 HEAD -- cpt-studio/studio/migrations`, listing exactly
  cpt-studio/studio/migrations/0014_event_inventory.py and cpt-studio/studio/migrations/0015_inventory_appraisal.py;
- `git diff -U0 c2e53f8e7d33732d5badd4ce9b681f274eb5c471 HEAD -- cpt-studio/requirements.txt`, changing the pypdf line
  alone;
- `git diff --name-only e426c747c7b73996d7f9fb4d598517aa0bc4d89a HEAD -- cpt-studio scripts/run-ruled-mutation.sh scripts/lib`, printing nothing.

Any other difference is a stop.

**The deploy range against held declarations** (docs/DEPLOYMENT_RUNBOOK.md 2.5, before this declaration is committed):
`the range c2e53f8e7d33..e426c747c7b7 is five merges (#1490, #1491, #1492, #1494, #1495); its 136 runtime files (git diff --name-only, docs, tests and markdown aside: 135 under cpt-studio/ and .github/workflows/cpt-studio.yml) were searched for by path, with and without the cpt-studio/ prefix, across docs/deploy-reports/, docs/foundation/deploys/ and docs/foundation/mutations/ on 2026-11-19, after the positive control (deploy-prod.sh: 60 files). Fifteen declarations name some of them - the fourteen CPT Studio installs and credential acts from 20261023 to 20261108 and 20261101-quillmd-rebuild-release-797199c7c625 - and five deploy reports (evidence, not declarations). None is HELD by DEPLOYMENT_RUNBOOK 2.5's four rows: each declaration's revision is an ancestor of, or is, the running c2e53f8e7d33 (`git merge-base --is-ancestor`), so it has shipped and cannot be overtaken. PRs #1492 (records) and #1494 (pypdf 6.21.4 with its compatibility layer) have no declaration of their own: they are judged jointly here - the delta above names them, the image phase's PDF gate and the walk's PDF upload judge #1494`.

## The migrations

Two, both additive under the installer's gate (ops/install.py migration_safety, which the image phase runs before it
builds anything; the test image builds of 21e79eff7b78 and earlier logged "all safe" over 0006 to 0015). They are
applied by the app phase's migrate one-shot BEFORE the switch, while the c2e53f8e7d33 pair still serves: that pair never
reads or writes any of them, a row it inserts names none of the new columns (they stay NULL there), and a rolled-back
pair runs on the migrated schema. Nothing is reversed. There is no migration after 0015: int6's
cpt-studio/studio/migrations/ ends at 0015_inventory_appraisal.py, round r3's question runs being ProviderRun rows (purpose
appraisal) whose scope names their round and batch, and round 4 changes engine files only `394f1c1e3148's cpt-studio/studio/migrations/ ends at 0015_inventory_appraisal.py, no 0016; 0014 sha256 db7e5f1a... and 0015 sha256 c825ab66..., byte-identical to int6's`.

**0014_event_inventory** (design v1's S05, unchanged since; FINAL-V2 6.3):
- creates `studio_eventinventory` (EventInventory: interpretation_version and inventory_version varchar 40;
  text_sha256, request_sha256, response_sha256 and sha256 varchar 64; state varchar 12; events, encounter_facts,
  open_questions and verification JSON; created_at; foreign keys encounter, provider_run and revision, PROTECT), with
  the index `studio_inventory_versions` (revision, interpretation_version, inventory_version) and the unique constraint
  `one_inventory_per_revision_versions_run` (revision, interpretation_version, inventory_version, provider_run), both
  on that new table;
- adds `studio_encountercontext.event_inventory_id` and `studio_assessment.event_inventory_id` (nullable foreign keys
  to the new table, PROTECT, no default, with Django's own non-unique index) and `studio_assessment.interpretation`
  (nullable JSON, no default);
- creates `studio_interpreterhold` (reason varchar 20, http_status, vendor_status, violations, created_at, run PROTECT)
  and `studio_interpreterholdrelease` (note, created_at, hold one-to-one PROTECT, released_by PROTECT).

**0015_inventory_appraisal** (FINAL-V2 6.3 as AMENDMENT-1 section 10's first row, step 1d-A1, edited the uninstalled
migration; the file states it - so FINAL-V2 6.3's "Nothing else" reads one column and two tables short):
- adds `studio_eventinventory.appraisal_run_id` (nullable foreign key to the pass-2 ProviderRun, PROTECT; on 0014's new
  table);
- adds `studio_encountercontext.earlier_assessment_id` (nullable foreign key to an Assessment, PROTECT; AMENDMENT-1 4.5,
  A5: the earlier codes a context was made after);
- creates `studio_providerhold` (provider and reason varchar 20, http_status, created_at, run PROTECT) and
  `studio_providerholdrelease` (note, created_at, hold one-to-one PROTECT, released_by PROTECT): the installation-wide
  holds of Corti, Astra and Fable (AMENDMENT-1 7.3, A16 and A20).

Together: studio_migrations 13 to 15, last 0015_inventory_appraisal; five new tables, empty; four nullable columns on
existing tables (studio_assessment.event_inventory_id, studio_assessment.interpretation,
studio_encountercontext.event_inventory_id, studio_encountercontext.earlier_assessment_id), NULL on every existing row;
one more on a new table (studio_eventinventory.appraisal_run_id). No data migration, no RunPython, no backfill, no
default and no NOT NULL on any column added to an existing table.

## Delta shipped (c2e53f8e7d33 to the revision)

    git diff --stat c2e53f8e7d33732d5badd4ce9b681f274eb5c471 e426c747c7b73996d7f9fb4d598517aa0bc4d89a -- cpt-studio: 1,069 files changed, 664,102 insertions(+), 2,217 deletions(-) (on 394f1c1e3148, whose cpt-studio tree the revision carries: H4; re-measured on the act checkout at J3)

At 087538cd8 (int3): 1,039 files changed, 623,340 insertions(+), 2,188 deletions(-). Round r3's own stat, on the final
tree: `int10 = int7 (int6 + rules4 + rules5 + rules6 + pairs + pairs2, D330 (4)) + int8 (D336 (1)) + the D339 rollback runner + int9 (D342 (1)) + int10 (D345); int10.diff (int3 to int10) sha256 576b10b0cd2a1dda...; `git diff --stat 087538cd8 394f1c1e3148 -- cpt-studio`: 172 files changed, 41,514 insertions(+), 781 deletions(-)`.

**This is a TREE, not one change** (AGENTS.md: a declaration is bound to a change, a deploy ships a tree). Every part
is named here, and the expected rows below are written for the whole of it:
- **From main, never installed:** PR #1492 (cpt-studio/HARNESS.md only: records) and PR #1494 (merged 2026-11-13,
  56b70eb5f): pypdf 6.21.2 to 6.21.4 under a fail-closed 6.21.2 compatibility layer (studio/ingest/pypdf_compat.py,
  which accepts exactly 6.21.4; ingest/_child.py, extract.py and pdf.py; ops/verify_passages.py; the image phase's PDF
  gate in ops/install.py). It ships here and is judged here: the image phase's PDF gate, and the walk's PDF uploads.
- **Design v1 (S01-S17, Gemini; superseded on the path, kept for its tests and as stored-run readers):** the
  interpretation package's top-level v1 modules, the dormant Gemini adapter (studio/interpretation/adapter.py, never
  called on the path), migration 0014, the interpreter hold, the legacy-call sentinel, the D22 report, the D15 runner
  (ops/rollback_check.py).
- **Design v2** (FINAL-V2, D178-D182; build waves 1-6 and repair rounds w7r-w9r, D185-D291): Fable owns the reading; a
  second call appraises it; the engine reads facts only. studio/interpretation/contract/ and engine/
  (`cpt-studio-events@`); the store binds every run in one EventInventory row; the overlay reads `event_coding@2`;
  fingerprints carry no word text and name their engine and requirements versions (decisions never carry across
  engines, FINAL-V2 6.5). The legacy keyword reader (studio/gi/* and the validation checks that read it) no longer runs on
  the new path: the sentinel refuses a retired call and the D22 report measures `legacy_calls` and `retired_calls`.
- **AMENDMENT-1** (D184, D208): the codes update automatically after a saved change of coding details; a v2 revision
  re-derives over its frozen inventory with no interpreter call; a legacy revision's first save reads it (both passes and
  the question stage) and clears its legacy decisions, kept as records; installation-wide provider holds
  (ProviderHold); `EncounterContext.earlier_assessment`; "what changed", earlier decisions and earlier downloads on the
  customer page (client contract customer-2026-11-13).
- **AMENDMENT-2** (D275-D293): the interpreter is Claude Fable 5.2 (`claude-fable-5-2`, the Anthropic Messages API,
  studio/interpretation/fable_adapter.py, `anthropic-version` 2026-10-21, no fallback model, no sampling parameter, an
  answer read only when Anthropic reports exactly that model); both fact passes at effort `high`, `max_tokens` 128,000,
  each send and read within 1,320 s inside a 1,380 s stage (stale thresholds 1,440 s for pass 1 and, since round r3,
  1,560 s for pass 2), the response cap 16 MiB; the slot rule; a decline (stop reason `refusal`) holds the installation and stays request-bound after a release;
  usage priced at $8 / $40 per million input / output tokens (cache write $10, read $0.20); the customer denylist covers
  `claude-fable-5-2`, "Claude Fable 5.2", `fable_unknown` and `AnthropicTimeout`.
- **Repair rounds r2 to r2f and int3** (D294-D316, 087538cd8): pairs 1-4's classes, the lesion arms read both
  directions, weakened dates, the tools' place rules.
- **Round r3** (D306-D349; int4 to int9 and the final int10, `394f1c1e3148f98c766c97b83170a4b3079796cd`): the QUESTION stage, described in
  full in the next section; built with D310 (1), D312, D313, D314, D315, D316 (QB with QD), D317 (1) and (4), D318
  (1)-(3) and D319, amended by D322 (one job per round), repaired after three adversarial passes (D324: seven
  false-READY paths; D325: six more; D328: five more, none a regression), finished by round 4 - int7, D330 (4):
  int6 + rules4 + rules5 + rules6 + pairs + pairs2 - (D328 (1) the lower-GI route table by principle; D328 (2) and D330
  (2) a statement-act pair's relation as ONE proposition across every answer that can set it apart, Q-FACT included;
  D330 (1) THE LOWER-GI PATH GUARD, described in the next section) - and completed by rounds 5 to 7 (int8: the guard's
  release rule, D336 (1); int9: one predicate over settle's outcome, D342 (1); int10, the last round by the owner's
  D344: a made place named in every field and the route read from the through's own entry, D345), each round with
  its adversarial passes and an independent final check:
  `every verified finding of rounds 4-7 was repaired by principle (D330, D336, D342, D345) or recorded as a fail-safe hold cost; the last final check (check:final8, workflow wf_2bbc4c01-546, build-v2/a2b/r3b/r3n/final-check) read READY TO COMMIT, and its lows with round 7's L10R-1 are recorded, not built (D349 (2), under "What is not claimed"). On 394f1c1e3148: tests.v2 4,275 OK; v1 8,830 OK (7 skipped); ops 878 OK; ops/verification 69 OK; the tools suite 411 OK (490 with the key tool, E0); v2dbtests 4 OK; D15 tooling 9 + 7 OK; mypy --strict as int9; D345's mutants 36 of 37 killed, 1 equivalent`.
  Not built (D320): Q-GROUP, Q-KIND, F9, U2, A3's narrowing and the CAUSE row's wrapper - their holds stay with the
  coder (fail-closed). The customer surface is unchanged: no customer or reviewer string names Fable, a question, a
  proof or an answer (DESIGN-v2 (i)); the progress panel words the question stage as it words pass 2 ("Checking the
  reading against the document").
- **Labels the new path writes** (studio/interpretation/__init__.py at int6; `unchanged on 394f1c1e3148: interpretation/__init__.py is byte-identical to int6's`): pass 1
  `gemini-events@3`, pass 2 `gemini-appraisal@2` (pair `gemini-events@3/appraisal@2`), inventory `gemini-inventory@3`,
  engine `cpt-studio-events@3`, requirements **`cpt-requirements@3`** (D324 (11), D327 (3)), adapter
  `anthropic-messages@cptstudio-interp-1`, provider `anthropic`, model `claude-fable-5-2`, context `gemini-context@2`,
  routing `gemini-routing@2`. Legacy rows keep their labels and are read as stored. Question runs are ProviderRun rows of
  purpose `appraisal` whose scope names their question round; the question stage's Job.kind is `question`.
- **The installer** (ops/install.py; ops/INSTALL.md updated for round r3): `--interpreter-mode`; the interpreter's shared
  credential (one bind); design v2's reads before the switch (V1_ROWS refuses on a v1 row; INSTALL_COUNTS counts and
  never refuses); the question stage's two figures written into every container (question_figures); the undo closes
  `interpret`, `appraise` and `question` stages on every undo whose next worker lacks them (read from that worker's own
  jobs.STAGES; READING_STAGE_KINDS = ('interpret', 'appraise', 'question') is what the undo's note counts and the
  put-back re-queues), reverts and puts back pending saves (AMENDMENT-1 9.4); STOP_SECONDS['worker'] **1,800 s** (above
  every stage deadline and stale threshold, the question stage's 1,588 s and 1,768 s included); the access check waits
  1,468 s for the provider lock, bounded at 1,900 s; the PDF gate (PR #1494). ops/INSTALL.md's one stale sentence -
  "60 minutes from the put-back" (:845-846 at int6) - is read here as the code's 120 minutes (jobs.QUEUE_DEADLINE).

**New readings apply to new uploads, addenda, member saves and the stages they queue. The install re-assesses or
re-sends no encounter, and no stored assessment, decision, answer or report is rewritten.**

## The question stage on the live site (D306, D320, D322, D325 (3), D326, D330)

Whenever the engine holds a candidate code for a READING uncertainty (the families the probe validated: Q-REL, Q-FACT -
the reach, the part link and the entry - Q-ONLESION, Q-ABSORB, G1), Fable is asked a question with the claim's exact
negation as its control and ONE calibration item per request (D319), with the whole note, the act's and the statement's
passages and the question in plain words. An answer is established only when its request is healthy, its claim is
supported with a located quote inside each named object's own passage (contract/proof.py) and its control is
rejected, every other proposition asked of the same slot or the same statement-act pair agreeing with it on both claim
and control (D325 (1), D328 (2)); an established answer can release a hold and can never exclude (exclusion reads the
base reading's own decision, D324 (6)). A pair's relation is ONE proposition across every answer that can set it apart,
Q-FACT included: a release through a row, or a kept entry's pair dropped from the unlisted pairs, stands only when every
pair-family question asked of the same pair, in any request or round, read AFFIRMED in an answered, healthy request;
otherwise the pair keeps its base relation (D330 (2)). The fact requests stay int3's byte for byte (I-FACT, effort high).

**The lower-GI path guard** (D330 (1); fail-closed by construction, built by lane rules6 on int6 + rules4 + rules5;
completed by int8's release rule, D336 (1), int9's one predicate over settle's outcome, D342 (1), and int10, D345).
Since int8-int10: a claim narrows the reading only when it is established through its control or unappraised
(settled_narrows); a filed field names its shape in every field (an established subtype that defines that place
aside); and the route's own entry is the entry the session's through names, its established type giving the route.
It runs after every existing arm, on every lower-GI code with a row in D328 (1)'s route table (colonoscopy 45378-45398,
sigmoidoscopy 45330-45350, proctosigmoidoscopy 45300-45327, through-stoma 44380-44408, pouch 44385-44386). Such a code
is held with the table's own hold (an existing reason) unless EVERY anatomy entry of the document is, for that code's
route, either the entry the route itself uses (the stoma or pouch the session established it entered through) or a
match for a row of the RULED HARMLESS SET - one finite typed table, one row per route family and entry shape, an entry
matching only when every possible value of every field it files (type, subtype, every joins member, organ and region,
silent and unreadable fields included) lies within the row. A per-anus code also holds when the session's approach is
filed or supported as anything but transanal, or its through may name an entry that may be a stoma or a pouch; a silent
approach reads per anus only when no entry may be a stoma or a pouch, as int6. The guard only holds: it never
releases what an arm held, and no answer lifts it (D324 (4)). The harmless set keeps int6's decisions on the common
inputs (D328 (1) (c)), on entries outside the lower GI tract and on a surgically absent appendix; a shape outside it
holds - an omission costs a hold for the coder, never a false READY. A census test enumerates every entry shape x route
family x approach and through state, and a completeness test asserts the guard reads every row of the route table
`on 394f1c1e3148: catalogue.HARMLESS (the ruled harmless set) and catalogue.ROUTE_OWN; tests/v2/test_r3m_guard.py (settle's whole outcome table, 39,095 checks; every uncontrolled type with 0, 1 and 2 joins members, 33,150 shapes x 6; 423 read claims and 1,225 landmark pairs, derived from the catalogue) and tests/v2/test_r3n_guard.py (21 tests: 142,920 read-claim checks, the through over every type x settle's states x none, 48,000 reader guards, 6,250 organ-and-joins combinations, 3,729 own-entry type states), each RED on the round before and GREEN here`.
Its recorded limits are under "What is not claimed".

As installed (cpt-studio/cptstudio/settings.py, fable_adapter.py, question_claims.py, asking.py and jobs.py at int6;
`each re-read on 394f1c1e3148: settings.py, fable_adapter.py, contract/question_claims.py and jobs.py byte-identical to int6's; engine/asking.py moved in rounds 4-7 and still reads QUESTION_BOUND 18 (derived) and CALIBRATION_COUNT 1`):

| what | value | why |
|---|---|---|
| effort | `max` (QUESTION_EFFORT) | D306's second addendum (b), D320 |
| max_tokens | 128,000 | the connector's maximum output |
| claims a request | QUESTION_BOUND 18 = 8 questions and 1 calibration item | D318 (2) and its addendum, D319 |
| a request's send deadline | **1,408 s**, derived: 128,000 tokens at 95 tokens a second, rounded up, plus 60 s | D322 (4): below the slowest max-effort rate measured, 101.04 |
| the question stage's deadline | **1,588 s** (120 s computation, 1,408 s send, 15 s recording, 45 s) | one wave at 25 and 4 |
| its stale-stage threshold | **1,768 s** (and pass 2's moves from 1,440 s to 1,560 s; pass 1's stays 1,440 s) | a live round is never swept |
| the worker's stop timeout | **1,800 s** | outlasts every stage |
| the queue window | **120 minutes** (jobs.QUEUE_DEADLINE) | a job queued behind two long notes still starts |
| jobs | ONE `question` job PER ROUND; its requests sent concurrently, one thread each, under the provider lock held once for the round, after ONE reservation of every request's worst case | D322 (1)-(3) |
| requests in flight | **at most 4** (`CPT_STUDIO_QUESTION_ROUND_CONCURRENCY=4`); the rest of a round waits, in the same job, for the next wave | D325 (3), D326 |
| per-document ceiling | **25 US dollars** of reserved worst case over every round of ONE revision - a version of the document: an addendum or a new version starts a new reading with its own 25 (jobs._document_reserved_usd(revision)) (`CPT_STUDIO_QUESTION_DOCUMENT_CEILING_USD=25`); a round that would pass it is not sent, its questions stay unresolved and their codes go to the coder; exactly at it is within it; a request whose own record proves it cost nothing stops counting | D325 (3), D326, D329 (4) |
| monthly threshold | none configured (`CPT_STUDIO_QUESTION_PROVIDER_CAP_USD` unset): the account's own limit is the only monthly bound | the owner's figure, class d |
| the rate floor | 110 tokens a second, a measure for question requests, never a hold | D310 (9) |
| rounds | until no new question (a defect guard of 8 rounds); an overrun is split and sent again; no question is dropped for a bound | D306 (d), DESIGN-v2 e.4 |

At 25 and 4 a round reserves at most 4 requests (25 // 5.128), one wave, so the stage keeps its 1,588 s and 1,768 s.
A later figure is a one-line change of settings.py's default and an install of that revision (D327 (5)); a figure that
allows more than one wave first needs the pipe lane's recorded change (the access check's lock wait and the queue
window, D327 (6)). Each request keeps its own deadline, usage, classification, stored answer and outcome, and fails
alone: a refused, failed, cut-off, declined or unreadable request leaves its questions unresolved and their holds stay;
nothing is retried automatically. A 429 naming `rate_limit_error` fails that request alone; any other 429, a 402, 401 or
403 sets the installation-wide hold (D39), which decides no question request: the document's stage pauses and, after
an operator's release, a member's Resume sends each owed request once. A worker that dies mid-round leaves each request
in flight an unknown outcome (one reconciliation each); no send is repeated.

**Cost and time** (D320, D321, D326, D329 (4)): about 3 US dollars and 10 minutes for a short note and about 14 dollars
and 25-55 minutes for a long one. The 25-dollar ceiling counts per REVISION (jobs._document_reserved_usd(revision)): an
addendum or a new version of a document starts a new reading with its own 25 dollars, so one version of a note costs at
most about 36 dollars (reading up to about 11 - D278's worst reading, $11.06 - and questions up to 25), and a document
read again after an addendum can cost that again. The owner was told "at most a note costs about $35" when he approved
the ceiling (D326); those words stay as they were said, and OWNER-ITEMS item 5 tells him the corrected figure. The owner
was told about $12 for a long note (D320) and approved "about $3 short, about $12 long" (D321); r3-probe-2's long note
measured about $3.40 of fact passes and $11.25 of questions (with four calibration items a request, before D319), which
is where the $14 comes from. A document over 20,000 characters or 40 pages is not sent to Fable at all. The
confirmation pair re-measures both on the built code: `S05 (B/fb13, an ERCP, 1,030 bytes) $1.908776 - both fact passes, 288 s, no question asked; L05 (an EGD, 7,678 bytes) $4.805311 - fact passes 562 s and one question request of 448.5 s, about 17 minutes in all; the pair $6.714087`.

## The accepted loss (D321, class b, as narrowed by the build: D329 (3); FINAL-V2 6.2 and 6.5; AMENDMENT-1 6.4, 6.5, 9.3)

The owner's approval of 2026-11-17T18:27:53Z ("i approve") accepts that a legacy (c2e53f8e7d33) assessment's approval
does not carry across engines. D321's ruled clause (a) - "a new approval or export of a legacy assessment is refused
until the encounter is checked again by its explicit act" - is BROADER than the build: the lead read the build
first-hand (int6 tests/v2/test_update_review.py BindingTests :107-124) and recorded the difference as DECISIONS D329
(3). The build narrows the loss the owner accepted, so no new approval is needed; the owner is told the exact behaviour
in plain words (OWNER-ITEMS item 1), and the rulings archive's D321 interpretation (a') cites the same item. As built:
- Nothing changes at the install: every encounter keeps its codes, decisions, approvals and downloads, and an untouched
  legacy encounter stays decidable and exportable exactly as today (its codes are fresh).
- The first saved change of a legacy encounter's coding details (the date, the setting, the billing context or the
  patient's status), an addendum to it, or a Resume (which reads it first) starts the new reading. From then until the reading completes no decision is recorded and no export is made of its earlier codes
  (review._allowed and _record_decision; reports.update_refusal).
- When the reading completes, every legacy decision is invalidated - never carried, since the events engine's
  fingerprints name their engine (review._carry_decisions) - and stays as its Decision row with its DecisionInvalidation,
  listed in Earlier decisions as made on the earlier reading; the legacy exports stay in Earlier downloads with the
  EARLIER banner; the new codes are reviewed and approved again.
- Counts at the baseline: `approve 51 on 31 encounters, reject 6 on 6, reinstate 1 on 1, and revoke 2 on 1 (a revoke is its own row, read beside the approvals, never netted)`.

## Measured before this declaration

**The confirmation pair** (D320 (6): the only paid step before the install; one short and one long note through the
built code on the test image of `394f1c1e3148`, through testinst/record_pair.sh and the r3 harness):
`S05 = B/fb13 (sha256 16d7ceb8b83882e0..., the pre-registered value) and L05 (sha256 d9ef21374d62c3d5..., as devsets_v2.py pair --k 5 and the plan computed it, never by opening the note before the send); batch pair-05, ONE batch with --questions through testinst/record_pair.sh on cpt-studio-test:394f1c1e3148; sent 2026-11-19T19:05:07Z-19:26:57Z, exit 0, stopped null (freeze ec26ec68..., manifest 3795a86c...), $6.714087 over 5 sends under the batch cap and the test-total stop. B/fb13: pass 1 $1.213520 in 157.7 s, pass 2 $0.695256 in 130.6 s, no question request (round 1 listed none). L05: pass 1 $1.768639 in 352.3 s, pass 2 $1.168856 in 209.4 s; one question request (round 1: 6 claims, one calibration item) $1.867816 in 448.5 s - 8,907 input and 44,914 output tokens, 44,336 of them thinking, about 100 tokens a second - reserving $5.304024 of the 25 USD ceiling; no round refused; the slowest question request 448.5 s against 1,408 s. Per code (score_v2, 10 rows): 9 correct, 1 unnecessary hold (L05 43249, held on coding_rule:competing_codes beside 43248), wrong READY 0, wrong exclusion 0. B/fb13: 43262 and 43264 READY; 43260 (included in the therapeutic ERCP), 43265 (not documented) and 74328 (unprofiled; the images were read by radiology) held. L05: 43239 READY, released by Fable's answer that the scope reached the duodenum; 43235 (included), 43248 (the Savary dilation is the 2021 history) and 43255 (no hemostasis) held. Both released proofs read first-hand: no hollow proof. Calibration breaches 0; no UNKNOWN, no deadline cut, no hold set (HOLD.json absent); the recorded replays reproduced 2 of 2. The test spend after: 36.233259 of the 120 USD ceiling. **Score (ii) = 6 (DECISIONS D348):** six candidate codes, each proposed alone, are held without the answers and READY with them - 43198, 43202, 43213, 43214 and 43220 (esophagoscopy codes) and 43233 (an EGD with a balloon of 30 mm or larger) - each wrong on L05, an EGD that reached the duodenum with an 18 mm through-the-scope balloon. Fable's answers were right (the key agrees); the engine's esophagoscopy rows accept any reached point, and no row reads a balloon's size, the transnasal route or a retrograde dilation. By the pre-registered pass rule this was a stop; the owner overrode it (D349, quoted under "What is not claimed") and directed this install`.
Its pass rule was written before the send: `install-r3/confirm-pair-preregistration.json (written 2026-11-19T19:04:43Z, 0400, sha256 0ed8ec3153fb100d...): stop on a wrong READY, a wrong exclusion, a hollow proof, a calibration breach, an UNKNOWN or a deadline cut, an installation-wide hold for any reason but money, or a TOO_LONG answer left unsplit; an unnecessary hold reported and judged, not a stop; a ceiling refusal reported, not a stop; a money stop judges nothing; and E-COMMANDS section 5 requires score (ii) 0 on the second score_ii run`.
It ran as ONE batch in the harness's documented form (D329 (1): `record_pair.sh ... --questions --plan`, then the same
without `--plan`; the replays with `--answers recorded`, `release-none` and `release-all`; key_compare.py and
score_ii.py), on the r3 harness installed as int6-tools.diff alone with int4-testinst.diff, each file's sha256 and the
file counts asserted and the suite green (D329 (6)). Its money (D329 (2), D331): each round gated on the SUM of its
requests' worst cases; the batch cap the pair's full worst case; the harness's provider figure set by D331's formula so
that its project threshold could not bind before that worst case; the 120 USD test ceiling unchanged; a provider refusal
for money a money stop - `the batch cap 74.26 (the pair's full worst case from the plan's own figures: pass-1 worst cases 6.495346 and 6.554674, each pass 2 bounded at 5.60, and 2 x 25 of question worst case), the harness's provider figure 250 (ten-dollar ceiling of the month's 101.683628 - the harness ledgers 71.683628 and the site's 30 - plus 74.26 + 25 + 40), the test total 120 unchanged; no gate bound`.
Its by-words key (D314 (5) in D329 (1)'s form) was written from the batch's RECORDED requests after the send and before
any answer, outcome or replay was read, its sha256 and UTC logged first:
`B/fb13 had no question request (its END logged 2026-11-19T19:27:23Z); L05's one round sealed 2026-11-19T19:28:41Z, sha256 39f0816e887ac276..., its END 19:29:02Z; key_requests.py --check printed CHECK PASSED at 19:29:09Z; key_compare: L05 AGREES (6 claims, 0 differences)`.

**The D15 runtime rollback test** (FINAL-V2 6.4; ops/INSTALL.md "The D15 rollback test (design v2)"):
`run f, 2026-11-19T19:13:21Z-19:28:07Z, on cptg_d15r3f (restored from a fresh read-only dump of live, live-20261119T190653Z.dump, sha256 42f0d7552b96135a, migrated 0014 and 0015 with the candidate), candidate cpt-studio-test:394f1c1e3148 to previous cpt-studio:c2e53f8e7d33: RESULT 8 of 8 PASS (cpt-studio-d15-rollback@2). Assertion 7's record kinds each present, the three round r3 kinds among them (queued_question 1, question_run 4, question_released 2), the declined hold reported (0), never required; assertion 6 closed the interpret, appraise and question stages before the previous worker started; assertion 8 (U17) as declared (3 named, 1 reverted, the value saved again taking effect); assertion 2 records the U17 measurement (34 differences, D338, D339)`.

**The install counts** (`ops/rollback_check.py counts` on a migrated copy of a fresh read-only dump of live, as the app
phase reads them after its migrate; AMENDMENT-1 9.5; reported to the owner before the install):
`counts.json 2026-11-19T19:06:31Z, from live-20261119T190625Z.dump (sha256 0625befa0e7c19c5); v1_rows none (0 assessments, 0 inventories); size: bound 20,000 characters and 40 pages, without_inventory 86, over_chars 0, over_pages 0, unframed 1 (unframed_empty 1, unframed_unextracted 1: an extraction that failed or has not run), longest_chars 19,398; values 0 (first_install true); refused corti_sent 0, participant_sent 0 and corti_token 0, no newest date; a21 0; holds none standing (the interpreter none; Corti, Astra and Fable none); equal to 8adce6fb's and 57b48228's but the identity and time fields`.
The copy was dropped once read.

**Image precheck** (/home/claude/cpt-studio-ux-tools-20261105/precheck_image.py, which builds exactly as the installer's
image phase does, from the head, whose cpt-studio/ tree equals the revision's):
`2026-11-19T19:00:55Z; cpt-studio-precheck:394f1c1e3148 (sha256:82e4430d81a194b2...); the apt, user and requirements (pip) steps CACHED, COPY and collectstatic run; its sorted dpkg-query list 166 packages, sha256 prefix 500b6abda58b9a3e, equal to cpt-studio:c2e53f8e7d33's; its pip list 23 packages (8323f00f67c378bc), against c2e53f8e7d33's pypdf 6.21.2 to 6.21.4 and nothing else; user 10150:10150; the record byte-identical to 8adce6fb's and 57b48228's`.
The builder is not pruned between that measurement and the image phase: every preflight from D329 (5) until the image
phase (E0, F0 and J0 among them) declines the health check's builder-prune auto-fix and reports the reclaimable figure
only.

**Offline predictions** with this revision's own code (install-r3/predict_f.sh: the installer's one-shot scripts, run
in the candidate test image and in cpt-studio:c2e53f8e7d33 as the app phase and the switch-back run them, every provider
disabled, on throwaway databases restored from one read-only `pg_dump -Fc` of live on the test server gi4-cpt-test-pg,
127.0.0.1:55461, never the live port, dropped afterwards): `live-20261119T190625Z.dump (2026-11-19T19:06:25Z, sha256 0625befa0e7c19c5, 39 TABLE DATA entries); every output of install-r3/predict-r3i10 byte-identical to int9's`.
- **migrate:** applies `studio.0014_event_inventory` and `studio.0015_inventory_appraisal` and nothing else; the schema
  then reads 15 migrations, last 0015, the five tables empty and the five columns present.
- **UNRUNNABLE_STAGES:** none stuck. **V1_ROWS:** none. **INSTALL_COUNTS:** equal to the counts above.
- **RECOMPUTE_STATES:** `{"encounters": 86, "changed": {}}` with this revision
  (every encounter is legacy: FINAL.md 13) - and in cpt-studio:c2e53f8e7d33 on the migrated database (what a switch-back
  hands it) `{"changed": {}}`.
- **The control:** one sent run of a reviewed encounter planted 'unknown' turns that encounter to provider_unknown, so
  the measurement can see a change.
- `**the gi-context@4 comparison** (install/cmp/cmp_ctx.py with 394f1c1e3148's code, on a migrated restore of the D2 dump): 35 gi-context@4 contexts (31 current), differing under @5: current 0, not current 0; CONTROL ok (planted on context 96f52227); byte-identical to int9's (install-r3/cmp-r3i10)`.

The predictions hold only while the re-read baseline shows no live activity since the dump.

## Baseline (read-only, `2026-11-19T20:25:37Z`; re-read immediately before the commit that lands this declaration; this act's preflight receipt is binding)

Read with these commands, all read-only (the SQL is SELECT only, in a read-only transaction, through the database
container's own psql; counts and states only, never a document, response or credential):

    bash /home/claude/cpt-studio-completion-20261106/install/live_baseline.sh       # with PRE-INSTALL-CHECKLIST.md I2's rows appended
    bash /home/claude/cpt-studio-completion-20261106/install/usage_since.sh 2026-11-01T00:00:00Z
    bash scripts/check-cotenants.sh
    docker ps -a --filter label=org.quillmd.cpt-studio=1 --format '{{.Names}} {{.Image}} {{.Status}} {{.Ports}}'
    docker image inspect cpt-studio:c2e53f8e7d33 --format '{{.Id}} {{index .Config.Labels "org.opencontainers.image.revision"}}'

I2's rows cover migrations 0014 and 0015 (absent before the app phase), the reading jobs and runs, the new-path rows
and the decisions on current assessments. Expected shape before the app phase: studio_migrations 13, last
0013_completion_answer_binding; the five tables 0014 and 0015 create `absent`; the five columns `absent`; no job of kind
interpret, appraise or question; no provider run of purpose interpretation or appraisal; no assessment of a
`cpt-studio-events@` engine; no context of a `gemini-context@` version.

    # install-r3/live_baseline_r3.sh (install/live_baseline.sh with I2's rows), read-only
    read_at 2026-11-19T20:25:37Z
    transaction_read_only on
    encounters 86
    revisions 87
    source_files 80
    contexts 103
    routing_runs 113
    provider_runs 265
    provider_runs_sent 231
    assessments 180
    proposals 2477
    clarifications 340
    decisions 62
    decision_invalidations 2
    audit_events 1337
    reports 203
    jobs 619
    jobs_active 0
    users 5
    memberships 3
    workspaces 1
    login_attempts 107
    reference_sources 2
    reference_facts 34665
    studio_migrations 13
    studio_migration_last 0013_completion_answer_binding
    studio_providerexchange 241
    studio_toolcall 167
    studio_findingconfirmation 0
    studio_passagesource 3
    studio_referencepassage 62
    studio_memberanswer 29
    studio_memberanswerrevocation 6
    studio_operatorgrant 2
    studio_operatorrevocation 0
    studio_workerbeat 1
    column studio_clarification.answer_id present
    column studio_decision.modifiers present
    column studio_encounter.client_key present
    column studio_encountercontext.document_date present
    column studio_memberanswer.question present
    column studio_reportartifact.audience present
    member_answers_standing 23
    member_answers_by_value cannot_confirm 17
    member_answers_by_value not_documented 12
    run_participant astra independent failed 2
    run_participant astra independent not_sent 1
    run_participant astra independent succeeded 41
    run_participant astra peer_review succeeded 43
    run_participant fable independent succeeded 42
    run_participant fable peer_review failed 1
    run_participant fable peer_review succeeded 38
    credits_sum 4.398655999999999826
    usage_keys astra input_tokens,input_tokens_details,output_tokens,output_tokens_details,total_tokens
    usage_keys corti creditsConsumed
    usage_keys fable cache_creation,cache_creation_input_tokens,cache_read_input_tokens,inference_geo,input_tokens,output_tokens,output_tokens_details,service_tier,speed
    encounter_state extraction_failed 1
    encounter_state needs_clarification 45
    encounter_state no_codes 4
    encounter_state ready_for_review 8
    encounter_state reviewed 28
    run astra independent failed t f 2
    run astra independent not_sent f f 1
    run astra independent succeeded f t 7
    run astra independent succeeded t f 34
    run astra peer_review succeeded f t 2
    run astra peer_review succeeded t f 41
    run corti primary not_sent f f 4
    run corti primary succeeded f t 11
    run corti primary succeeded t f 80
    run corti second_review succeeded t f 2
    run fable independent succeeded f t 7
    run fable independent succeeded t f 35
    run fable peer_review failed t f 1
    run fable peer_review succeeded f t 2
    run fable peer_review succeeded t f 36
    job analyze succeeded 86
    job assess succeeded 180
    job astra cancelled 3
    job astra succeeded 42
    job astra_peer succeeded 43
    job extract succeeded 87
    job fable cancelled 4
    job fable succeeded 42
    job fable_peer cancelled 1
    job fable_peer succeeded 38
    job predict succeeded 91
    job review2 succeeded 2
    runs_unreconciled_unknown 0
    runs_reserved_or_sending 0
    last_audit assessment.created 2026-11-08T23:58:06Z 937651
    account demo-reviewer human t reviewer t
    account ops-agent agent t  
    account owner human t owner t
    account platform-operator human t  
    account review-agent agent t reviewer t
    reference_source cms-mue-practitioner-2026q4 cms-mue-practitioner 2026-Q4 15212 40a09bcd128dd18569a0a01e4fc4cffe
    reference_source cms-pfs-rvu26d cms-pfs RVU26D 19453 40a09bcd128dd18569a0a01e4fc4cffe
    assessments_by_engine cpt-studio-validation@10 57
    assessments_by_engine cpt-studio-validation@3 12
    assessments_by_engine cpt-studio-validation@4 46
    assessments_by_engine cpt-studio-validation@5 13
    assessments_by_engine cpt-studio-validation@6 15
    assessments_by_engine cpt-studio-validation@7 8
    assessments_by_engine cpt-studio-validation@8 6
    assessments_by_engine cpt-studio-validation@9 23
    contexts_by_version gi-context@1 12
    contexts_by_version gi-context@2 26
    contexts_by_version gi-context@3 19
    contexts_by_version gi-context@4 35
    contexts_by_version gi-context@5 11
    current_context_by_version gi-context@1 12
    current_context_by_version gi-context@2 24
    current_context_by_version gi-context@3 7
    current_context_by_version gi-context@4 31
    current_context_by_version gi-context@5 11
    current_context_by_version none 1
    routing_by_version gi-routing@10 11
    routing_by_version gi-routing@11 8
    routing_by_version gi-routing@12 11
    routing_by_version gi-routing@3 12
    routing_by_version gi-routing@4 38
    routing_by_version gi-routing@5 7
    routing_by_version gi-routing@6 7
    routing_by_version gi-routing@7 7
    routing_by_version gi-routing@9 12
    studio_eventinventory absent
    studio_interpreterhold absent
    studio_interpreterholdrelease absent
    studio_providerhold absent
    studio_providerholdrelease absent
    column studio_encountercontext.earlier_assessment_id absent
    column studio_assessment.interpretation absent
    column studio_eventinventory.appraisal_run_id absent
    column studio_assessment.event_inventory_id absent
    column studio_encountercontext.event_inventory_id absent
    assessments_new_path 0
    contexts_new_path 0
    decisions_on_current_assessments approve 51 31
    decisions_on_current_assessments reinstate 1 1
    decisions_on_current_assessments reject 6 6
    decisions_on_current_assessments revoke 2 1

    # install/usage_since.sh 2026-11-01T00:00:00Z
    read_at 2026-11-19T20:25:38Z on
    astra independent failed t f 2 credits=0 in=4004 cache_read=0 cache_write=0 out=214
    astra independent not_sent f f 1 credits=0 in=0 cache_read=0 cache_write=0 out=0
    astra independent succeeded f t 7 credits=0 in=0 cache_read=0 cache_write=0 out=0
    astra independent succeeded t f 34 credits=0 in=337814 cache_read=0 cache_write=0 out=74846
    astra peer_review succeeded f t 2 credits=0 in=0 cache_read=0 cache_write=0 out=0
    astra peer_review succeeded t f 41 credits=0 in=239856 cache_read=0 cache_write=0 out=20992
    corti primary not_sent f f 3 credits=0 in=0 cache_read=0 cache_write=0 out=0
    corti primary succeeded f t 7 credits=0 in=0 cache_read=0 cache_write=0 out=0
    corti primary succeeded t f 35 credits=2.113707999999999945 in=0 cache_read=0 cache_write=0 out=0
    corti second_review succeeded t f 1 credits=0.09915199999999999 in=0 cache_read=0 cache_write=0 out=0
    fable independent succeeded f t 7 credits=0 in=0 cache_read=0 cache_write=0 out=0
    fable independent succeeded t f 35 credits=0 in=914488 cache_read=0 cache_write=0 out=158513
    fable peer_review failed t f 1 credits=0 in=14101 cache_read=0 cache_write=0 out=648
    fable peer_review succeeded f t 2 credits=0 in=0 cache_read=0 cache_write=0 out=0
    fable peer_review succeeded t f 36 credits=0 in=878366 cache_read=0 cache_write=0 out=57687
    unknown_or_reserved 0

    # scripts/check-cotenants.sh
    HOST                   EXPECTED  OBSERVED
      🟢 quillmd.com          200       200
      🟢 www.quillmd.com      200       200
      🟢 app.quillmd.com      302       302
      🟢 admin.quillmd.com    503       503
      🟢 pro.quillmd.com      410       410
    🟢 every co-tenant answers its expected status (4 distinct codes — the probe discriminates).

    # docker ps -a --filter label=org.quillmd.cpt-studio=1; docker image inspect cpt-studio:c2e53f8e7d33
    cpt-studio-worker 02a99d53026f Up 4 days 8000/tcp
    cpt-studio-web 02a99d53026f Up 4 days (healthy) 127.0.0.1:9150->8000/tcp
    cpt-studio-db postgres:17.11-alpine Up 4 days 127.0.0.1:55451->5432/tcp
    sha256:02a99d53026f303cfeae5c5b64a1d9f18dec7a78c8306025427117c806b769a4 c2e53f8e7d33732d5badd4ce9b681f274eb5c471

## Expected changes, per phase

- **preflight:** none. One random ACME probe file is written and removed. Its receipt records the baseline the switch
  is verified against: the quillmd-cpt vhost as this installer's HTTPS stage for 9150 (sha256
  259b895dd1307e81b8fbcb5439874477daf71eba63c9b996b3bdfc572bf71a0c, the 9150 rendering
  `as the structure round's app receipt left it: app-20261108T225631452167Z.json switch.vhost_sha_after 259b895d..., from f816a27d... at its preflight; this act's preflight receipt must read 259b895d...`); 9150 held by cpt-studio-web
  alone and 9151 free; no cpt-studio-web-next; co-tenant routing and https://app.quillmd.com/health/; both participant
  sources present; whether an earlier /etc/cpt-studio/gemini.env exists (reported, never touched: AMENDMENT-2 1.11)
  as the preflight receipt reports it.
- **image:** a new local image cpt-studio:`e426c747c7b7`, built from git archive of the revision's cpt-studio/,
  labelled with the revision, user 10150 and CPT_STUDIO_RELEASE_SHA = the revision. Before it builds, the migration check
  accepts 0006 to 0015 and records why each passed. The build: `the apt, user and requirements (pip) steps CACHED, as C2 showed them`;
  the `dpkg-query` list identical to cpt-studio:c2e53f8e7d33's and pypdf 6.21.4, checked offline after the phase. The
  image's own checks: English OCR data, a working `pdftoppm`, `manage check`, the WSGI application loading as uid 10150
  on a read-only root, and the PDF gate (the synthetic guard PDF read through the image's extraction child as pypdf
  6.21.2 reads it, the compatibility layer accepting the installed 6.21.4). A build log showing apt ran, or pip
  installing anything the precheck did not show, is a stop before app.
- **Before app, outside the installer and read-only on the database** (install-r3/pre_app_f.sh): one `pg_dump -Fc` of the
  cptstudio database, through the database container's own pg_dump in a read-only transaction, to
  /home/claude/cpt-studio-install-20261023/pre-app-`e426c747c7b7`-UTC.dump (0600). Its `pg_restore --list` shows
  39 TABLE DATA entries (the schema is still c2e53f8e7d33's). It is kept until a separate, recorded decision removes it.
  **The gi-context@4 comparison, a CONDITIONAL step** (the last two installs' standing stop condition; checklist D4;
  pre_app_f.sh's CMP_CTX): `CMP_CTX=run: checklist D4 kept the comparison (0 differing, the control detected)`.
  With CMP_CTX=run, install/cmp/cmp_ctx.py runs with the act checkout's code on a restore of that dump on the test
  server gi4-cpt-test-pg (never the live port; the restore dropped afterwards) and must print "differing under @5:
  current 0, not current 0" and "CONTROL ok" - anything else is a stop before app. With CMP_CTX=skip and a recorded
  reason, it is not run and pre_app_f.sh prints that reason; nothing else replaces it.
  The baseline is re-read and equals the declared one (read_at and the last audit's age aside), with jobs_active 0, no
  provider run reserved or sending, no unreconciled unknown outcome, no reading job and no audit event newer than 10
  minutes. pre_app_f.sh's log ends "PRE-APP PASS" only when every step passed; act_f.sh's app phase requires it.
- **app (the blue/green switch; ops/INSTALL.md "Phases" and "What each phase checks"):**
  - before anything changes, the application's own loaders read, in the worker's mount layout and with no network: the
    Corti credentials; Astra's /etc/cpt-studio/openai-credentials.env; Fable's /etc/cpt-studio/anthropic-credentials.env;
    and the same file again through the interpreter's loader (studio.interpretation.fable_adapter.load_anthropic_credentials,
    which also proves the image imports the adapter) - format and permissions only;
  - **migrate (a one-shot) applies `studio.0014_event_inventory` and `studio.0015_inventory_appraisal` and nothing
    else**, while the c2e53f8e7d33 pair still serves;
  - the queue read finds 0 stages this revision cannot run;
  - design v2's reads, in this revision's image: **V1_ROWS finds no design v1 row** (live never held one);
    **INSTALL_COUNTS** records the counts above in the receipt's `install_counts` and its summary - printed, never a
    refusal - equal to counts.json, or each difference explained by a recorded member act;
  - the replacement plan reads **blue/green**: quillmd-cpt is this revision's HTTPS stage for 9150, the port the running
    web publishes; 9151 free; no -next or -previous left;
  - **S1** cpt-studio-web-next starts on 127.0.0.1:9151 and answers /health/ `{status ok, service cpt-studio, data_mode
    synthetic-only, database ok, release e426c747c7b73996d7f9fb4d598517aa0bc4d89a}`, and serves its sign-in page and every static file that page names;
    **S2** the old worker is parked (`docker stop --time 1800`; idle, about a second); **S3** the vhost's proxy_pass is
    switched 127.0.0.1:9150 to 127.0.0.1:9151 (sha256 259b895d... to
    f816a27de9e64af51d6a905484e22fdfc5f13a941a246931261bfc0df1e3ca65, the 9151 rendering, `deploy/nginx/` unchanged since
    c2e53f8e7d33 by the byte-identical list), `sudo -n /usr/sbin/nginx -t` clean with no new warning, `sudo -n
    /usr/bin/systemctl reload nginx` (graceful), and https://cpt.quillmd.com/health/ serves the revision with the
    co-tenants and app.quillmd.com as the preflight baseline found them; **S4** the new worker starts with Corti, Astra,
    Fable and the interpreter live (CPT_STUDIO_GEMINI_MODE=live, the historical name), binding the Corti, OpenAI and
    Anthropic credentials files read-only (the Anthropic file once), with the two question figures in its environment,
    and its startup sweep settles every RUNNING job (none: the old worker was idle and parked); **S5** the old web is
    drained (at least 130 s, until 10 quiet one-second samples, at most 600 s), stopped, parked as
    cpt-studio-web-previous, and the incoming web renamed cpt-studio-web; **S6** the stored list states are recomputed
    and the parked pair removed;
  - availability (the public /health/ every 0.5 s, from before S1 to the end): every sample 200; releases_seen
    c2e53f8e7d33732d5badd4ce9b681f274eb5c471 then the revision; non_200_count 0;
  - **states_recomputed `{"encounters": 86, "changed": {}}`** (predicted above). The receipt's
    `replaced` names the c2e53f8e7d33 pair (the switch-back's target);
  - the receipt's `interpreter`: mode live, given true, credentials_loaded true, worker_started_at = S4;
    `access_checks`: "not run (no --access-check)";
  - the API now asks for client build customer-2026-11-13: a page opened before the switch is answered 409
    client_outdated ("CPT Studio was updated. Reload this page to continue.") until reloaded (blue/green residual 3);
  - nothing is sent (below). No stage is queued and no context is remade: the contexts by version and the current
    contexts by version equal the pre-app reading;
  - counts after app: every count equals the pre-app reading, apart from a member's own use during the act (identified
    read-only by encounter and acting account, recorded, set aside), and: **studio_migrations 13 to 15, last
    0015_inventory_appraisal; studio_eventinventory, studio_interpreterhold, studio_interpreterholdrelease,
    studio_providerhold and studio_providerholdrelease present with 0 rows; the five columns present, every existing
    row NULL in each; no job of kind interpret, appraise or question**. studio_workerbeat stays one row named 'worker';
    its revision becomes the revision once the new worker beats.
- **After app, outside the installer and read-only (the receipt does not record the environment):** the worker's and
  the web's question figures and the worker's interpreter mode, read through a filtered template only - never the whole
  environment, which carries the env-file's secrets:

      docker inspect cpt-studio-worker cpt-studio-web --format '{{.Name}}{{range .Config.Env}}{{if eq (index (split . "=") 0) "CPT_STUDIO_QUESTION_DOCUMENT_CEILING_USD" "CPT_STUDIO_QUESTION_ROUND_CONCURRENCY" "CPT_STUDIO_QUESTION_PROVIDER_CAP_USD" "CPT_STUDIO_GEMINI_MODE"}} {{.}}{{end}}{{end}}'

  Expected: each container shows `CPT_STUDIO_QUESTION_DOCUMENT_CEILING_USD=25` and
  `CPT_STUDIO_QUESTION_ROUND_CONCURRENCY=4`, `CPT_STUDIO_GEMINI_MODE=live`, and no `CPT_STUDIO_QUESTION_PROVIDER_CAP_USD`.
- **passages:** the three committed files (git ls-tree of the revision, byte-identical to c2e53f8e7d33's), each imported
  in name order by `manage import_passages` after `manage migrate --check` passes: cms-claims-manual-100-04-ch12 "is
  already loaded with these 4 passages", cms-ncci-policy-manual-2026-ch6 16, cms-pfs-rvu26d-documentation 42 (the
  importer is idempotent). studio_passagesource 3 and studio_referencepassage 62 unchanged; every other count unchanged.
- **license-note:** the two reference sources already hold the corrected note (corrected 2026-11-03; LICENSE_NOTE_OLD
  and _NEW unchanged since): `{"rows": 2, "before": {"old": 0, "new": 2, "other": 0}, "after": {"old": 0, "new": 2,
  "other": 0}}`, no row changed, and it says so. Every other count unchanged.
- **verify:** no difference from the preflight baseline but the quillmd-cpt vhost's proxy_pass line (sha256 f816a27d...,
  as S3 wrote it); https://cpt.quillmd.com/health/ serves the revision under normal certificate verification, each
  security header once, and a request whose SNI is not cpt.quillmd.com is closed (444); nothing an app parks or starts is
  left; the web holds no bind and the worker only the three credentials files, read-only, at their worker paths. Its
  D22 one-shot (`manage interpretation_report --since S4 --self-test --json`, S4 the new worker's start, the interpreter disabled in the
  one-shot, nothing written or sent): the worker's interpreter mode live, as the app receipt installed it; the worker
  holding /etc/cpt-studio/anthropic-credentials.env read-only (shared with the live Fable participant); every check of
  ops/install.py's INTERPRETATION_SELF_TEST run and passed - the nine of int6, which round r3 does not extend: 'sentinel
  installed', 'deny set as pinned', 'positive control', 'positive control trips', 'model constant', 'no new-path legacy
  execution recorded', 'every new-path assessment carries its record', 'no sentinel trip', 'no legacy-engine
  assessment' `the same nine on 394f1c1e3148: ops/install.py:7322 INTERPRETATION_SELF_TEST, and install.py and interpretation/report.py byte-identical to int6's`;
  the retired kind as pinned; the interpreter hold "none standing". The filtered inspect above is read again after
  verify, with the same answer.
- Image cpt-studio:c2e53f8e7d33 is kept: it is the rollback image. Nothing removes any image.

## What the install sends

Nothing, to any provider. In ops/install.py the only code that sends to Corti, OpenAI or Anthropic is the opt-in
access check (`participant_access_check`, run only with `--access-check`), which this act does not run
(OPEN-QUESTIONS L3: the walk's first sends exercise the changed participant code, and D320 names the confirmation pair as
the only paid step before the install). Every other one-shot - the credential parses (`--network none`), migrate, the
queue read, V1_ROWS, INSTALL_COUNTS, RECOMPUTE_STATES, the passage importer, the licence-note correction and verify's D22
report - runs with Corti, both participants and the interpreter disabled. The interpreter has no access check of its
own. The new worker (S4) sends only for stages a member queues, and nothing is in flight at the switch.

Immediately before app: jobs_active 0; no provider run reserved or sending; no unreconciled unknown outcome; no audit
event newer than 10 minutes; no member activity during the act (`the owner was told at about 20:20Z on 2026-11-19 to stay off the site from then until he is told it is live (about 22:50Z); the site's last audit event is 2026-11-08T23:58:06Z`).
Checked after app, after passages, after license-note and after verify: provider runs, sent runs, provider exchanges,
tool calls, credits_sum and every token sum of the month's usage equal their pre-app reading; no provider run has a
created_at at or after the app receipt's started_at (install/usage_since.sh with that time prints no run).

The other traffic of the act is the installer's own: HEAD and GET probes of local nginx, cpt.quillmd.com,
https://app.quillmd.com/health/ and the co-tenants (scripts/check-cotenants.sh); the public /health/ every 0.5 s during
app; DNS lookups; the image build's package fetches if a step is not cached.

## After the install: the acceptance walk (ordinary use, not a phase)

FINAL-V2 9.9, as AMENDMENT-2 11.4 adapts it to Claude Fable 5.2 and round r3 adds the question stage. Ordinary use of
the installed service, after verify, first by the synthetic agent accounts review-agent (the customer page) and
ops-agent (the operator views) with ops/verify_browser.cjs, then by the owner (class c, D320 (7)).
- **Its inputs:** `the agent walk (K1), minimal as the 2026-11-16 directive asks: ops/verification's synthetic gi-01 (a Word document, an established office visit) and gi-02 (a PDF, an EGD with antral biopsy), rendered by ops/verification/generate.py and checked by hash before upload (`--only gi-01,gi-02`); then the owner's own documents of his choosing (D331: "i wanna walk live and try my docs"), at least one of them a realistic long note walked to the end`.
  Each sealed input is checked by hash before anything reads it.
- **How it is run:** one document at a time, `--allow-live-provider`, and `--deadline-seconds`
  `3,600`.
  verify_browser.cjs at int6 reads no question run in its provenance check and keys duplicates on provider, purpose and
  request sha256, so distinct question requests are never counted as duplicates `re-read on 394f1c1e3148: ops/verify_browser.cjs is byte-identical to int6's`.
- **What it sends:** real requests through the existing authorized accounts, with the product's own deadlines, Stop
  and duplicate prevention: per document, the interpreter's pass 1 and pass 2 (Anthropic, `claude-fable-5-2`, effort
  high, `max_tokens` 128,000), each question request (effort max, `max_tokens` 128,000, 1,408 s; at most 4 at once,
  within the 25 dollar ceiling), Corti's coding request, Astra's and Fable 5.1's first readings and peer reviews, and a
  bounded second review only where one is owed and asked for. Usage and cost are recorded from the provider runs it
  creates and reported per document.
- **Cost and time per document** (re-stated from the confirmation pair before the walk):

  | | short note | realistic long note (about 2 pages) | 19.4 KB note (5 pages; stress material, D278) |
  |---|---|---|---|
  | fact passes, effort high | $1.03-1.87 as production pays (F3all, AMENDMENT-2 7.1); 110-286 s | pairs 1-4: $3.30-4.75 per pair with its short note | measured $6.55-7.10 (a cache write), $11.06 at the worst (both passes cut at 128,000) |
  | question stage, effort max | r3-probe-1 (one request, four calibration items): $2.246928, 55,219 output tokens at 102.64 tok/s, about 538 s | r3-probe-2 (three requests, four items each): $11.250816; 1,049 / 691 / 921 s, so about 1,049 s run concurrently | at most 25 dollars of reserved worst case (D326) |
  | measured on the built code | `S05, an ERCP: $1.91, 288 s, no question` | `L05, an EGD: $4.81, about 1,010 s (fact passes 562 s; one question request 448.5 s)` | not measured (D278) |

  Corti's credits and the participants' tokens are added as today. The walk's total is `about $5 for the agent walk (two short synthetic documents, at about $1-3 each as the pair measured them) plus the owner's own documents at about $2-15 each`,
  against the Anthropic account's remaining month `which the owner manages himself (D331: "dont worry about the api budget ill take care of it by my self"); the month's recorded usage before the walk is about $108.40 (the harness ledgers $78.40 after the pair, and the site's $30)`.
- **What it checks** (9.9, adapted):
  1. upload of PDF and Word documents through actual ingestion, on the installed site;
  2. progress shown truthfully, both fact passes and the question stage as steps named by function, never by provider;
  3. review: exactly one item per held code; READY codes approvable with the labelled synthetic approval and the
     acknowledgement;
  4. save and reload;
  5. the downloaded reports equal the saved decisions, with no provider or model name in any form (`claude-fable-5-2`,
     "Claude Fable 5.2", joined and underscored forms; the customer denylist's three readers), and no question, proof or
     answer named;
  6. operator evidence: `legacy_calls` 0 and `retired_calls` 0; pass 1, pass 2 and every question run with provider
     `anthropic`, requested and returned model `claude-fable-5-2`, adapter `anthropic-messages@cptstudio-interp-1`; the
     fact passes at effort high and each question request at effort max with `max_tokens` 128,000 (from the stored
     request bodies); the versions `gemini-events@3/appraisal@2`, `gemini-inventory@3`, `cpt-studio-events@3`; the cache
     and thinking tokens in the report; each question request inside 1,408 s; each released code's witness and located
     spans, each unestablished question's reason, each request's calibration, health and reserved worst case, and any
     round the ceiling refused, in the operator report; no released retry counted as a duplicate paid request;
  7. availability: the app phase's record (every sample 200). Rollback is evidenced by the D15 runtime test on a test
     instance before the install (attached), never by switching the live site back;
  8. the report: the installed revision, the remaining defects, the incorrect approvals, the unnecessary holds, the
     usage and the actual download results; at least one long note walked to the end with its latency, or shown
     truthfully as a reading that reached its limit.
- **The owner's walk** (class c): the owner reviews documents of his choosing on the installed site; a document is right
  or wrong to the doctor reading it, and no gate substitutes for it.
- **What it claims:** every agent approval is labelled an agent-executed synthetic review; no human clinical review is
  claimed. A walk failure is reported as the finding it is, not hidden.

## Must not change

- Every existing encounter's assessments, proposals, clarifications, decisions, member answers, reports and audit rows.
  No phase queues a stage, remakes a context or re-assesses anything: the contexts by version and the current contexts
  by version equal the pre-app reading after app, passages, license-note and verify.
- Every provider run, exchange and tool call; the month's provider usage. No question run exists after the act.
- The reference sources (cms-pfs-rvu26d, cms-mue-practitioner-2026q4), their licence notes and their 34,665 facts; the
  3 passage sources and 62 passages.
- Users, memberships, workspaces, operator grants and revocations; the credentials files under /etc/cpt-studio/ and
  /etc/cpt-studio-provider-sources/, their owners and modes (an earlier gemini.env, if present, untouched).
- cpt-studio-db: the same container, image, port and restart policy, running throughout; volumes cpt-studio-pg and
  cpt-studio-files; network cpt-studio-net.
- nginx.conf, the enabled links and every other sites-available file; the Let's Encrypt lineages.
- app.quillmd.com, quillmd.com and every co-tenant's status (scripts/check-cotenants.sh before and after).
- The live database's schema beyond migrations 0014 and 0015's five tables, five columns and their indexes and
  constraints.

## Validation per phase

Each phase's own checks (ops/INSTALL.md) must pass and its receipt must say ok, with tree.mode
descendant-without-runtime-change, tree.head the merge commit that lands this declaration, door.declaration this file,
door.declaration_commit the commit that last touched it and door.declaration_sha256 this file's. Then, before the next
phase, the judgment is written into install-r3/judgment-fable-r3.md (the structure round's install/judgment-structure.md
form) with the receipt names and the times from the receipts:
- preflight: every check passes; the vhost, ports, sources and baseline as above;
- image: the migration verdicts (0006-0015 safe), the build steps and the `dpkg-query` and pip lists as declared,
  pypdf 6.21.4, the PDF gate, user 10150, the revision label and release;
- app: credentials parsed; migrate applied exactly 0014 and 0015; no unrunnable stage; no v1 row; install_counts as
  measured; blue/green 9150 to 9151 with the vhost sha256 before and after as declared; availability and releases_seen;
  the drain; states_recomputed; `replaced`; the interpreter record; no leftover container; then the read-only counts,
  usage since the app's start, and the filtered inspect of the two figures and the interpreter mode;
- passages and license-note: the answers above, and nothing else moved;
- verify: the differences, health, headers, binds, the D22 self-test as declared, and the filtered inspect again.

## Rollback per phase, and its limits

- preflight, image, passages, license-note and verify change nothing that serves. A failed image leaves at most an
  unused image. passages and license-note are idempotent: a rerun completes them.
- app fails before S3 (a credentials parse, migrate, the queue read, a v1 row, the incoming web's health or smoke): the
  c2e53f8e7d33 web never stopped serving; the incoming web is removed and the old worker restarted. Migrations 0014 and
  0015, once applied, stay: they are additive, the c2e53f8e7d33 pair never reads them, and it runs on that schema.
- app fails at or after S3: exactly as ops/INSTALL.md and the receipt set out (the vhost bytes put back, the stages the
  new pair queued closed - interpret, appraise and question among them, as failed and never resumable on the old web -
  the list states put back, or the new pair left serving with its worker held while a person decides). An installer
  killed outright inside S3 (`kill -9`, or the door's ceiling) writes no receipt and runs no undo: ops/INSTALL.md,
  Recovery notes. Each failure is a stop: the pair that is running serves while it is judged, and no remedy is taken
  without a decision recorded under this declaration.
- **After a successful app, the way back is switch-back to the c2e53f8e7d33 pair** (the receipt's `replaced`), without
  interruption: `preflight` again, then `--phase switch-back --provider-mode live --astra-mode live --fable-mode live
  --authorization-ref docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`, with no `--interpreter-mode` (c2e53f8e7d33
  has no interpreter; the ruling file is tracked at c2e53f8e7d33), run under this declaration with this revision's
  installer, by a decision recorded under it. install-r3/act_f.sh enforces the order: it refuses switch-back unless a
  preflight log written after the app log (a TAGged act-f-preflight log newer than act-f-app.log) ended exit 0 (D329
  (6)). Its web returns on 9150. Its limits, stated now (FINAL-V2 6.4; AMENDMENT-1 9.4; ops/INSTALL.md "Switching
  back"):
  - it refuses, starting and stopping nothing, while this revision recorded what the older revision would act on or show
    wrongly - UNDO_HAZARDS, read against c2e53f8e7d33, which reads the rest (switch_back_hazards drops every reason the
    target revision reads: ops/install.py target_reads and switch_back_hazards, :4029-4067 at int6). For this target
    ONLY FOUR reasons refuse (D329 (6)): an unreconciled unknown outcome, a failed request it could make again, a
    member's date conflict, and a reviewer's reinstatement on a new-path assessment, each on an encounter with a record
    made since this revision's pair. They are cleared on this revision's web first (reconcile, Resume, an addendum,
    "Undo decision"), or this revision stays installed. The other reasons never refuse this switch-back, because
    c2e53f8e7d33 reads them: it runs review2, astra and fable (so a code only a second review or a harness participant
    proposed, and a second review refused or left unread), and its models have MemberAnswer with
    jobs.recompute_after_answers and Decision.modifiers (so a member's standing answer and a chosen modifier). The walk's
    agent approvals with a modifier and its member answers are therefore NOT hazards for this switch-back, and nothing
    of the walk is undone before one;
  - this revision's worker is parked with its 1,800 s stop timeout: a question round in flight is finished within it (a
    stopping worker starts no further wave; the later wave's reservations are released and their requests stay owed);
    then every open interpret, appraise and question stage is closed as failed (CLOSE_STAGES reads the previous worker's
    own jobs.STAGES; the note counts them as `reading_closed`), the run it had in flight settled (sending: unknown;
    reserved: not sent); no Resume is offered there;
  - the old image never reads the new rows. A v2 assessment keeps SERVICES_STUB in services and INVENTORY_PROBLEMS in
    completeness, so the old image reads it fail-closed: statuses as stored, a held code held and a READY code -
    released by a proven question answer included - approvable, as on this revision;
  - **D59's limit stands:** a reinstatement made ON the old web on a new-path assessment can leave the diagnostic base
    code approvable beside the reinstated therapeutic code (a reinstated 45385 beside 45378, which this revision holds),
    and its approved export would bill both. The switch-back note names the exposed encounters (`reinstatable`); they
    are re-checked on this revision before anyone reviews them on the old web;
  - pending updates are named (`update_pending`), never a refusal: a save still pending before analyze has its
    unapplied values reverted (one `context.rollback_reverted` audit row each; its member saves the change again on the
    old web); one pending after analyze shows the legacy codes there, the approved export blocked; an A21 encounter reads
    as an outcome being confirmed;
  - legacy decisions a v2 update cleared stay cleared (their invalidation rows stay); decisions recorded on v2
    assessments are never rewritten; the customer page returns to the 2026-11-03 client build (pages opened on this
    revision are asked to reload);
  - this revision's installer starts the previous pair with the two question figures in its environment, which
    c2e53f8e7d33's settings never read;
  - migrations are not reversed: the five tables and five columns stay; the old image ignores them;
  - on the old pair the interpreter is gone: uploads are read by the legacy reader again, with its known open findings.
- The pre-app dump is the only data-level way back; restoring it deletes every row made after it, which is a separate
  declared act (class d: deletion of data). Image cpt-studio:c2e53f8e7d33 and its receipts are kept.

## What is not claimed

Functional completion on the installed site is judged by verify and the acceptance walk. Clinical accuracy and billing
readiness are not claimed, and this act establishes neither.
- D277 gave up the statistical acceptance bar: the acceptance run A and D1-D3 were not run. The evidence is the free
  replays of every recording through the built engine, pairs 1-4, the r3 probe (r3-probe-1 and r3-probe-2), the
  adversarial passes over int4 to int9 and the focused refutation of int10's repair, with every reproduced serious
  finding repaired until the owner's D349, the one confirmation pair, the D15 runtime test and the walk.
- **THE OWNER'S ACCEPTED GAP (D348, D349) - NOT fail-closed.** The confirmation pair's score (ii) was 6: a code
  PROPOSED for a note can show READY when it is the wrong code of its family - an esophagoscopy code (43197-43229) on
  a note whose scope reached the duodenum (an EGD), or a balloon code of 30 mm or larger (43214, 43233) for a smaller
  balloon - because the esophagoscopy rows accept any reached point and no row reads a balloon's size, the
  transnasal route or a retrograde dilation. By the pre-registered pass rule that stopped the install. The owner
  overrode it on 2026-11-19 (answering whether to fix first or install now and fix later), verbatim: "Bro i dont want
  to have rule to block our fable decesion since he is the best stop patching and rules delete the rules and anythign
  is block our things let fable completly judge for codes through me to the live aasp". Read (D349): go live now on
  this revision; no more patch rounds; Fable judging the codes completely is the next change, scoped with him before
  it is built. Recorded with it, also not fail-closed and also accepted under D349 (2): L10R-1 (an unappraised through
  naming a non-stoma entry lets a colonic-stoma route take another established stoma; 44389 and 44407 READY in the final
  check's 100 constructed cases of that shape, 0 with the through supported) and the last final check's finding 2 (a hepaticojejunal or
  esophagogastric join filed with organ "pouch" releases lower-GI codes in a contrived merged filing); both were
  present on int9 too.
- **The guard's hold costs, which the owner is told in plain words before his walk** (D336 (2), D340 Q2, D342 (2), D343
  Q4-Q5, D345, D346 Q1; fail-safe: the code goes to the coder, never a wrong code): a stoma or ileal pouch anywhere in the history,
  reversed ones included, holds the per-anus colonoscopy codes even when the note says the scope went in through the
  anus (the approach has no control yet); a non-GI surgical history recorded as an anatomy change (heart bypass, joint
  replacement, hernia mesh, C-section, transplant); upper-GI re-plumbing (gastric bypass, Whipple, fundoplication);
  anal-canal surgery beside a per-anus code; an anastomosis, stoma or pouch whose type the reader cannot confirm; a
  scope reaching a place the history says was removed (the cecum after a right hemicolectomy, the rectum after a low
  anterior resection, the appendiceal orifice after an appendectomy); a history marked patient-reported or hedged; a
  stoma or pouch written into a joined bowel's description. The confirmation pair's unnecessary hold (43249 beside
  43248, coding_rule:competing_codes) is of the same direction.
- **Known limits recorded, not built** (each fail-closed unless said otherwise):
  - **The trap's polarity** (D325 (5), R3C-L1-2, medium): one negative calibration item per request (D319) cannot tell
    a model that affirms every positive sentence and rejects every negative one; with hollow quotes such a model would
    release a positive claim. Fable showed no such bias (every keyed answer and all 16 calibration items of the probe
    right), and the release guards stand - the exact negation, and a located proof (stronger since D325 (4)). The
    after-go-live remedy for model bias in general is a Fable double-check of every READY code, the owner's question of
    2026-11-18; it is not part of this install.
  - **D325 (6) Q2:** Q-F4 is not built - a session an answer rules out stays possible in coverage.sessions_of,
    combination and classes. A lost release, never a wrong one.
  - **The silent-anastomosis residual** (D328 addendum, rules4 Q3): at int6 an anastomosis whose subtype AND joins are
    both silent stayed as int6 decided it, so a colonoscopy code could read READY where the record never says a colon
    remains (constructed notes only; no development document files one). D330 (1) rules that the lower-GI path guard
    closes it - such an entry matches no row of the ruled harmless set, so the code holds
    `as D330 (1) rules; no final check since (rounds 5-7) recorded it open on 394f1c1e3148`.
  - D328 (1): there is no rectum-absent arm. Since D330 (1), a sigmoidoscopy after a low anterior resection reads READY
    only where each of its anatomy entries is the route's own entry or matches a row of the ruled harmless set;
    otherwise it holds for the coder.
  - **D330's recorded limits** (each a hold for the coder, never a false READY):
    - (1) (d), R5R-5, fail-safe and not built: a stoma's organ is never claimed or askable, so D324 (5)'s exemption for a
      gastrostomy (or a tracheostomy) cannot fire, and a lower-GI code on a note that names ANY stoma, with the approach
      silent, holds for the coder (int6 already did this for the colonoscopy family). The remedy, after go-live, is a
      pass-2 claim on the stoma's organ or an approach question template; reading pass 1's unverified organ in the
      release direction is refused. The owner is told in plain words (OWNER-ITEMS item 13).
    - R5R-3: a Kock pouch entered through its continent stoma - 44382 is held, and 44386's hold is a recorded limit, not
      built: the pouch codes go to the coder.
    - Any post-surgical lower-GI anatomy outside the ruled harmless set holds: an omission from the set costs a hold,
      never a false READY.
    - (3): the pairs lane's Q1 (exclusive(records, refused, R_base) in jobs.py) is not adopted; RP-3 and Q3 (a paid
      round asked after an earlier answer held the pair, in a rare shape) are recorded as cost, not built.
  - D324 (2)'s hold side: two negations of one slot hold each other (ASK2-3); D327 (2) reads a rival's "contradicted"
    with any qualifier, as settle reads a value's own control.
  - The lows: D324 (12) and its addendum (L7-A4), D325 (7) (findings2.json's lows: L3P-1, L7P2-1, L3P-3, L3P-4, L3P-5,
    L5c-1, L5c-2, L5-2-still, L5-1-replay-still, L5-3-still, L6B-3, L6B-4, L6B-5, L8-1, L8-2), D328's lows (L3R-1 and
    L6C-4 downgraded; L4, L5 and L8 lenses' lows) `and rounds 4-7's recorded lows and hold costs (D330-D346): L8R7-1 to L8R7-5 and FC2 (fail-safe holds); L10R-1 and the last final check's lows are NOT fail-closed and are listed under the owner's accepted gap above` - every one fail-closed or
    tooling.
- Round r3 does not build Q-GROUP, Q-KIND, F9, U2, A3's narrowing or the CAUSE row's wrapper: those holds stay with the
  coder. Showing the located proof to a reviewer is the owner's eye (D307 Q5, D308 Q-G), not built.
- The question requests run below the 110 tokens-per-second floor (measured 101-104): a measure, never a hold (D310
  (9)). A question request whose stream runs past its 1,408 s deadline is cut and recorded UNKNOWN (its bytes kept, its
  cost unknown: a reconcile, and an encounter-wide block until then); the longest measured took 1,049 s and used 83% of
  128,000 tokens (r3-probe-2).
- A round over the 25 dollar ceiling is not sent: its codes go to the coder, which is the designed behaviour (D326);
  how often it binds on an ordinary long note is measured by the confirmation pair and the walk (D328 addendum, harness
  Q5: the recorded long note's round 1 reserved about $16.28 of the $25).
- A decline holds the whole installation until an operator releases it, and blocks its identical request after the
  release (D275; D279 (6)).
- The installed release's recorded residuals no longer apply on the new path but stand on any legacy encounter not yet
  read again and on the rollback image.
- NCCI PTP stays unconnected: modifiers are considerations only (limitation L2). D3 to D5 and decision (m) stay open.
- Data at rest is on the unencrypted root disk and the database has no scheduled backup (ops/INSTALL.md "Known limits"):
  acceptable only because the service is synthetic-only.
- Blue/green residuals (ops/INSTALL.md "Known limits", 1-13): an upload an old nginx worker still held after the drain
  can answer 503; a page from before the switch may ask for an old-hash static file or be asked to reload; processing
  pauses for the old worker's remaining stage time plus the switch; `systemctl reload nginx` is host-global; the vhost
  sha256 alternates with the port.

## Stop conditions

Any of these stops the act:
- a difference in the byte-identical list, or a migration other than 0014 and 0015;
- before app, pre_app_f.sh's log not ending "PRE-APP PASS": a pre-app dump whose `pg_restore --list` is not 39 TABLE DATA
  entries; where checklist D4 kept the gi-context@4 comparison (CMP_CTX=run), any encounter differing under @5 or the
  control not detected on the dump's restore; a re-read baseline differing from the declared one (read_at and the last
  audit's age aside); jobs_active not 0, a provider run reserved or sending, an unreconciled unknown outcome, a reading
  job, or an audit event newer than 10 minutes;
- an undeclared count movement;
- a provider run, exchange or tool call created by any phase, or a provider or interpreter hold set during the act;
- a job queued (an interpret, appraise or question job among them), or a context remade, by app, passages,
  license-note or verify;
- V1_ROWS naming any encounter; install_counts differing from the measured counts with no recorded member act to
  explain it (judged before the next phase);
- a build log showing apt ran, or pip installing anything the precheck did not show; the PDF gate or the migration
  check refusing;
- a non-200 availability sample, or a releases_seen other than the two declared;
- states_recomputed naming any changed encounter;
- a leftover *-previous or *-next container after app;
- the app receipt's `interpreter` other than mode live, given true, credentials_loaded true;
- a worker or web environment whose question figures are not exactly 25 and 4, or that carries a
  CPT_STUDIO_QUESTION_PROVIDER_CAP_USD, or a worker interpreter mode other than live (the filtered inspect);
- passages importing anything new, or license-note changing a row;
- verify reporting any difference but the proxy_pass line, a worker interpreter mode other than live, a worker not
  holding the shared key read-only or holding any other bind, or a D22 self-test check failed or not run;
- a phase ended by the door's watchdog (exit 124), judged first against this declaration before anything else runs;
- co-tenant routing or app.quillmd.com differing from the preflight baseline.

## Attached: the D15 transcript

`docs/foundation/mutations/20261119-cpt-studio-fable-interpreter-install-d15/, beside this file: D15-SUMMARY.txt (sha256 4aa8691e3c386ac75f7c4aec86bd78bd8748e012177eed999c89d1f5cd6699a7), d15.json (5912a0e8d352c3e7183cfc0beaf2e5d5572c03e2c1c5a25b0a7e8d3804553d3c) and counts.json (943d1b85ef6b4f2978ccfa9d2b921a07e02091c7bc39b184c72ad27c073b620a, the install counts of D2). The run's arguments: database cptg_d15r3f on gi4-cpt-test-pg, candidate cpt-studio-test:394f1c1e3148, previous cpt-studio:c2e53f8e7d33, port 9174, since 2026-11-19T19:07:12+00:00, the declared JSON declared-f.json (sha256 2f389279f748ff3d83bd92599f56bba16d7f61eb84830026cfbc0e86dea4152f), no resume encounter (its http block's resume names none). RESULT: "D15 rollback runtime test (cpt-studio-d15-rollback@2) - PASS", 8 of 8, 2026-11-19T19:13:21Z-19:28:07Z`.
