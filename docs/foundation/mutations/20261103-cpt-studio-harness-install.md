# Prospective declaration: CPT Studio GI coding harness at cpt.quillmd.com (80df1831d168 to 41e03656df617d5fab4a551ba7a0d7aea5ca3380): round 4, harness@1 and harness@2, with Astra and Fable live

Authority: the owner's directive of 2026-11-01 ("Implement and install on cpt.quillmd.com a harness in which Corti plus
independent Astra and Fable reviews of each uploaded document are validated ...") and his directive of 2026-11-02 ("If
access passes, update the checklist and continue implementation, installation on cpt.quillmd.com, and the complete live
acceptance workflow under the existing authorization. Keep QuillMD and unrelated services unchanged."), both recorded
verbatim in docs/foundation/rulings/2026-10-23-cpt-studio-gi.md with this session's interpretations (on receipt; after
the second refutation; after the third refutation). The round-4 work it carries is the owner's directive of 2026-10-31.
Session cd048041 is the single integration and deployment owner (it took over from 1bf3b49c at the owner's choice,
2026-11-02 00:40Z). The install is governed by the 2026-10-23 directive cited in
docs/foundation/mutations/20261023-cpt-studio-install.md: a protected synthetic demonstration, provider credentials
server-side, app.quillmd.com and unrelated services preserved. CPT Studio stays standalone: no QuillMD source, database,
users, files, units or environment are shared, promoted or edited. No purchase, agreement, new ACME account, new key or
payment change is part of this act; the participant keys were placed by the owner and copied by the installer's secrets
phase under docs/foundation/mutations/20261102-cpt-studio-participant-credentials.md (receipts
/home/claude/cpt-studio-install-20261102), which this act does not repeat. D3 to D5 stay open as recorded; nothing here
accepts an agreement or infers a licensing permission.

Revision to install: 41e03656df617d5fab4a551ba7a0d7aea5ca3380, the merge commit of PR #1459 (branch feat/cpt-studio-harness-20261101); image tag
cpt-studio:41e03656df61. Its citation, on 41e03656df617d5fab4a551ba7a0d7aea5ca3380: secrets-scan (TruffleHog) succeeded, run 41680283049; CI (Fresh application tests, Marketing build, Private browser and accessibility) succeeded, run 41680282951; cpt-studio ran every step - Django 5,278 tests, ops 313 (1 skipped), ops/verification 37 and node 91 passed - and failed only its dependency audit on pypdf 6.21.2 (seven advisories, CVE-2026-119203 to CVE-2026-119209), run 41680283029. It replaces the live revision
80df1831d168c4ee83d83c37bac9860690986cf3, installed 2026-10-31 under docs/foundation/mutations/20261031-cpt-studio-gi3-upgrade.md,
which runs image cpt-studio:80df1831d168 (sha256:88544c7cd33f), web 1f603dddd9aa, worker 083b9af8657a and database
1c5498b3aacc. That declaration and its receipts stay as they are.

Execute each install phase separately through scripts/run-ruled-mutation.sh with
`python3 -B cpt-studio/ops/install.py --phase <phase> --revision 41e03656df617d5fab4a551ba7a0d7aea5ca3380 --receipts /home/claude/cpt-studio-install-20261023`,
in this order: preflight, image, app (with `--provider-mode live --astra-mode live --fable-mode live --authorization-ref
docs/foundation/rulings/2026-10-23-cpt-studio-gi.md --access-check`), passages, license-note, verify. Run them from a
clean, detached checkout of the merge commit that lands this declaration: a descendant of the revision that changes
nothing under cpt-studio/, scripts/run-ruled-mutation.sh or scripts/lib/. Read each receipt before the next phase. The
receipts directory is the live install's own (it holds the live vhost's receipts, ops/INSTALL.md "Reinstalling a new
revision"); no receipt there is changed: each file is created once.

Not run: secrets (done this morning; the app phase checks the three credential files itself), db, reference,
provision, http-vhost, cert and https-vhost, whose objects exist. Between 80df1831d168 and 41e03656df617d5fab4a551ba7a0d7aea5ca3380 these are
byte-identical: cpt-studio/deploy/ (Dockerfile, entrypoint, gunicorn, nginx templates, .dockerignore),
cpt-studio/requirements.txt, requirements.in and requirements-dev.txt, scripts/run-ruled-mutation.sh, scripts/lib/ and
scripts/check-cotenants.sh. So the image recipe, its pinned dependencies and the vhost are those that installed
80df1831d168. The installer (cpt-studio/ops/install.py, ops/INSTALL.md) and cpt-studio/cptstudio/ (settings) DIFFER:
this act runs the harness revision's installer, which adds the participant credentials, the participant modes and the
access check to the app phase, the passages and license-note phases, the peer stage kinds to its undo, and the
settings STUDIO_OFFER_CONFIRMATIONS = False (HARNESS.md 12.10). Before preflight the operator runs, in the act's
checkout, `git diff --quiet 80df1831d168c4ee83d83c37bac9860690986cf3 HEAD -- scripts/check-cotenants.sh
cpt-studio/deploy cpt-studio/requirements.txt`; any difference is a stop.

## Delta shipped (80df1831d168 to 41e03656df617d5fab4a551ba7a0d7aea5ca3380)

PR #1459. Its body, cpt-studio/HARNESS.md (sections 11 and 12; 12.9 to 12.20 record refutation rounds 2 to 12) and
CPT-HARNESS-CHECKLIST.md list every change, measurement and limit. For this act:

- Migrations 0007 and 0008 (studio_migrations 6 to 8): 0007 adds Assessment.participants and Assessment.retrieval
  (JSON lists, default '[]'), ProviderRun.endpoint, requested_model, returned_model and response_id (strings, default
  ''), each with a database default, and creates PassageSource and ReferencePassage; 0008 creates ProviderExchange,
  ToolCall and FindingConfirmation with two constraints. No data migration: existing rows gain only those defaults.
- Reader versions: gi-context@3 to @4, gi-routing@4 to @5, gi-services@1 to @2, cpt-studio-validation@4 to @5;
  gi-profiles@3 and cpt-studio-ingest@3 unchanged; harness-reading@2 new. New readings apply to new uploads, addenda,
  member saves and the stages they queue. No existing encounter is re-assessed or re-sent by the install, and every
  stored list state recomputes unchanged (predicted below).
- From the app phase on, Astra (OpenAI gpt-6-astra) and Fable (Anthropic claude-fable-5-1) are live: every new upload,
  and every member action that queues stages, runs Corti, then Astra's and Fable's independent readings with their CMS
  tool loops, then their peer reviews and the second assessment, each a paid request (HARNESS.md 2, 11). An existing
  encounter runs them only if a member queues its stages again.
- No reviewer confirmation is offered (HARNESS.md 12.10, D7): the confirmation endpoint refuses and records nothing,
  and no candidate or located passage is served for an open question (D8). The reports print a participant's peer
  answer only as its claim that the document does or does not settle the question, with the passages it located, and
  never a value (D10).
- In this release a participant's code is never a proposal (D14, HARNESS.md 12.14). A code only Astra or Fable gave
  is listed as an alternative with CPT Studio's own reason. Participants never make a code ready, never count as
  covering a documented act, never make another code included and never clear an unresolved item. Corti's proposals
  are assessed exactly as with no participant configured.
- The installed readers' false READY on Corti's own selections (HARNESS.md 12.14's table: failed acts, denials, another
  procedure's sentence, pathology addenda, indications and history lines; and 12.20's attached prior EGD report, whose
  title Corti cites for 43235) is unchanged by this act (I1): it neither adds nor removes that exposure. Its repair is
  a separate, later change.
- A diagnostic base not held again after a reviewer reinstates a therapeutic code of its family (HARNESS.md 12.18,
  round 10's retrieval-1, blocking) is unchanged by this act: `review._actions` is byte-identical on 80df1831d168 and
  41e03656df617d5fab4a551ba7a0d7aea5ca3380. Its repair, a review-layer base hold, is a separate, later change. The walk below reinstates nothing.
- pypdf stays 6.21.2 and the reader is byte-identical, so uploads read as installed reads them. Its seven known
  advisories (CVE-2026-119203 to CVE-2026-119209) stand, and the PR's cpt-studio job's pip-audit step is red on them.
  That is stated here, not waived: interpretation 68 stays the owner's open question.

## Baseline (read-only, 2026-11-03T17:03:33Z; re-read immediately before the commit that lands this declaration; this act's preflight receipt is binding)

Read 2026-11-03T17:03:33Z by $S4/install-harness/live_baseline.sh (SELECT only, in a read-only transaction, through
the database container's own psql; output kept 0600 as baseline-20261103T170333Z.txt):
- encounters 43, revisions 43, source_files 38, contexts 57, routing_runs 50, provider_runs 51 (46 sent),
  assessments 58 (12 by cpt-studio-validation@3, 46 by @4), proposals 712, clarifications 69, decisions 25,
  decision_invalidations 0, audit_events 393, reports 110, jobs 194, jobs_active 0, users 3, memberships 3,
  workspaces 1, login_attempts 41, reference_sources 2, reference_facts 34665; studio_migrations 6 (last
  0006_services_completeness_second_review); the five harness tables absent; credits_sum 2.185796.
- encounter states: needs_clarification 24, no_codes 4, ready_for_review 3, reviewed 12.
- runs (provider, purpose, state, sent, unknown-reconciled, count): corti primary not_sent f f 1; corti primary
  succeeded f t 4; corti primary succeeded t f 45; corti second_review succeeded t f 1. Unreconciled unknown 0;
  reserved or sending 0.
- jobs, all succeeded: analyze 43, assess 58, extract 43, predict 49, review2 1.
- last audit event: report.generated 2026-10-31T13:03:11Z.
- accounts: demo-reviewer (human, reviewer), owner (human, owner), review-agent (agent, reviewer), each active.
- reference sources: cms-mue-practitioner-2026q4 (15,212 facts) and cms-pfs-rvu26d (19,453), each with the licence
  note md5 7d5648201e426fff664b4002f5106fc4 (LICENSE_NOTE_OLD).
- Against the 2026-11-02T13:02:15Z reading: login_attempts 38 to 41, and nothing else moved.
- Re-read 2026-11-03T17:30:30Z, immediately before the commit that lands this declaration (baseline-20261103T173030Z.txt): identical; only the read time moved.

## Expected changes, per phase

- preflight: none. One random ACME probe file is written and removed.
- image: a new local image cpt-studio:41e03656df61, built from git archive of 41e03656df617d5fab4a551ba7a0d7aea5ca3380 cpt-studio/, labelled with the revision,
  user 10150, CPT_STUDIO_RELEASE_SHA=41e03656df617d5fab4a551ba7a0d7aea5ca3380. Steps 2 to 6 (apt, the user, WORKDIR, requirements, pip) are expected CACHED,
  as in the 2026-10-31 build: the Dockerfile, .dockerignore and requirements are byte-identical to 80df1831d168's. Every
  RootFS layer but the last two equals 88544c7cd33f's (11 layers, the first 9 equal). By the operator, offline, after
  the phase: pypdf 6.21.2 in the new image; `dpkg-query -W -f '${Package} ${Version}\n'` read first from
  cpt-studio:80df1831d168, where it reproduces the recorded list (166 lines, sha256
  6f1b61f6480b598761c5e9e9af22c901c8cfde16cadb83fe5c23b1b749b07ed8; re-read 2026-11-02T13:2xZ), then from the new
  image: identical. A build log showing apt or pip ran is a stop before app.
- Before app, outside the installer and read-only on the database: one `pg_dump -Fc` of the cptstudio database through
  the database container's own pg_dump, to /home/claude/cpt-studio-install-20261023/pre-app-41e03656df61-<UTC>.dump (0600);
  its `pg_restore --list` shows 29 TABLE DATA entries. The only data-level way back; synthetic documents, responses
  and password hashes; kept until a separate, recorded decision removes it.
- app:
  - the application's loader parses the Corti credentials and each participant's credentials file in the worker's
    mount layout with no network (the three files exist as the secrets phase wrote them: 10150:10150 0400);
  - migrate applies exactly 0007_harness_participants_retrieval and 0008_harness2_exchanges_tools_confirmations;
  - the queue read finds 0 stages this revision cannot run;
  - the 80df1831d168 pair is stopped and parked, a new cpt-studio-web and cpt-studio-worker run on the new image with
    the same hardening, mounts, limits, labels and ports, and the worker mounts the two participant credential files
    read-only; /health/ reports release 41e03656df617d5fab4a551ba7a0d7aea5ca3380;
  - states_recomputed {"encounters": 43, "changed": {}} (predicted below); the parked pair is removed;
  - access_checks: one check each - corti (one request), astra and fable (one run of the pipeline's tool loop each, at
    most PARTICIPANT_MAX_EXCHANGES = 4 exchanges, each counted in its receipt) - each ok, astra's returned model gpt-6-astra and
    fable's claude-fable-5-1 recorded exactly as returned, each receipt checked by a root helper to carry no credential
    value. The access check writes nothing to the database.
  Counts after app: every count equals the pre-app reading (no data migration, nothing re-assessed, the access check
  writes no row); studio_migrations 8; the five new tables exist and are empty.
- passages: three files imported (cms-claims-manual-100-04-ch12 4 passages, cms-ncci-policy-manual-2026-ch6 16,
  cms-pfs-rvu26d-documentation 42): passage sources 0 to 3, reference passages 0 to 62. Every other count unchanged.
- license-note: {"rows": 2, "before": {"old": 2, "new": 0, "other": 0}, "after": {"old": 0, "new": 2, "other": 0},
  "updated": 2, "updated_keys": ["cms-mue-practitioner-2026q4", "cms-pfs-rvu26d"]}; assessments_with_old_note 58 (the
  stored assessments keep the note they were made with: history is not rewritten, I1's declared exception). Every other
  count unchanged.
- verify: none.
- Image 88544c7cd33f (cpt-studio:80df1831d168) is kept: it is the rollback image. Nothing removes any image.

Predicted with this revision's own code (2026-11-03T17:03:48Z, on 41e03656df61, over the read-only live dump of that minute (sha256 c2bd29a2c94f1bc8, 29 TABLE DATA); $S4/install-harness/predict_*.sh, kept with their outputs) over a
read-only dump of the live database restored into scratch databases on the test server: migrate applies 0007 and 0008;
RECOMPUTE_STATES {"encounters": 43, "changed": {}}; the installed revision's RECOMPUTE on the same dump the same; a
control with an unknown outcome planted on one sent run of a reviewed encounter turns that encounter to
provider_unknown; the passages and license-note answers above, and each phase run twice changes nothing more; the
rollback hazard read (UNDO_HAZARDS_READ) {"hazards": {}}, its planted control named. The prediction holds only while the
re-read baseline shows no live activity.

## What the install sends

Three access checks, all in the app phase, after the new pair runs. Each runs under the installation-wide lock, with
no retry:
- Corti: one minimal synthetic coding request, after the OAuth token request its adapter sends first (two HTTPS
  requests);
- OpenAI (gpt-6-astra, the harness@2 request): one run of the pipeline's tool loop;
- Anthropic (claude-fable-5-1, the harness-3 request): one run of the pipeline's tool loop.

Each tool-loop run sends one request per exchange, at most PARTICIPANT_MAX_EXCHANGES (4). So the checks send 4 to 10
HTTPS requests in all, every participant exchange counted in its receipt. Nothing else: the
installer's other one-shots run with the providers disabled. Immediately before app: jobs_active 0; no provider run
reserved or sending; no unreconciled unknown outcome; no audit event newer than 10 minutes. Checked after app: provider
runs, sent runs, credits_sum, jobs and audit events equal their pre-app reading, and no provider run has a created_at at
or after the app receipt's started_at.

## After the install: the acceptance walk (ordinary use, not a phase)

All through https://cpt.quillmd.com, through the ordinary reviewer account demo-reviewer (a human reviewer membership;
interpretation 63: every approval's note says "session-made synthetic acceptance-test approval, not a human review").
One document per invocation, strictly in sequence; the next starts only when jobs_active is 0 again. From cpt-studio/ of
the install checkout:

    node ops/verify_browser.cjs --base-url https://cpt.quillmd.com --password-file /home/claude/.cpt-studio/demo-reviewer-password \
      --username demo-reviewer --acceptance-reviewer --expect-harness --docs /home/claude/cpt-studio-gi4-20261031/walk-harness-out \
      --manifest /home/claude/cpt-studio-gi4-20261031/walk-harness/manifest.json --out <a fresh evidence directory> --only <id> \
      --deadline-seconds 1500 --allow-live-provider
    python3 -B ops/verify_downloads.py --evidence <dir>/evidence.json --only <id> --json-out <dir>/downloads.json

The password file is passed by path and never read by a session tool. The manifest (sha256 f6653f6360e8d50559de6f9a696fa3c81f315d893fc0ed38c009ef7faff68877) and the
generated uploads (generated.json binds them) are three fresh synthetic documents the session wrote on 2026-11-02 and
never uploaded anywhere: hw-01 (colonoscopy to the cecum, one cold snare polypectomy; a text-layer PDF; approve 45385),
hw-02 (EGD with a cold forceps biopsy of the antrum; DOCX; approve 43239), hw-03 (flexible sigmoidoscopy with a cold
forceps biopsy; pasted; approve 45331). Offline, with a scripted Corti answer citing the expected code verbatim and no
participant, each reaches ready_for_review with that one code ready and no question; live, the result depends on
Corti's and the participants' actual answers, and whatever they are is recorded and reported, never retried.

The walk approves only a ready selected code its plan names, makes no rejection, confirms no exclusion, asks no second
review and makes no confirmation (none is offered). A document whose every selected code is ready and named reaches its
reviewed report, which is downloaded and checked against the saved state; any other withholds it, and that is a result.

Bounds per document (database counts, SELECT only, before and after each): encounters +1, revisions +1, source files +1
(0 for the paste); provider runs at most +5 (Corti's primary, Astra's and Fable's first readings, their two peer
reviews), each sent at most once; provider exchanges at most +16 (four per participant run) and their tool calls; jobs
at most +10 (extract, analyze, predict, astra, fable, assess, astra_peer, fable_peer, assess, and one spare for a
member's identical save); assessments at most +2; decisions and reports + what the evidence records as HTTP 201;
second-review runs +0; finding confirmations +0; jobs_active back to 0. Cost: about 0.04 Corti credits and an
estimated US$0.40-1.50 per document from the participants (the access checks measured 0.0435 for one Astra exchange and
0.1261 for two Fable exchanges), a record, not a gate; the whole walk is stopped if the estimated participant cost of
the walk exceeds US$10.

## Must not change

- The quillmd vhost (e9aa049d…7638) and every other sites-available file, quillmd-cpt included; nginx.conf, conf.d and
  every sites-enabled entry; the local routing of every co-tenant name/port pair and of an unknown host.
- app.quillmd.com /health/ and the check-cotenants.sh results; every container outside CPT Studio running at preflight
  (same id, still running); every existing volume; every Let's Encrypt lineage and renewal config; the ACME account set.
- The QuillMD rebuild, its database, users and files. /etc/cpt-studio/ and its six files (app.env, db.env,
  corti-credentials.env, openai-credentials.env, anthropic-credentials.env, initial-credentials.json - as the secrets
  receipts of 2026-11-02 record them) and /etc/cpt-studio-provider-sources/.
- cpt-studio-db: the same container, image, port and restart policy, running throughout; volumes cpt-studio-pg and
  cpt-studio-files; network cpt-studio-net.
- The two ReferenceSource rows (except their licence note, above) and 34,665 reference facts; the three accounts and
  their memberships.
- Every existing encounter, revision, source file, context, routing run, provider run, assessment, proposal, decision,
  clarification, audit event, report and job: no data migration, nothing re-assessed, every stored state recomputed
  unchanged.

## Validation per phase

Each phase's own checks (ops/INSTALL.md) must pass and its receipt must say ok, with tree.mode
descendant-without-runtime-change, tree.head the merge commit that lands this declaration, door.declaration this file,
door.declaration_commit the commit that last touched it. preflight: the nginx files, the known warnings, check-cotenants
exit 0, app.quillmd.com 200, ports 9150 and 55451 published only by cpt-studio-web and cpt-studio-db, no task outside
CPT Studio as uid 10150, A 147.189.172.8 only, one ACME account, at least 10 GiB free. image: as above. app: as above,
then by the operator /health/ through 127.0.0.1:9150 {status ok, service cpt-studio, data_mode synthetic-only,
database ok, release 41e03656df617d5fab4a551ba7a0d7aea5ca3380}. passages, license-note: as above. verify: no difference from the preflight baseline;
https://cpt.quillmd.com/health/ serves 41e03656df617d5fab4a551ba7a0d7aea5ca3380 under normal certificate verification; the security headers once each.

## Rollback per phase, and its limits

The installer's rollback rules are this revision's (ops/INSTALL.md, "What each phase checks", "Reinstalling an older
revision"; refuted with the release); they read every hazard as 057a7d39 reads the rows.
- preflight, image, passages, license-note and verify change nothing that serves. A failed image leaves at most an
  unused image. passages and license-note are idempotent: a failure leaves the files imported before it imported, or
  no note changed (license-note writes in one transaction), and a rerun completes them.
- app fails before the swap (a credentials parse, migrate or the queue read refuses): nothing is replaced and the
  80df1831d168 pair keeps running. Migrations 0007 and 0008 are additive: once applied they stay (migrations are not
  reversed), and 80df1831d168 runs on that schema (0007 gives each new column a database default; no older revision
  reads the new tables).
- app fails while the 80df1831d168 pair is being parked, after it is parked and before the new pair is ready, or after
  the new pair is ready (the recompute, the parked pair's removal, an interrupt, or the access check): exactly as
  ops/INSTALL.md and the app phase's receipt set out (the close of the stages it queued, the settlement of the runs it
  left unsettled, the hazard read, the put-back or the pair left stopped). An access check that does not pass leaves
  the new pair installed and serving, with the participants live: the receipt says which check failed and nothing is
  undone; the walk does not start, and whether to re-run `app --access-check`, or reinstall with a participant
  disabled, is a separate recorded decision.
- Each failure is a stop: the pair that is running serves while it is judged, and no remedy (rerun, rollback-app,
  rename back) is taken without a decision recorded under this declaration.
- After a successful app, going back to 80df1831d168 is: clear the hazards on this revision's web, run this revision's
  rollback-app (it refuses while any remains), then a separately declared reinstall of 80df1831d168. The hazard read
  predicted over the live dump names nothing ({"hazards": {}}; its planted control named). The walk's encounters will
  very likely carry the hazard "participant" (a code only Astra or Fable proposed): clearing it needs this revision
  installed again with --astra-mode disabled --fable-mode disabled and each named encounter re-assessed on its web (a
  saved context change re-checks; an addendum sends a new request), each a separate recorded decision. Until then this
  revision stays installed.
- The pre-app dump is the only data-level way back; restoring it deletes every row made after it and is a separate
  declared act. Requests already sent and their usage stay. Image 88544c7cd33f and its receipts are kept for a reinstall.

## What is not claimed

- No coding-accuracy figure and no reliable-coding claim. Clinical validation is NOT established: no qualified coder
  has adjudicated a predeclared set. The live walk proves the pipeline runs end to end, not that its codes are right.
- No reviewer confirmation (HARNESS.md 12.10): checklist 4.6 is not done in this release; what it becomes is the
  owner's open question.
- CPT descriptors, guidelines and NCCI procedure-to-procedure edits stay not verified; CMS public sources only (D3, D4
  open). Data at rest is unencrypted and there is no scheduled backup.
- pypdf 6.21.2 and its seven advisories stay (interpretation 68, owner's open question); the dependency audit stays red.
- The existing encounters are neither re-assessed nor re-sent; how the new screens present them is not walked.

## Stop conditions

Stop and diagnose on any of these; do not rerun a phase and do not upload the next walk document:
- any non-zero phase exit or a receipt that does not say ok; a tree mode other than descendant-without-runtime-change;
- a routing, health, check-cotenants or file-hash difference, or a new nginx warning;
- a new image whose pypdf is not 6.21.2 or whose package list differs, or a list from 88544c7cd33f that does not
  reproduce the recorded one; a build log showing apt or pip ran;
- a migrate log that applies anything but 0007 and 0008; a stage this revision cannot run;
- before app: jobs_active not 0, a reserved or sending run, an unreconciled unknown outcome, or an audit event under
  10 minutes old; across app: any count moving, or a provider run created during the install;
- states_recomputed naming any changed encounter (predicted none); a leftover *-previous container;
- an access check that is not ok, that returned a model other than the one requested, or whose receipt carries a
  credential value;
- passages or license-note answers other than the ones above;
- ports 9150 or 55451 held by anything but cpt-studio-web and cpt-studio-db; any task outside CPT Studio as uid 10150;
- during the walk: a request carrying a date the document's own reading does not give; more provider runs, exchanges or
  jobs than the bounds above; a second-review run; any finding confirmation; a decision of a kind, or on a code, the
  plan does not name; an unknown provider outcome (reconciling it is a separate, recorded decision); a provider
  authentication, quota or payment failure (acts from the next document); verify_downloads exiting 1 or 2; jobs_active
  not returning to 0 within the stage deadlines; a /health/ release other than 41e03656df617d5fab4a551ba7a0d7aea5ca3380, or any 5xx; a downloaded report that
  misstates the persisted decisions; any action on an encounter the walk did not create.

## Decision recorded under this declaration after the image phase's stop (2026-11-03, session cd048041)

Appended after the act began; nothing above is changed. It is committed, and lands through its own PR, before any
later phase runs.

**What stopped.** The preflight phase passed (receipt preflight-20261103T193306134597Z.json: ok, every preflight row
above as declared). The image phase exited 0 and its receipt says ok (image-20261103T193415728635Z.json: cpt-studio:41e03656df61
= sha256:31d8d09721d5ab8ce0340f8906cb657c370584bca3566771c2358c5c98d46ae1). The operator's checks then met two of the
stop conditions above:
- The build log (image-20261103T193354313426Z-01-docker-build.log) shows `[5/8] COPY requirements.txt ./` and
  `[6/8] RUN pip install` ran, not CACHED (pip took 11.0 s). Steps 2 to 4 (apt, the user, WORKDIR) were CACHED.
- The new image's `dpkg-query -W -f '${Package} ${Version}\n'` list (166 lines, sha256
  500b6abda58b9a3e08f082bcfd06e641a580e97e951ffca2b939a2f545ed9194) differs from the recorded one. cpt-studio:80df1831d168
  still reproduces the recorded list exactly (166 lines, sha256 6f1b61f6…). The difference is exactly two packages:
  libsasl2-2 and libsasl2-modules-db, 2.1.28+dfsg-10 to 2.1.28+dfsg-10+deb12u1, a Debian 12 stable-update revision
  whose content is not established here (the slim image carries no changelog).
- So the RootFS prediction was false as well: 11 layers, of which the first 4 (the base image's) equal 88544c7cd33f's,
  not 9.

Nothing ran after the stop. The app phase was not run, and the 80df1831d168 pair served throughout.

**Cause, measured.** The cause is this session's own error. On 2026-11-02T07:10Z, in the disk cleanup the owner asked
for, the session ran an unfiltered `docker builder prune -af`. That deleted every build-cache record, the 2026-10-31
image build's included. At 07:52Z it built a precheck image, cpt-studio-precheck:fa457805ca3b
(sha256:b469e2d4310e…), from the same Dockerfile and requirements, in a context it extracted itself with GNU tar. Its
apt step ran afresh and installed the +deb12u1 packages, giving layer sha256:530d5634d484…. The precheck image built at
05:55Z, before the prune (cpt-studio-precheck:e3c05bc007c6), has the original layer sha256:e84a2052de1b…, as
88544c7cd33f does.

Today's build reused the 07:52Z apt layer, reported as CACHED, but not its requirements COPY. `git archive` writes
requirements.txt with mode 0664. The precheck's context kept 0664, and the installer's extraction normalizes files to
0644, so the COPY's cache key differed and pip ran again. The prediction above was written without checking that the
surviving cache records matched the installer's context. The check made before the act, at 19:04Z, confirmed only that
records for those steps existed.

**Measured equivalence of what changed:**
- **pip.** The 23 installed distributions have identical names and versions in cpt-studio:80df1831d168 and the new
  image. Each one's installed-file hash list is also identical: its RECORD without bytecode entries, read offline in
  each image (the two fingerprint files are byte-identical, sha256 176156b6…). So pip installed the same wheels. pypdf is
  6.21.2.
- **The two system libraries.** They are used by the system libldap-2.5-0, and through it by libcurl4: tesseract's URL
  input, which CPT Studio does not use. The database driver loads its own bundled copy,
  psycopg_binary.libs/libsasl2-84219a89.so.3.0.0, which is identical in both images (above).
- **The rest of the image.** User 10150:10150, the revision label and CPT_STUDIO_RELEASE_SHA=41e03656df617d5fab4a551ba7a0d7aea5ca3380
  are as declared, and the image phase's own smoke checks passed.

**Decision.** Made by session cd048041, the integration and deployment owner, under the standing authority. It is not
one of the owner's four classes: no product decision, capability loss, eyeball acceptance, money, key or deletion.
- **The image.** Install sha256:31d8d09721d5… as built. It is not rebuilt: no build through this revision's installer
  can bring back the deleted records, and the Debian mirror now serves +deb12u1.
- **The image rows above, amended to what was measured:**
  - apt (step 2) is the 2026-11-02 precheck's layer;
  - requirements and pip (steps 5 and 6) ran, installing the same files;
  - the package list is 500b6abd…, the recorded list with libsasl2-2 and libsasl2-modules-db at +deb12u1;
  - 4 of 11 RootFS layers equal 88544c7cd33f's.
- **The rest of this declaration stands unchanged:** the baseline, the pre-app dump, the app, passages, license-note
  and verify predictions, the walk and its bounds, the stop conditions and the rollback. Image 88544c7cd33f stays the
  rollback image.
- **How the remaining phases run.** They run in order, from a clean, detached checkout of the merge commit that lands
  this addendum: a descendant of the revision without runtime change, with its tree.head and door.declaration_commit in
  each receipt.
  - preflight-20261103T193306134597Z.json stays this act's binding baseline, and image-20261103T193415728635Z.json its
    image. Neither phase is re-run.
  - The app phase's pre-checks (jobs_active 0; no reserved or sending run; no unreconciled unknown outcome; no audit
    event under 10 minutes old) and the baseline counts are read again immediately before it.
