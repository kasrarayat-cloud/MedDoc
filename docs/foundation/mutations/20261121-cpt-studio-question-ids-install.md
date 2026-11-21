# Prospective declaration: CPT Studio asks each question once at cpt.quillmd.com (0de2b5844857 to c28ff379ba40), installed blue/green with the site kept serving: no migration, a change in how the coding review is asked for questions and how its answer is read, nothing re-coded

Authority: the owner's direction of 2026-11-20 recorded verbatim, with this programme's interpretation, in
docs/foundation/rulings/2026-10-23-cpt-studio-gi.md (its section "Owner direction, 2026-11-20 — ask each question once,
for every document", landed with the fix in PR #1503) and a RULINGS.md row:

- D372: after the read-only report on a document of his that showed its two questions five times: "is it fixable and
  also i expect taht fix for whole thing not related only for this pdf tho", and "yeah run alongside since we have
  resources". The session's recorded interpretation: the fix is general (every document, every round, never a rule about
  one document or one wording); each question is written once with an id and the site merges by id; it is proven by
  offline tests, one paid pair, a refutation pass on the finished diff (it is the coding path) and CI; and it gets its
  own code-only install through the ruled-act door, after the highlight's.

It stands on the standing directions this install keeps:
- D358, "start it but dont crate the old system engine again": the change is plumbing. Nothing reads a question's
  meaning or compares wordings beyond the exact-text merge the site already had; no question is dropped; no code is held
  or changed by it.
- The 2026-10-23 directive (a protected synthetic demonstration; app.quillmd.com and unrelated services preserved).
- D360's install conditions: no unresolved critical or high finding; every suite green; CI green on the merged commit;
  this declaration committed before the act; the rehearsal on a restored copy of live passed; preflight not BLOCK; the
  act only through the door; a check on the live site afterwards; a report either way.

The integration and deployment owner is session `738699b2`. CPT Studio stays standalone and synthetic-only. No purchase,
agreement, key or payment change is part of this act, and no paid request is made by it.

Revision to install: `c28ff379ba40edb461cf5476c94968e228dcac03`, the merge commit of PR #1503 (branch
feat/cpt-studio-question-ids-20261120, head `dfd3f955f17a1ef07415f877c4a8cea83055aaf2`; the merge commit's tree is the
head's tree: main had not moved since b567d7357). It contains origin/main as of the merge. Image tag
cpt-studio:`c28ff379ba40`. Its citation, on the revision: `CI 44898782078 success, cpt-studio 44898782091 success,
secrets-scan 44898782114 success, the same three in both views (gh run list --commit and --branch main,
2026-11-21T11:48Z)`. The PR head's citation: `CI 44896702411 success, cpt-studio 44896702415 success, secrets-scan
44896702449 success, the same three in both views (gh run list --commit and --branch)`. cpt-studio is not a required
check; it is required here.

It replaces the live revision 0de2b5844857daf9593663f5f730e3ebc7a65130 (image cpt-studio:0de2b5844857, id
sha256:83283df751fa167bd4ce0bba7d87c67b4356f5e5710c7cd7afe5c7e2b26c65cd, its web on 127.0.0.1:9151 since that install's
switch at 2026-11-21T10:12:03Z), installed under docs/foundation/mutations/20261121-cpt-studio-pdf-highlight-install.md
(PR #1501, a141c2ea85d7). That image is kept as the rollback image (switch-back). That declaration and its receipts stay
as they are.

Execute each phase separately through scripts/run-ruled-mutation.sh with `RULED_ACT_MAX_SECS=9000`, as `python3 -B
cpt-studio/ops/install.py --phase PHASE --revision c28ff379ba40edb461cf5476c94968e228dcac03 --receipts
/home/claude/cpt-studio-install-20261023` (questions-20261121/install/act_q.sh: the highlight's act_h.sh with this
release's names).

Phases, in this order:
1. preflight;
2. image;
3. app, with `--coding-mode live --authorization-ref docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`, the modes
   the live pair runs with;
4. verify.

The installer gives the web and the worker the same coder settings as the live pair (the revision's settings.py
defaults: effort max, the 25 US dollar per-document ceiling, 4 documents at once).

Run them from a clean, detached checkout of the merge commit that lands this declaration
(/opt/meddoc-pro/.worktrees/cpt-questions-act-20261121). That commit must be a descendant of the revision that changes
nothing under cpt-studio/, scripts/run-ruled-mutation.sh or scripts/lib/. Read each receipt before the next phase.

Not run: secrets, db, reference, passages, license-note, provision, operators, http-vhost, cert, https-vhost,
rollback-vhost, rollback-app and switch-back. switch-back is the incident path (below). No document is sent by the
install.

Between 0de2b5844857daf9593663f5f730e3ebc7a65130 and the revision, these are byte-identical (`git diff --quiet
0de2b5844857daf9593663f5f730e3ebc7a65130 c28ff379ba40edb461cf5476c94968e228dcac03 -- <these paths>: exit 0,
2026-11-21T11:26Z`): the migrations (still 0016_fable_coding, the last), models.py, api.py, storage.py, intake.py,
jobs.py, state.py, the whole static viewer (studio/static: app.js, styles.css and the pinned PDF library), access.py,
the page template index.html, cptstudio/settings.py, ops/install.py, ops/walk.cjs, deploy/ (the Dockerfile) and
requirements.txt. These change, and are named here: the coding review's instructions and how its answer is read
(studio/fable/prompts.py, studio/fable/result.py), how decisions and the customer view refer to questions
(studio/decisions.py, studio/customer.py), the operator console's encounter page (studio/operator.py,
studio/templates/studio/ops_encounter.html), the dev preview (ops/dev_preview_server.cjs: a fixture with a shared
question), the tests and fixtures (among them tests/test_question_ids.py), and the docs (API.md, ARCHITECTURE.md);
outside cpt-studio/, docs only (docs/foundation/RULINGS.md, docs/foundation/rulings/2026-10-23-cpt-studio-gi.md, and
this morning's highlight declaration and report).

Before preflight the operator runs, in the act's checkout:
- `git diff --quiet 0de2b5844857daf9593663f5f730e3ebc7a65130 HEAD -- cpt-studio/studio/migrations
  cpt-studio/studio/models.py cpt-studio/studio/api.py cpt-studio/studio/storage.py cpt-studio/studio/intake.py
  cpt-studio/studio/jobs.py cpt-studio/studio/state.py cpt-studio/studio/static cpt-studio/studio/access.py
  cpt-studio/studio/templates/studio/index.html cpt-studio/cptstudio/settings.py cpt-studio/ops/install.py
  cpt-studio/ops/walk.cjs cpt-studio/deploy cpt-studio/requirements.txt`, exit 0;
- `git diff --name-only 0de2b5844857daf9593663f5f730e3ebc7a65130 HEAD -- cpt-studio/studio/migrations`, printing
  nothing;
- `git diff --name-only c28ff379ba40edb461cf5476c94968e228dcac03 HEAD -- cpt-studio scripts/run-ruled-mutation.sh
  scripts/lib`, printing nothing.

Any other difference is a stop.

**The deploy range against held declarations** (docs/DEPLOYMENT_RUNBOOK.md 2.5; install-judge/held_check_j.sh with this
range): `install-judge/held_check_j.sh 0de2b5844857daf9593663f5f730e3ebc7a65130
c28ff379ba40edb461cf5476c94968e228dcac03, 2026-11-21T11:26Z: the range's first-parent merges are #1503, #1502 and #1501;
7 runtime files, all under cpt-studio/; positive control (deploy-prod.sh named by 63 files) passed; 1 declaration names
a runtime file of the range (this morning's highlight declaration), and every revision it names is an ancestor of the
running revision; possibly held: 0`.

## Delta shipped (0de2b5844857 to the revision)

**This is a TREE, not one change**, but its only runtime change is the question fix: the range carries #1503 (this fix:
its 6 commits and the merge of main into it) and #1501 and #1502 (this morning's highlight declaration and report, docs
only).

- Runtime, on the coding path: the coding review is asked to write each question once with an id and to refer to it by
  id from its code lines; the second check is shown the coding review's questions with their ids and writes only new
  ones; the answer is read by id, with the exact-text merge kept, and a line's question is resolved among the questions
  its author was shown. The customer view and the decisions refer to questions the same way; the operator console's
  encounter page lists any question id a line, review or missed code gave that names no question, and any id both
  answers defined. No model, no setting of the coder, no migration, no stored round re-read or re-coded.
- Docs: API.md and ARCHITECTURE.md state the id rules and the written limit QL3-1.

## What members see after the install

- A new coding round asks each question once: the coding review writes each question once with an id (Q1, Q2 ...),
  the second check writes only questions the coding review did not ask (C1, C2 ...), and each question is shown once
  with every line it affects. Answers keep their shape.
- A document already coded keeps the question list its stored round shows, until it gets a new round (an answer, a
  retry or a new upload): measured on a copy of live, every stored encounter's customer view is identical under the
  revision (below).
- A new round's exports show its questions the same way (the draft lists each question once, and a line shows its
  question); a stored round's exports, and every export already made, are unchanged (they are built by the same
  functions as the customer view, which measured identical).
- Nothing else changes: the viewer, the highlight, the operator console's other pages.

## Cost and time

No paid request. The image build reuses the cached apt and pip layers (deploy/Dockerfile and requirements.txt are
byte-identical to 0de2b5844857's). The app phase takes about 3 minutes (the blue/green switch; the worker's stop bound;
this morning's app phase took 3 min 1 s).

## Measured before this declaration

**The paid pair (D379, owner rule: one short and one realistic document)**: on a restored copy of live with the branch's
image cpt-studio-test:8ee7b906d25b, the owner's document asked its two questions once each (live had shown them five
times) with the same codes, and the short synthetic document came back ready; US$5.95. The question path of the revision
(studio/fable, decisions.py, customer.py, operator.py, ops_encounter.html, models.py, jobs.py, state.py, api.py, the
migrations) is byte-identical to that head's (`git diff --quiet 8ee7b906d HEAD -- <those paths>`: exit 0), so the pair
speaks for it.

**The refutation of the finished diff (the coding path)**: rounds 1-3 to dry; round 4 changed docs only (D378); one
written limit, QL3-1 (a plain string in question_ids is always read as an id, so question text written there reaches
only the operator console).

**Offline predictions** (questions-20261121/install/predict_q.sh on a throwaway restore of a fresh read-only dump of
live, in the revision's test image): 2026-11-21T11:23Z, cpt-studio-test:c28ff379ba40 (sha256:5bf57265eb80...): dump
11:23:01Z (sha256 7181797315359508..., 48 TABLE DATA); schema 16 migrations, last 0016_fable_coding, before and after;
migrate in the candidate image applied nothing; every encounter's customer view (customer.encounter_json with a fixed
clock and the workspace's first active membership) built by the installed image and by the candidate over the same
pristine restore and hashed per encounter: 95 and 95, 0 errors, 0 differing (the same step run at 10:58Z with the
branch's image: 95 distinct hashes, 6 coded encounters, 2 with questions holding 9, the files byte-identical);
UNRUNNABLE_STAGES stuck 0; V1_ROWS none; INSTALL_COUNTS encounters 95 (6 coded); RECOMPUTE_STATES changed {} (6 coded,
89 kept); no table delta; states awaiting_answer 2, extraction_failed 1, needs_clarification 47, no_codes 4, ready 2,
ready_for_review 8, reviewed 31. The throwaway database and its files volume were dropped.

**The rehearsal on a restored copy of live**: install-judge/rehearse_j.sh setup with CODING=disabled (nothing sent): a
fresh read-only dump of live (2026-11-21T11:23:47Z, sha256 709d0267a8d8231f...) restored as cptg_jreh_20261121t112344z
on the test server, migrated with cpt-studio-test:c28ff379ba40 (nothing applied), the revision's web and worker on
127.0.0.1:9371, every provider disabled, 95 encounters; the two synthetic walk originals copied into the copy's files
volume from live's (mounted read-only, each sha256 equal to the database's), since a restore carries the database only.
hl_check.cjs (the revision's walk) passed: 255e92ac (gi-02, a PDF) 15 of 15 quotes marked once with both redraws judged,
6c450473 (gi-01, a text) 17 of 17; GET requests only besides the sign-in and sign-out POSTs; no violation, no page
error; its sign-out navigation was cut short again (net::ERR_ABORTED) and judged by its outcome, GET /api/session
answering 401. Its database footprint, counted table by table: studio_loginattempt +1, nothing else.

**The switch-back rehearsal on that copy**: rehearse_j.sh switchback 0de2b5844857daf9593663f5f730e3ebc7a65130 on that
copy, as the installer runs it: the stack stopped; UNDO_HAZARDS_READ {} and TOUCHED_SINCE_READ []; CLOSE_STAGES closed
0; the installed image's UNRUNNABLE_STAGES stuck 0 and PUT_BACK_STATES changed {} for the 6 coded encounters; the
installed image's own API read every encounter as the customer: the list 200 and all 95 details 200; forward again,
RECOMPUTE_STATES changed {}; the states identical throughout; rounds done 6. Then torn down: the copy dropped, its files
volume (with the two copied originals) removed.

## Baseline (read-only, `2026-11-21T11:48:53Z`; re-read immediately before the commit that lands this declaration; this act's preflight receipt and pre_app_q.sh are binding)

Read with these commands, all read-only (the SQL is SELECT only, in a read-only transaction, through the database
container's own psql; counts and states only, never a document, response or credential):

    bash /home/claude/cpt-studio-completion-20261106/gemini-migration/install-judge/live_baseline_j.sh
    bash scripts/check-cotenants.sh
    docker ps -a --filter label=org.quillmd.cpt-studio=1 --format '{{.Names}} {{.Image}} {{.Status}} {{.Ports}}'
    docker image inspect cpt-studio:0de2b5844857 --format '{{.Id}} {{index .Config.Labels "org.opencontainers.image.revision"}}'

    read_at 2026-11-21T11:48:53Z
    transaction_read_only on
    encounters 95
    revisions 96
    source_files 89
    contexts 106
    routing_runs 116
    provider_runs 299
    provider_runs_sent 263
    assessments 186
    proposals 2549
    clarifications 348
    decisions 63
    decision_invalidations 2
    audit_events 1465
    reports 209
    jobs 659
    jobs_active 0
    users 5
    memberships 3
    workspaces 1
    login_attempts 119
    reference_sources 2
    reference_facts 34665
    studio_migrations 16
    studio_migration_last 0016_fable_coding
    studio_providerexchange 264
    studio_toolcall 173
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
    run_participant anthropic appraisal succeeded 4
    run_participant anthropic coding_checker succeeded 6
    run_participant anthropic coding_reader succeeded 6
    run_participant anthropic interpretation succeeded 3
    run_participant astra independent failed 2
    run_participant astra independent not_sent 1
    run_participant astra independent succeeded 44
    run_participant astra peer_review succeeded 46
    run_participant fable independent succeeded 45
    run_participant fable peer_review failed 1
    run_participant fable peer_review succeeded 41
    credits_sum 4.452079999999999826
    usage_keys anthropic cache_creation,cache_creation_input_tokens,cache_read_input_tokens,fallback_credit,inference_geo,input_tokens,iterations,output_tokens,output_tokens_details,server_tool_use,service_tier,speed
    usage_keys astra input_tokens,input_tokens_details,output_tokens,output_tokens_details,total_tokens
    usage_keys corti creditsConsumed
    usage_keys fable cache_creation,cache_creation_input_tokens,cache_read_input_tokens,inference_geo,input_tokens,output_tokens,output_tokens_details,service_tier,speed
    encounter_state awaiting_answer 2
    encounter_state extraction_failed 1
    encounter_state needs_clarification 47
    encounter_state no_codes 4
    encounter_state ready 2
    encounter_state ready_for_review 8
    encounter_state reviewed 31
    run anthropic appraisal succeeded t f 4
    run anthropic coding_checker succeeded t f 6
    run anthropic coding_reader succeeded t f 6
    run anthropic interpretation succeeded t f 3
    run astra independent failed t f 2
    run astra independent not_sent f f 1
    run astra independent succeeded f t 7
    run astra independent succeeded t f 37
    run astra peer_review succeeded f t 2
    run astra peer_review succeeded t f 44
    run corti primary not_sent f f 4
    run corti primary succeeded f t 13
    run corti primary succeeded t f 81
    run corti second_review succeeded t f 2
    run fable independent succeeded f t 7
    run fable independent succeeded t f 38
    run fable peer_review failed t f 1
    run fable peer_review succeeded f t 2
    run fable peer_review succeeded t f 39
    job analyze succeeded 89
    job appraise succeeded 3
    job assess succeeded 186
    job astra cancelled 3
    job astra succeeded 45
    job astra_peer succeeded 46
    job code succeeded 6
    job extract succeeded 90
    job fable cancelled 4
    job fable succeeded 45
    job fable_peer cancelled 1
    job fable_peer succeeded 41
    job interpret succeeded 3
    job predict succeeded 94
    job question succeeded 1
    job review2 succeeded 2
    runs_unreconciled_unknown 0
    runs_reserved_or_sending 0
    last_audit decision.recorded 2026-11-21T03:11:07Z 31066
    account demo-reviewer human t reviewer t
    account ops-agent agent t  
    account owner human t owner t
    account platform-operator human t  
    account review-agent agent t reviewer t
    reference_source cms-mue-practitioner-2026q4 cms-mue-practitioner 2026-Q4 15212 40a09bcd128dd18569a0a01e4fc4cffe
    reference_source cms-pfs-rvu26d cms-pfs RVU26D 19453 40a09bcd128dd18569a0a01e4fc4cffe
    assessments_by_engine cpt-studio-events@3 6
    assessments_by_engine cpt-studio-validation@10 57
    assessments_by_engine cpt-studio-validation@3 12
    assessments_by_engine cpt-studio-validation@4 46
    assessments_by_engine cpt-studio-validation@5 13
    assessments_by_engine cpt-studio-validation@6 15
    assessments_by_engine cpt-studio-validation@7 8
    assessments_by_engine cpt-studio-validation@8 6
    assessments_by_engine cpt-studio-validation@9 23
    contexts_by_version gemini-context@2 3
    contexts_by_version gi-context@1 12
    contexts_by_version gi-context@2 26
    contexts_by_version gi-context@3 19
    contexts_by_version gi-context@4 35
    contexts_by_version gi-context@5 11
    current_context_by_version gemini-context@2 3
    current_context_by_version gi-context@1 12
    current_context_by_version gi-context@2 24
    current_context_by_version gi-context@3 7
    current_context_by_version gi-context@4 31
    current_context_by_version gi-context@5 11
    current_context_by_version none 7
    routing_by_version gemini-routing@2 3
    routing_by_version gi-routing@10 11
    routing_by_version gi-routing@11 8
    routing_by_version gi-routing@12 11
    routing_by_version gi-routing@3 12
    routing_by_version gi-routing@4 38
    routing_by_version gi-routing@5 7
    routing_by_version gi-routing@6 7
    routing_by_version gi-routing@7 7
    routing_by_version gi-routing@9 12
    studio_eventinventory 3
    studio_interpreterhold 0
    studio_interpreterholdrelease 0
    studio_providerhold 0
    studio_providerholdrelease 0
    column studio_assessment.event_inventory_id present
    column studio_assessment.interpretation present
    column studio_encountercontext.earlier_assessment_id present
    column studio_encountercontext.event_inventory_id present
    column studio_eventinventory.appraisal_run_id present
    jobs_reading appraise succeeded 3
    jobs_reading interpret succeeded 3
    jobs_reading question succeeded 1
    runs_interpreter anthropic appraisal 4
    runs_interpreter anthropic interpretation 3
    assessments_new_path 6
    contexts_new_path 3
    decisions_on_current_assessments approve 52 32
    decisions_on_current_assessments reinstate 1 1
    decisions_on_current_assessments reject 6 6
    decisions_on_current_assessments revoke 2 1
    studio_codinground 6
    studio_codinganswer 0
    studio_codedecision 8
    studio_exportartifact 6
    jobs_code succeeded 6
    runs_coding coding_checker succeeded 6
    runs_coding coding_reader succeeded 6
    interpreter_holds_standing 0

    # bash scripts/check-cotenants.sh
    HOST                   EXPECTED  OBSERVED
      🟢 quillmd.com          200       200
      🟢 www.quillmd.com      200       200
      🟢 app.quillmd.com      302       302
      🟢 admin.quillmd.com    503       503
      🟢 pro.quillmd.com      410       410
    🟢 every co-tenant answers its expected status (4 distinct codes — the probe discriminates).

    # docker ps -a --filter label=org.quillmd.cpt-studio=1; docker image inspect cpt-studio:0de2b5844857
    cpt-studio-worker 83283df751fa Up 2 hours 8000/tcp
    cpt-studio-web 83283df751fa Up 2 hours (healthy) 127.0.0.1:9151->8000/tcp
    cpt-studio-db postgres:17.11-alpine Up 6 days 127.0.0.1:55451->5432/tcp
    sha256:83283df751fa167bd4ce0bba7d87c67b4356f5e5710c7cd7afe5c7e2b26c65cd 0de2b5844857daf9593663f5f730e3ebc7a65130

## Expected changes, per phase

- **preflight:** none. Its receipt records the baseline: the quillmd-cpt vhost as this installer's HTTPS stage for 9151
  (sha256 f816a27de9e64af51d6a905484e22fdfc5f13a941a246931261bfc0df1e3ca65); 9151 held by cpt-studio-web alone and 9150
  free; no cpt-studio-web-next; co-tenant routing and https://app.quillmd.com/health/.
- **image:** a new local image cpt-studio:`c28ff379ba40`, built from git archive of the revision's cpt-studio/ and
  labelled with the revision. Its Dockerfile and requirements are 0de2b5844857's, so the apt and pip layers come from
  the cache; the test image of the same revision built as cpt-studio-test:c28ff379ba40 (sha256:5bf57265eb80...), its
  migration safety all safe and its manage check clean. cpt-studio:0de2b5844857 is kept.
- **Before app, read-only on the database** (pre_app_q.sh): one `pg_dump -Fc` through the database container's own
  pg_dump in a read-only transaction, 48 TABLE DATA entries; a restore on the test server migrated with the revision's
  image, where nothing applies; the baseline re-read equals the declared one, with no job active, no run reserved or
  sending, and no audit event newer than 10 minutes. Its log ends "PRE-APP PASS"; act_q.sh's app phase requires it.
- **app (the blue/green switch):** **migrate applies nothing**; UNRUNNABLE_STAGES finds none; V1_ROWS none;
  INSTALL_COUNTS as the prediction (its report again notes the Fable tables' existing rows, as this morning's did); S1
  cpt-studio-web-next starts on 127.0.0.1:9150 and answers /health/ with the revision; S2 the old worker parked; S3 the
  vhost's proxy_pass switched 127.0.0.1:9151 to 127.0.0.1:9150 (sha256 f816a27d... to
  259b895dd1307e81b8fbcb5439874477daf71eba63c9b996b3bdfc572bf71a0c), `nginx -t` clean, graceful reload,
  https://cpt.quillmd.com/health/ serving the revision, the co-tenants unchanged; S4 the new worker starts with the
  coding step live, as the live worker does; S5 the old web drained, stopped and parked; S6 RECOMPUTE_STATES changes
  nothing (6 coded encounters, 0 changed, 89 kept). The receipt names the replaced pair (0de2b5844857's web and worker),
  which a switch-back returns to.
- **verify:** nothing changes.

**Database deltas after app, against the baseline:** none from the install: every count and every encounter's stored
state unchanged. Rows written by members in the window are their own and are named if they appear.

## After the install: the view-only check (ordinary use, not a phase)

highlight-20261120/install/hl_check.cjs (sha256 ba96d6bce7e95e8a5a4c62e48ca3defc16b649d67e121e21d74d5f174789962d, the
copy this morning's live check ran), using the revision's ops/walk.cjs, against https://cpt.quillmd.com with the
review-agent account, on the two synthetic walk documents of 2026-11-20 (gi-02, a PDF; gi-01, a text): it signs in
through the form, opens each document, chooses every quote and judges the marks, so the review page, its codes and
questions panels and the viewer are exercised as members see them. GET only besides the sign-in and sign-out POSTs; any
other request, or one leaving the origin, fails it. Its database rows: studio_loginattempt +1 (its one sign-in) and
nothing else, counted table by table in the rehearsal. No real document is opened. The new question format itself shows
only on a new coding round, which would be a paid request: it is not exercised on the live site (the paid pair above
proved it on the copy).

## Must not change

Every encounter and every row of every table apart from the check's sign-in row (studio_loginattempt +1); the accounts,
memberships, workspace, reference sources, facts and passages; the database container and its volumes; /etc/cpt-studio/;
the co-tenants' HTTP answers and https://app.quillmd.com/health/; every other nginx vhost; every image (nothing is
removed).

## Validation per phase

Each receipt is read before the next phase: preflight exit 0 with the baseline above; image exit 0 with the image id
recorded; pre_app_q.sh ending PRE-APP PASS; app exit 0 with migrate applying nothing, the counts as declared, the switch
applied and https://cpt.quillmd.com/health/ serving the revision; verify exit 0. After app: post_check_q.sh against
this declaration's deltas; scripts/check-cotenants.sh; then the view-only check and post_check_q.sh again.

## Rollback per phase, and its limits

- preflight, verify: nothing to undo.
- image: nothing to undo.
- app before the switch: the installer's own undo stops the incoming web and restarts the parked worker.
- app after the switch: the installer's own undo switches back on failure. After a successful app, the incident path is
  `switch-back` (a fresh preflight, then act_q.sh switch-back with SWITCH_BACK_DECISION recorded). The 0de2b5844857 pair
  returns with its own modes. Both revisions share the schema, so no coding job is closed and no state changes (measured
  on the copy: no hazard, nothing closed, the states unchanged). A round coded under the revision before a switch-back
  keeps its stored answer, and the previous image would show it by its own reading: not rehearsed, since no such round
  exists on the copy.
- The receipts, the pre-app dump and the images stay.

## What is not claimed

- That the coding review always follows the id format: one paid pair showed it does; where an answer departs from the
  instructions, the site still merges exact-text copies as before and drops no question, and written limit QL3-1 holds.
- That a stored round's repeated questions disappear: a document keeps its stored question list until a new round.
- Any change to the codes themselves: the instructions change only how questions are written and referred to.
- Past the known limits written in cpt-studio/ARCHITECTURE.md and API.md for question ids.

## Stop conditions

- Any phase exiting non-zero.
- A receipt or reading that differs from this declaration: a difference not declared here is THE finding, whatever its
  explanation.
- migrate applying anything.
- An encounter's stored state changing in app.
- The citation not success in both views.
- A held declaration found.
- Preflight BLOCK, or the installer's preflight refusing.
- The door's ceiling reached.
- A co-tenant's or app.quillmd.com's answer changing.
- The view-only check failing: judged, then reported. A defect found there is fixed under D358 and installed under a new
  declaration, or the site is switched back. It is never patched in place.
