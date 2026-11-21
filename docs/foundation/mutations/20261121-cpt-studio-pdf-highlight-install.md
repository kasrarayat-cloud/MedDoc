# Prospective declaration: CPT Studio's PDF quote highlight at cpt.quillmd.com (7dd813005077 to 0de2b5844857), installed blue/green with the site kept serving, code only: no migration, no coding change, nothing re-coded

Authority: the owner's direction of 2026-11-20 recorded verbatim, with this programme's interpretation, in
docs/foundation/rulings/2026-10-23-cpt-studio-gi.md (its D368 section, landed with the feature in PR #1500) and a
RULINGS.md row:

- D368: "ok do highlight". This answers the 13:03Z install report's question: "Should I do the next update: highlighting
  the quoted text inside the PDF viewer (about 1–2 days), the four medium fixes, and removing the last unused piece of
  old code?" The session's recorded interpretation is: build the highlight; prove it (refutation rounds, every suite and
  CI green, the owner's share-link PDFs measured offline, a rehearsal on a restored copy of live); install it as a
  code-only release through scripts/run-ruled-mutation.sh with this declaration committed first; check it view-only on
  the live site; report. The four medium fixes and the store.py removal stay queued (not in this release).

It stands on the standing directions this install keeps:
- D358, "start it but dont crate the old system engine again": the highlight is display plumbing. It only locates the
  quote's own characters on the page. Nothing reads the note's meaning, no word list, no code rule, and no code or
  quote is held or changed.
- The 2026-10-23 directive (a protected synthetic demonstration; app.quillmd.com and unrelated services preserved).
- D360's install conditions, applied again here: no unresolved critical or high finding; every suite green; CI green on
  the merged commit; this declaration committed before the act; the rehearsal on a restored copy of live passed;
  preflight not BLOCK; the act only through the door; a check on the live site afterwards; a report either way.

The integration and deployment owner is session `738699b2`. CPT Studio stays standalone and synthetic-only. No purchase,
agreement, key or payment change is part of this act, and no paid request is made by it.

Revision to install: `0de2b5844857daf9593663f5f730e3ebc7a65130`, the merge commit of PR #1500 (branch
feat/cpt-studio-pdf-highlight-20261120, head `d7eedf5f9629db9519f1c01be306d3148cf1cb78`; the merge commit's tree,
ce725d7e7d3d, is the head's tree: main had not moved since d7c6a77dc). It contains origin/main as of the merge. Image
tag cpt-studio:`0de2b5844857`. Its citation, on the revision: `CI 44887491312 success, cpt-studio 44887491304 success,
secrets-scan 44887491306 success, the same three in both views (gh run list --commit and --branch main,
2026-11-21T09:31Z)`. The PR head's citation: `CI 44882655743 success, cpt-studio 44882655768 success, secrets-scan
44882655716 success, the same three in both views (gh run list --commit and --branch)`. cpt-studio is not a required
check; it is required here.

It replaces the live revision 7dd8130050773f57c98dd48dfa6c128d4fd20292 (image cpt-studio:7dd813005077, id
sha256:b72e426037fde7420194247a79b4d04cb691c75ecdbf49c7411d79ef79458095, its web on 127.0.0.1:9150 since that install's
switch at 2026-11-20T12:48Z), installed under docs/foundation/mutations/20261120-cpt-studio-fable-judge-install.md
(PR #1499, d7c6a77dc). That image is kept as the rollback image (switch-back). That declaration and its receipts stay as
they are.

Execute each phase separately through scripts/run-ruled-mutation.sh with `RULED_ACT_MAX_SECS=9000`, as `python3 -B
cpt-studio/ops/install.py --phase PHASE --revision 0de2b5844857daf9593663f5f730e3ebc7a65130 --receipts
/home/claude/cpt-studio-install-20261023` (highlight-20261120/install/act_h.sh: act_j.sh with this release's names).

Phases, in this order:
1. preflight;
2. image;
3. app, with `--coding-mode live --authorization-ref docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`, the modes
   the live pair runs with;
4. verify.

The installer gives the web and the worker the same coder settings as the live pair (the revision's settings.py
defaults: effort max, the 25 US dollar per-document ceiling, 4 documents at once).

Run them from a clean, detached checkout of the merge commit that lands this declaration
(/opt/meddoc-pro/.worktrees/cpt-highlight-act-20261121). That commit must be a descendant of the revision that changes
nothing under cpt-studio/, scripts/run-ruled-mutation.sh or scripts/lib/. Read each receipt before the next phase.

Not run: secrets, db, reference, passages, license-note, provision, operators, http-vhost, cert, https-vhost,
rollback-vhost, rollback-app and switch-back. switch-back is the incident path (below). No document is sent by the
install.

Between 7dd8130050773f57c98dd48dfa6c128d4fd20292 and the revision, these are byte-identical (`git diff --quiet
7dd8130050773f57c98dd48dfa6c128d4fd20292 0de2b5844857daf9593663f5f730e3ebc7a65130 -- <these paths>: exit 0,
2026-11-21T09:12Z`): the migrations (still 0016_fable_coding, the last), models.py, api.py, customer.py, intake.py,
storage.py, jobs.py, state.py, the whole fable/ package (the coding path), ops/install.py, deploy/ (the Dockerfile) and
requirements.txt. These change, and are named here: the viewer (studio/static/studio/app.js, styles.css appended to, the
page template studio/templates/studio/index.html naming the library's two static addresses), the pinned PDF library (14
new files under studio/static/studio/lib/pdfjs-6.5.438/, its licences and MANIFEST.json with a checksum of every file),
cptstudio/settings.py and studio/access.py (the site's security headers now wrap WhiteNoise, so static files carry them
too, with base-uri 'none': the library's module worker takes its policy from its own script's response), the walk and
its tools (ops/walk.cjs, ops/test_walk.cjs, ops/dev_preview_server.cjs, ops/scan_customer.py,
ops/verification/customer-denylist.json), the tests (tests/frontend/app.test.cjs, tests/test_frontend.py) and the docs
(API.md, ARCHITECTURE.md, CORE-UX-DESIGN.md, README.md); outside cpt-studio/, docs only (docs/foundation/RULINGS.md,
docs/foundation/rulings/2026-10-23-cpt-studio-gi.md, and the previous install's declaration).

Before preflight the operator runs, in the act's checkout:
- `git diff --quiet 7dd8130050773f57c98dd48dfa6c128d4fd20292 HEAD -- cpt-studio/studio/migrations
  cpt-studio/studio/models.py cpt-studio/studio/api.py cpt-studio/studio/customer.py cpt-studio/studio/intake.py
  cpt-studio/studio/storage.py cpt-studio/studio/jobs.py cpt-studio/studio/fable cpt-studio/studio/state.py
  cpt-studio/ops/install.py cpt-studio/deploy cpt-studio/requirements.txt`, exit 0;
- `git diff --name-only 7dd8130050773f57c98dd48dfa6c128d4fd20292 HEAD -- cpt-studio/studio/migrations`, printing
  nothing;
- `git diff --name-only 0de2b5844857daf9593663f5f730e3ebc7a65130 HEAD -- cpt-studio scripts/run-ruled-mutation.sh
  scripts/lib`, printing nothing.

Any other difference is a stop.

**The deploy range against held declarations** (docs/DEPLOYMENT_RUNBOOK.md 2.5; install-judge/held_check_j.sh with this
range): `install-judge/held_check_j.sh 7dd8130050773f57c98dd48dfa6c128d4fd20292
0de2b5844857daf9593663f5f730e3ebc7a65130, 2026-11-21T09:11Z: the range's first-parent merges are #1500 and #1499; 24
runtime files, all under cpt-studio/; positive control (deploy-prod.sh named by 62 files) passed; 5 declarations name a
runtime file of the range, and every revision each names is an ancestor of the running revision; possibly held: 0`.

## Delta shipped (7dd813005077 to the revision)

**This is a TREE, not one change**, but its only runtime change is the highlight: the range carries #1500 (this feature,
32 commits over eight rounds of building, verification and refutation, D368-D383) and #1499 (the previous install's
declaration, docs only).

- Runtime: the viewer, the pinned library, the security headers on static files and the page template, as listed above.
  No Python of the coding path, no model, no migration, no setting of the coder.
- Checks: the walk now reads each PDF itself with the pinned library and holds the viewer to its own reading; its quotes
  check fails a viewer that marks none of its quotes.
- Docs: CORE-UX-DESIGN.md section 8 ("Marking a quoted passage") states the rule and its known limits; section 9 states
  what the walk checks and its own limits.

## What members see after the install

- Choosing a quoted passage of a PDF, or of a Word document's converted PDF, opens the viewer at the quote's page and
  marks the quoted words. A note under the viewer says what was done: marked once, marked K times, continued onto the
  next page, not found in the page's searchable text, or the page has no searchable text.
- The viewer draws the document in the page with zoom from 75% to 300%. The quotes list keeps its height.
- Text documents mark their passage inside the text, and the note says so. A text frame that does not hold the document
  (the edge's own page while the app restarts, an answer the frame refuses) is never searched: the note says the
  document could not be downloaded.
- Where marking cannot run, the browser's own viewer is shown as before, opened at the quote's page where the browser
  allows it. The note says why (a browser below the floor, the marking tool failing or not answering for 20 seconds of
  visible time, a document it refuses, a download that stalls for 20 seconds, or a download that fails) and names the
  quote's page.
- Browsers that mark: Chrome and Edge 119+, Firefox 125+ (ESR 128 and 140), Safari 17.4+ on macOS, iOS and iPadOS,
  Samsung Internet 25+ (measured in Chromium; the other versions are MDN's data for what the measurement found needed).
  Older browsers get the fallback.
- No capability is lost: the browser's own viewer is still what a browser below the floor, or any failure, shows, opened
  at the quote's page; Download original is kept; a text document is still shown in its frame.

## Cost and time

No paid request. The image build reuses the cached apt and pip layers if the Dockerfile and requirements are unchanged
(deploy/Dockerfile and requirements.txt are byte-identical to 7dd813005077's). The app phase takes about 3 minutes (the
blue/green switch; the worker's stop bound; the previous install's app phase took 2 min 50 s, 12:44:50Z to 12:47:40Z on
2026-11-20).

## Measured before this declaration

**The owner's share-link PDFs, offline (D361's standard)**: highlight-20261120/wf/merge5/tools/measure-judged.cjs on a
git-archive copy of the final head d7eedf5f9 (the revision's tree), 2026-11-21T07:56Z, counts only: the six PDFs, 264
citations, each chosen as a quote whose page is only its start page: 240 marked once, 24 marked more than once (every
occurrence on the page counted), 0 not found, 1 continued onto the next page; the walk's own judge passes every document
with 0 problems, its checks (page count, text layer, misaligned, unseen) all 0 and both redraws judged; the synthetic
gi-02 23 of 23 marked once; per citation, 0 of 287 differ from the round-5 merge's run.

**The rehearsal on a restored copy of live**: install-judge/rehearse_j.sh setup with CODING=disabled (nothing sent): a
fresh read-only dump of live (2026-11-21T09:02:12Z, sha256 3205d95a11c4d72a...) restored as cptg_jreh_20261121t090209z
on the test server, migrated with cpt-studio-test:0de2b5844857 (nothing applied), the revision's web and worker on
127.0.0.1:9371, every provider disabled, 95 encounters. hl_check.cjs (the revision's walk) on the two synthetic walk
documents (255e92ac..., gi-02, a PDF with real Fable citations; 6c450473..., gi-01, a text): the first run failed
honestly - the copy's files volume held no originals, so every view answered 409 and both viewers said the document
could not be downloaded; with those two synthetic originals copied from live's files volume (mounted read-only, each
sha256 equal to the database's), four runs judged the marks the same way every time: gi-02 15 of 15 marked once with
both redraws judged, gi-01 17 of 17 marked once, GET requests only besides the sign-in and sign-out POSTs, no violation,
no page error. Three of the four passed outright; the third failed only at its sign-out, whose navigation was cut short
(net::ERR_ABORTED) after the POST had gone. hl_check now judges a cut-short sign-out by its outcome (GET /api/session
must answer 401 or 403); the two runs after that change signed out normally and passed. Its database footprint, counted
table by table: studio_loginattempt +1 per run, nothing else.

**The switch-back rehearsal on that copy**: rehearse_j.sh switchback 7dd8130050773f57c98dd48dfa6c128d4fd20292 on that
copy, as the installer runs it: the stack stopped; the candidate's UNDO_HAZARDS_READ {} and TOUCHED_SINCE_READ [];
CLOSE_STAGES closed 0 (no job, no run, no round touched); the installed image's UNRUNNABLE_STAGES stuck 0 and
PUT_BACK_STATES changed {} for the 6 coded encounters; the installed image's own API read every encounter as the
customer: the list 200 and all 95 details 200; forward again, the candidate's RECOMPUTE_STATES changed {}; the encounter
states identical before, after the put-back and after forward (awaiting_answer 2, extraction_failed 1,
needs_clarification 47, no_codes 4, ready 2, ready_for_review 8, reviewed 31); rounds done 6. Then torn down: the copy
dropped, its files volume (with the two copied originals) removed.

**Offline predictions** (highlight-20261120/install/predict_h.sh on a throwaway restore of a fresh read-only dump of
live, in the revision's test image): 2026-11-21T09:01Z, cpt-studio-test:0de2b5844857 (sha256:4dd341903e78...): dump
09:01:36Z (sha256 dca51f9d68ad6ac5..., 48 TABLE DATA); schema 16 migrations, last 0016_fable_coding, before and after;
migrate in the candidate image applied nothing; UNRUNNABLE_STAGES stuck 0; V1_ROWS none; INSTALL_COUNTS encounters 95 (6
coded); RECOMPUTE_STATES changed {} (6 coded encounters, 89 kept); no table delta at all; states awaiting_answer 2,
extraction_failed 1, needs_clarification 47, no_codes 4, ready 2, ready_for_review 8, reviewed 31. The throwaway
database and its files volume were dropped.

## Baseline (read-only, `2026-11-21T09:31:57Z`; re-read immediately before the commit that lands this declaration; this act's preflight receipt and pre_app_h.sh are binding)

    bash /home/claude/cpt-studio-completion-20261106/gemini-migration/install-judge/live_baseline_j.sh
    bash scripts/check-cotenants.sh
    docker ps -a --filter label=org.quillmd.cpt-studio=1 --format '{{.Names}} {{.Image}} {{.Status}} {{.Ports}}'
    docker image inspect cpt-studio:7dd813005077 --format '{{.Id}} {{index .Config.Labels "org.opencontainers.image.revision"}}'

    read_at 2026-11-21T09:31:57Z
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
    login_attempts 118
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
    last_audit decision.recorded 2026-11-21T03:11:07Z 22850
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

    # docker ps -a --filter label=org.quillmd.cpt-studio=1; docker image inspect cpt-studio:7dd813005077
    cpt-studio-worker b72e426037fd Up 21 hours 8000/tcp
    cpt-studio-web b72e426037fd Up 21 hours (healthy) 127.0.0.1:9150->8000/tcp
    cpt-studio-db postgres:17.11-alpine Up 6 days 127.0.0.1:55451->5432/tcp
    sha256:b72e426037fde7420194247a79b4d04cb691c75ecdbf49c7411d79ef79458095 7dd8130050773f57c98dd48dfa6c128d4fd20292

## Expected changes, per phase

- **preflight:** none. Its receipt records the baseline: the quillmd-cpt vhost as this installer's HTTPS stage for 9150
  (sha256 259b895dd1307e81b8fbcb5439874477daf71eba63c9b996b3bdfc572bf71a0c); 9150 held by cpt-studio-web alone and 9151
  free; no cpt-studio-web-next; co-tenant routing and https://app.quillmd.com/health/.
- **image:** a new local image cpt-studio:`0de2b5844857`, built from git archive of the revision's cpt-studio/ and
  labelled with the revision. Its Dockerfile and requirements are 7dd813005077's, so the apt and pip layers come from
  the cache; the test image of the same revision built as cpt-studio-test:0de2b5844857 (sha256:4dd341903e78...), its
  migration safety all safe and its manage check clean. cpt-studio:7dd813005077 is kept.
- **Before app, read-only on the database** (pre_app_h.sh): one `pg_dump -Fc` through the database container's own
  pg_dump in a read-only transaction, 48 TABLE DATA entries; a restore on the test server migrated with the
  revision's test image, where nothing applies; the baseline re-read equals the declared one, with no job active, no run
  reserved or sending, and no audit event newer than 10 minutes. Its log ends "PRE-APP PASS"; act_h.sh's app phase
  requires it.
- **app (the blue/green switch):** **migrate applies nothing**; UNRUNNABLE_STAGES finds none; V1_ROWS none;
  INSTALL_COUNTS as the prediction; S1 cpt-studio-web-next starts on 127.0.0.1:9151 and answers /health/ with the
  revision; S2 the old worker parked; S3 the vhost's proxy_pass switched 127.0.0.1:9150 to 127.0.0.1:9151 (sha256
  259b895d... to f816a27de9e64af51d6a905484e22fdfc5f13a941a246931261bfc0df1e3ca65), `nginx -t` clean, graceful reload,
  https://cpt.quillmd.com/health/ serving the revision, the co-tenants unchanged; S4 the new worker starts with the
  coding step live, as the live worker does; S5 the old web drained, stopped and parked; S6 RECOMPUTE_STATES changes
  nothing (6 coded encounters, 0 changed, 89 kept: combine() and the stored rounds are untouched by this release). The
  receipt names the replaced pair (7dd813005077's web and worker), which a switch-back returns to.
- **verify:** nothing changes.

**Database deltas after app, against the baseline:** none from the install: every count and every encounter's stored
state unchanged. Rows written by members in the window are their own and are named if they appear.

## After the install: the view-only check (ordinary use, not a phase)

highlight-20261120/install/hl_check.cjs (sha256 ba96d6bce7e95e8a5a4c62e48ca3defc16b649d67e121e21d74d5f174789962d, the
copy the rehearsal's last two runs used), using the revision's ops/walk.cjs, against https://cpt.quillmd.com with the
review-agent account, on the previous install's two synthetic walk documents of 2026-11-20 (gi-02, a PDF with real Fable
citations; gi-01). It signs in through the form, opens each document, chooses every quote, and judges the marks with the
walk's own reader and judge. It makes no request but GET, apart from the sign-in and sign-out POSTs: anything else, or
any request leaving the origin, fails the check. A sign-out whose navigation is cut short is judged by its outcome (GET
/api/session must answer 401 or 403). Its database rows, measured in the rehearsal, are studio_loginattempt +1 (its one
sign-in) and nothing else, counted table by table. No real document is opened.

## Must not change

Every encounter and every row of every table apart from the check's sign-in row (studio_loginattempt +1); the accounts,
memberships, workspace, reference sources, facts and passages; the database container and its volumes; /etc/cpt-studio/;
the co-tenants' HTTP answers and https://app.quillmd.com/health/; every other nginx vhost; every image (nothing is
removed).

## Validation per phase

Each receipt is read before the next phase: preflight exit 0 with the baseline above; image exit 0 with the image id
recorded; pre_app_h.sh ending PRE-APP PASS; app exit 0 with migrate applying nothing, the counts as declared, the switch
applied and https://cpt.quillmd.com/health/ serving the revision; verify exit 0. After app: post_check_h.sh against
this declaration's deltas; scripts/check-cotenants.sh; then the view-only check and post_check_h.sh again with its rows.

## Rollback per phase, and its limits

- preflight, verify: nothing to undo.
- image: nothing to undo.
- app before the switch: the installer's own undo stops the incoming web and restarts the parked worker.
- app after the switch: the installer's own undo switches back on failure. After a successful app, the incident path is
  `switch-back` (a fresh preflight, then act_h.sh switch-back with SWITCH_BACK_DECISION recorded). The 7dd813005077 pair
  returns with its own modes. Both revisions are the Fable coding build with the same schema, so no coding job is closed
  and no state changes (measured on the copy: no hazard, nothing closed, the states unchanged). Members lose only the
  highlight.
- The receipts, the pre-app dump and the images stay.

## What is not claimed

- Marks on documents beyond those measured; on scanned pages (no searchable text, so nothing is marked, and the note
  says so).
- Form-field values and annotation text are outside the searchable text.
- Browsers below the floor mark nothing (the fallback); Firefox and Safari were not run locally (Chromium only; the
  floor comes from measured features and MDN data).
- Any coding change: none is in this release.
- Past the known limits written in cpt-studio/CORE-UX-DESIGN.md section 8 (and the walk's, section 9): among them a page
  printed by a web browser is searched in the order the browser drew it, a superscript digit typed as a character is a
  word part, letter-spaced text loses its word edges, and a text frame whose load never ends is waited for in silence.

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
