# Prospective declaration: the admin host in the app (2894cda36322 to 3d7c589261bd), release 1 of the admin.quillmd.com move, installed blue/green with the site kept serving: no migration, no new dependency, no change to the web front end; admin.quillmd.com stays routed to QuillMD's notice until release 2

Authority: the owner's direction of 2026-11-23 recorded verbatim, with this programme's interpretation (a)-(e), in
docs/foundation/rulings/2026-10-23-cpt-studio-gi.md (its D396 section, landed with the change in PR #1515) and a
RULINGS.md row:

- D396: "Not Found The requested resource was not found on this server. i seen this errro on the specefic url you told
  me to check bhut no problem jsut move to admin.quillmd.com and lemme walk into live one", under D392's "also admin
  dashbaord is repalce to admin.quillmd.com" and D395's "Build now, move later". Interpretation (c): two releases, as a
  design refutation before any code required (workflow wf_75dbe414-b35) - this one teaches the app the admin host with
  no change to the web front end, so release 2 moves admin.quillmd.com onto an app that already answers it and a switch
  back from release 2 lands on a revision that answers admin. The release goes by the standing process.

It stands on the standing directions this install keeps:
- D358: nothing here touches the coding path. The coding review, its instructions, the decisions, the approval rules,
  the customer API and the doctor's page are untouched.
- The 2026-10-23 directive (a protected synthetic demonstration; app.quillmd.com and unrelated services preserved).
- D360's install conditions: no unresolved critical or high finding; every suite green; CI green on the merged commit;
  this declaration committed before the act; the rehearsal on a restored copy of live passed; preflight not BLOCK; the
  act only through the door; a check on the live site afterwards; a report either way.

The integration and deployment owner is session `738699b2`. CPT Studio stays standalone and synthetic-only. No purchase,
agreement, key or payment change is part of this act, and no paid request is made by it. No account, password or
workspace is created by the install: the console's acts are the owner's to use afterwards.

Revision to install: `3d7c589261bd3370a3f1178de1f03c3bef98334e`, the merge commit of PR #1515 (branch feat/cpt-studio-admin-host-20261123, head
`fc5b528e4c10e39982c61da96385462f20b07056`; its tree 0d0ba9a255c70ed1d8658a9068501cbedc9d88e5 equals the head's; its first parent abd64e64e504, main before the merge, carries nothing under cpt-studio/ since the live revision). Image tag cpt-studio:`3d7c589261bd`. Its citation, on the revision: `CI 45149819630, cpt-studio 45149819620 and secrets-scan 45149819817, each completed success, read by commit (full sha) and by branch (main), twice, 2026-11-23`. The PR head's
citation: `CI 45145637657, cpt-studio 45145637894 and secrets-scan 45145637686, each completed success, read by commit and by branch`. cpt-studio is not a required check; it is required here.

It replaces the live revision 2894cda36322968ea5dd612876a85d25c0011613 (image cpt-studio:2894cda36322, id
sha256:2b65b45cfab6f5af38ab47933833589f14346bcd7496088fee7d91cffeba76fa, its web on 127.0.0.1:9151 since that install's switch on 2026-11-23), installed under
docs/foundation/mutations/20261123-cpt-studio-admin-console-install.md (PR #1513, de9d703242b2). That image is kept as the
rollback image (switch-back). That declaration and its receipts stay as they are.

Execute each phase separately through scripts/run-ruled-mutation.sh with `RULED_ACT_MAX_SECS=9000`, as
`python3 -B cpt-studio/ops/install.py --phase PHASE --revision 3d7c589261bd3370a3f1178de1f03c3bef98334e --receipts /home/claude/cpt-studio-install-20261023`
plus each phase's fixed arguments (cpt-admin-host-20261123/release/act_h.sh: the admin dashboard release's act_a.sh,
reviewed in two rounds, with this release's names).

Phases, in this order:
1. preflight;
2. image;
3. app, with `--coding-mode live --authorization-ref docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`, the modes
   the live pair runs with;
4. verify.

act_h.sh refuses any REV other than this declaration's "Revision to install", a second run of a changing phase, and app
without pre_app_h.sh's log ending PRE-APP PASS written after preflight and image, or with the newest preflight log or the
image log not ending exit 0. The installer gives the web and the
worker the same coder settings as the live pair (the revision's settings.py defaults: effort max, the 25 US dollar
per-document ceiling, 4 documents at once).

Run them from a clean, detached checkout of the merge commit that lands this declaration
(/opt/meddoc-pro/.worktrees/cpt-admin-host-act-20261123). That commit must be a descendant of the revision that
changes nothing under cpt-studio/, scripts/run-ruled-mutation.sh or scripts/lib/. Read each receipt before the next
phase.

Not run: secrets, db, reference, passages, license-note, operators, provision, http-vhost, cert, https-vhost,
rollback-vhost, rollback-app and switch-back. switch-back is the incident path (below). No document is sent by the
install.

Between 2894cda36322968ea5dd612876a85d25c0011613 and the revision, these are byte-identical
(`git diff --quiet 2894cda36322968ea5dd612876a85d25c0011613 3d7c589261bd3370a3f1178de1f03c3bef98334e -- <these paths>: exit 0, 2026-11-23; 27 pathspecs covering 82 files`):
the migrations (still 0016_fable_coding, the last), models.py, the whole coding path (studio/fable/, jobs.py, intake.py,
state.py, decisions.py, storage.py), the customer surface (customer.py, api.py, client_contract.py, access.py, audit.py,
templates/studio/index.html and login.html, static/studio/app.js, styles.css and lib/), the export path (exports.py,
physician_report.py, physician_pdf.py and every font file in report_fonts/), the management commands, deploy/ (the
Dockerfile, and deploy/nginx: the web front end's templates), ops/install.py and the requirements.
These change, and are named here (11 files): studio/hosts.py (new: the host middleware, the admin host's own-origin
rule, the signed-out redirect), cptstudio/urls_admin.py (new: the admin host's urlconf - the sign-in, the root and /ops
redirects, and the full urlconf's own console routes), studio/views.py (the admin host's views appended: admin_home,
admin_ops_slash, admin_login_view; login_view and every customer view unchanged), cptstudio/settings.py (ADMIN_HOST in
ALLOWED_HOSTS; the host middleware before CommonMiddleware), studio/operator.py (docstrings only), the templates
(ops_login.html new; ops_base.html gains an empty head block, a block around the navigation, the release line and the
sign-out - rendered exactly as before on every console page - the password input style and two sign-in layout rules),
ops/verification/customer-denylist.json (the admin_host pattern and two vectors), the tests (tests/test_admin_host.py new)
and the docs (ARCHITECTURE.md, CORE-UX-DESIGN.md); outside cpt-studio/, docs only: this change's
docs/foundation/RULINGS.md and docs/foundation/rulings/2026-10-23-cpt-studio-gi.md, and the previous release's declaration
and report (docs/foundation/mutations/20261123-cpt-studio-admin-console-install.md,
docs/deploy-reports/20261123-cpt-studio-2894cda3-install-and-live-check.md). Positive control for the byte-identity
command: the same `git diff --quiet` on cpt-studio/studio/views.py exits 1.

Before preflight the operator runs, in the act's checkout:
- `git diff --quiet 2894cda36322968ea5dd612876a85d25c0011613 HEAD -- cpt-studio/studio/migrations cpt-studio/studio/models.py cpt-studio/studio/fable cpt-studio/studio/jobs.py cpt-studio/studio/intake.py cpt-studio/studio/state.py cpt-studio/studio/decisions.py cpt-studio/studio/storage.py cpt-studio/studio/customer.py cpt-studio/studio/api.py cpt-studio/studio/client_contract.py cpt-studio/studio/access.py cpt-studio/studio/audit.py cpt-studio/studio/templates/studio/index.html cpt-studio/studio/templates/studio/login.html cpt-studio/studio/static/studio/app.js cpt-studio/studio/static/studio/styles.css cpt-studio/studio/static/studio/lib cpt-studio/studio/exports.py cpt-studio/studio/physician_report.py cpt-studio/studio/physician_pdf.py ':(glob)cpt-studio/studio/report_fonts/*.ttf' ':(glob)cpt-studio/studio/report_fonts/OFL*.txt' cpt-studio/studio/management cpt-studio/deploy cpt-studio/ops/install.py ':(glob)cpt-studio/requirements*.txt'`, exit 0;
- `git diff --name-only 2894cda36322968ea5dd612876a85d25c0011613 HEAD -- cpt-studio/studio/migrations`, printing nothing;
- `git diff --name-only 3d7c589261bd3370a3f1178de1f03c3bef98334e HEAD -- cpt-studio scripts/run-ruled-mutation.sh scripts/lib`, printing nothing.

Any other difference is a stop.

**The deploy range against held declarations** (docs/DEPLOYMENT_RUNBOOK.md 2.5; install-judge/held_check_j.sh with this
range): `install-judge/held_check_j.sh 2894cda36322968ea5dd612876a85d25c0011613 3d7c589261bd3370a3f1178de1f03c3bef98334e, 2026-11-23: the range's first-parent merges are #1515, #1514 and #1513; 8 runtime files, all under cpt-studio/; positive control (deploy-prod.sh named by 67 files) passed; 9 declarations and reports name a runtime file of the range, and every revision each names is an ancestor of the running revision; possibly held: 0`.

## Delta shipped (2894cda36322 to the revision)

**This is a TREE, not one change**, but its only runtime change is the admin host in the app: the range carries #1515 (this change) and #1513 and #1514 (the admin dashboard release's declaration and install report, docs only).

- Requests whose Host is admin.quillmd.com are answered from the admin host's own urlconf: `/` (an operator to /ops/,
  anyone else to /login/, every method), `/ops` (to /ops/), an operator-only sign-in at /login/ (any other account gets
  the wrong-password sentence, no session and a failed attempt on the shared throttle), /logout/, /health/, and the
  console's own routes (any signed-out request goes to the sign-in; every signed-in account that is not an operator meets
  the gate's 404). No doctor app and no API answer there. An unsafe request whose Origin or Referer is not the admin host
  itself is refused (403) before any view; Django's global CSRF_TRUSTED_ORIGINS (cpt.quillmd.com) never applies there.
- Nothing routes admin.quillmd.com to the app yet: the web front end still sends it to QuillMD's Caddy notice (503), and
  only release 2 changes that. Until then the admin host is reached only on the loopback port, by this act's checks.
- cpt.quillmd.com is unchanged: every page, the doctor app, the API, the sign-in, and /ops/ for operators.

## What the owner and members see after the install

- Nothing changes in public. admin.quillmd.com still shows QuillMD's notice until release 2. The owner keeps signing in
  at https://cpt.quillmd.com/login/ as platform-operator (its password is in /etc/cpt-studio/operator-credentials.json,
  root-only), which opens the console as before.
- Members: nothing changes - the doctor's page, the review, the approvals and the PDF report are byte-identical code, and
  every /ops/ path on cpt.quillmd.com still answers them exactly as an unknown URL (404).

## Cost and time

No paid request. The image build reuses the cached apt and pip layers (the Dockerfile and requirements are unchanged)
and rebuilds the application layers: on this host the revision's test image, built the same way from the cached layers, took about 5 seconds (testinst/build_image.sh, started 10:09:30Z; reh_h.sh began 10:09:35Z). The app phase takes about 3 minutes (the blue/green switch; the
worker's stop bound).

## Measured before this declaration

**The full gate** (scripts/ci/verify-cpt-studio.sh on the revision's tree): on the PR head fc5b528e4 (its tree 0d0ba9a255c7 is the revision's tree), with the CI interpreter, on a clean tree: Django suite 722 tests OK (1 skipped), ops 538 OK, verification 37 OK, walk node tests 97 of 97, pip-audit "No known vulnerabilities found"; exit 0 (cpt-admin-host-20261123/logs/gate-final.log).

**The refutation of the finished diff**: a design refutation before any code (workflow wf_75dbe414-b35: three lenses, five high findings against a one-release design, which split it into two releases), then two rounds of read-only lenses over the finished diff, each told to refute and to show a concrete input and the wrong output, every finding re-demonstrated by its own verifier before it was believed: round 1, three lenses (the gate, the operator door, regressions), 9 findings, 6 distinct, 1 medium (the operator door's throttle untested), repaired in 925e2d46e (among them: the admin host now trusts only its own origin, since Django's global CSRF_TRUSTED_ORIGINS names cpt.quillmd.com); round 2, two lenses (the repairs, fresh eyes), 8 findings, all low but one test-quality medium (the grant sweep did not reach the acts' bodies), repaired in fc5b528e4. Neither round found a way for an account that is not an operator to reach console data or an act through either host. Six mutants each fail their tests.

**The install rehearsal on a restored copy of live**, every output on file (cpt-admin-host-20261123/release/
reh-3d7c589261bd-20261123T103519Z/, reh_h.sh): reh_h.sh, with the package as it is committed here, began 2026-11-23T10:35:19Z with a fresh read-only dump of live (sha256 8adb50b2ce28bb37, 10:35:21Z) restored as cptg_jreh_20261123t103519z, the revision's test image cpt-studio-test:3d7c589261bd on 127.0.0.1:9371 with every provider mode and coding disabled (migrate applied nothing; 97 encounters). console_check_h.py WITHOUT --acts, exactly as on live, with --admin-loopback http://127.0.0.1:9371 and --admin-release the revision: the loopback's /health/ read first, then 46 checks passed - the 35 of the cpt arm (every console page with the frame, the four fonts, the session ended, the member's 404 on every console page and on the real ids), the 10 admin-host checks (the web on the loopback reporting the revision; / and HEAD / to /login/; /api/session 404 with cpt's 401 the control; the operator sign-in page; the signed-out redirect; /ops to /ops/; PUT /login/ and POST /ops/people/add with a valid CSRF token and Origin https://cpt.quillmd.com refused 403 by the own-origin rule) and admin.arm_complete; 36 requests and 11 admin-host requests, all in the evidence, none failed. Its footprint over every table's exact row count (48 tables), the sessions, every account's last sign-in, the encounter states and the password digest: studio_auditevent 1494 to 1495 (operator.viewed 131 to 132), studio_loginattempt 131 to 133, the last sign-in of ops-agent and review-agent; nothing else - the admin probes wrote no row. Then with --acts: 58 checks passed, 63 requests and 16 admin-host requests - the operator signing in on the admin host, reading the console and signing out (the replayed session sent to the sign-in), and the member refused there with no session, beside every console act on cpt; no session left open. The switch-back to cpt-studio:2894cda36322 and forward again: no stage closed, PUT_BACK_STATES and RECOMPUTE_STATES changed nothing, and the previous revision read all 97 encounters 200 as the customer. The PR head fc5b528e4 and the package before each review round rehearsed the same way.

**The release package's review** (this declaration, act_h.sh, pre_app_h.sh, post_check_h.sh, baseline_h.sh,
declare_baseline_h.sh, console_check_h.py, reh_h.sh, fill_decl.py and the evidence, before this commit):
two rounds of one read-only lens each, told to refute, on a sealed copy of the package, the previous release's reviewed package and the revision's tree (cpt-admin-host-20261123/release-review/dispositions-r1.md and dispositions-r2.md). Round 1, what differs from the reviewed package: 6 findings (1 medium, latent: --acts was refused by --base-url only, so the new admin arm given a live loopback could have signed the real accounts in on live - now refused unless --admin-loopback is the rehearsal's too; 5 low: the arm optional and not required by the pass rule, a foreign-origin probe Django's own refusal could pass, the admin requests missing from the evidence, stale names, the changed-files sentence), every one repaired. Round 2, on the repairs: 5 findings, all low, 3 of them regressions of round 1's repairs (the valid-token sign-in probe would write a failed-attempt row were the own-origin rule missing - now a PUT the sign-in answers 405; the usage text; credentials accepted in --admin-loopback and the member's password checked in raw form only), and 2 more (a wrong loopback found only after the cpt arm had run on live - now refused before any request to live; a request whose answer was lost missing from the evidence), every one repaired and verified with the lens's own batteries: eleven malformed loopbacks refused with no request, a wrong or silent loopback stopping the run with nothing asked of live, a dropped request listed, an echoed password refused, and the revision served with live's flags passing all ten admin checks with the own-origin rule and failing both foreign-origin checks without it, every table unchanged either way. No high finding in either round.

## Baseline (read-only, `2026-11-23T10:37:03Z`; re-read immediately before the commit that lands this declaration; this act's preflight receipt and pre_app_h.sh are binding)

Read with these commands, all read-only (the SQL is SELECT only, in a read-only transaction, through the database
container's own psql; counts, names and states only, never a document, response or credential):

    bash /home/claude/cpt-admin-host-20261123/release/declare_baseline_h.sh   (baseline_h.sh under umask 077, and the rest)
    bash scripts/check-cotenants.sh
    docker ps -a --filter label=org.quillmd.cpt-studio=1 --format '{{.Names}} {{.Image}} {{.Status}} {{.Ports}}'
    docker image inspect cpt-studio:2894cda36322 --format '{{.Id}} {{index .Config.Labels "org.opencontainers.image.revision"}}'

baseline_h.sh is install-judge/live_baseline_j.sh unchanged plus this release's rows: every category, every workspace,
every membership (account, category, workspace, role, active), one sha256 digest over every account's username and
password hash (no hash is printed), every operator grant and the audit events by name.

    read_at 2026-11-23T10:37:03Z
    transaction_read_only on
    encounters 97
    revisions 98
    source_files 91
    contexts 106
    routing_runs 116
    provider_runs 303
    provider_runs_sent 267
    assessments 186
    proposals 2549
    clarifications 348
    decisions 63
    decision_invalidations 2
    audit_events 1494
    reports 209
    jobs 661
    jobs_active 0
    users 9
    memberships 7
    workspaces 3
    login_attempts 131
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
    run_participant anthropic coding_checker succeeded 8
    run_participant anthropic coding_reader succeeded 8
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
    encounter_state awaiting_answer 3
    encounter_state extraction_failed 1
    encounter_state needs_clarification 47
    encounter_state no_codes 4
    encounter_state ready 2
    encounter_state ready_for_review 8
    encounter_state reviewed 32
    run anthropic appraisal succeeded t f 4
    run anthropic coding_checker succeeded t f 8
    run anthropic coding_reader succeeded t f 8
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
    job code succeeded 8
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
    last_audit operator.viewed 2026-11-23T05:38:13Z 17930
    account demo-reviewer human t reviewer t
    account ops-agent agent t  
    account owner human t owner t
    account owner-neuro human t owner t
    account owner-ortho human t owner t
    account platform-operator human t  
    account review-agent agent t reviewer t
    account review-agent-neuro agent t reviewer t
    account review-agent-ortho agent t reviewer t
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
    current_context_by_version none 9
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
    studio_codinground 8
    studio_codinganswer 0
    studio_codedecision 11
    studio_exportartifact 13
    jobs_code succeeded 8
    runs_coding coding_checker succeeded 8
    runs_coding coding_reader succeeded 8
    interpreter_holds_standing 0
    categories 3
    category gastroenterology gi-profiles@3 present
    category neurosurgery fable-coding@1 present
    category orthopedic-surgery fable-coding@1 present
    workspace gastroenterology Gastroenterology present
    workspace neurosurgery Neurosurgery present
    workspace orthopedic-surgery Orthopedic_Surgery present
    member demo-reviewer gastroenterology Gastroenterology reviewer t
    member owner gastroenterology Gastroenterology owner t
    member owner-neuro neurosurgery Neurosurgery owner t
    member owner-ortho orthopedic-surgery Orthopedic_Surgery owner t
    member review-agent gastroenterology Gastroenterology reviewer t
    member review-agent-neuro neurosurgery Neurosurgery reviewer t
    member review-agent-ortho orthopedic-surgery Orthopedic_Surgery reviewer t
    password_hashes_digest 55943abb454109ca2e9d854b782c9590dc3ef610972bfd4e72859478131bdddd
    operator_grant ops-agent standing
    operator_grant platform-operator standing
    audit_event account.provisioned 7
    audit_event assessment.created 186
    audit_event assessment.recompute_queued 12
    audit_event assessment.refreshed 20
    audit_event coding.round_done 8
    audit_event coding.round_queued 8
    audit_event context.changed 17
    audit_event decision.recorded 74
    audit_event detail.answered 32
    audit_event detail.revoked 6
    audit_event encounter.created 97
    audit_event export.created 13
    audit_event operator.viewed 131
    audit_event pipeline.resumed 8
    audit_event pipeline.stopped 8
    audit_event provider.finished 267
    audit_event provider.reused 31
    audit_event provider.second_review_requested 2
    audit_event provider.sending 267
    audit_event report.generated 209
    audit_event revision.addendum 1
    audit_event revision.extracted 90
    --- co-tenants
        🟢 quillmd.com          200       200
        🟢 www.quillmd.com      200       200
        🟢 app.quillmd.com      302       302
        🟢 admin.quillmd.com    503       503
        🟢 pro.quillmd.com      410       410
    🟢 every co-tenant answers its expected status (4 distinct codes — the probe discriminates).
    --- containers
    cpt-studio-worker 2b65b45cfab6 Up 5 hours 8000/tcp
    cpt-studio-web 2b65b45cfab6 Up 5 hours (healthy) 127.0.0.1:9151->8000/tcp
    cpt-studio-db postgres:17.11-alpine Up 8 days 127.0.0.1:55451->5432/tcp
    --- image
    sha256:2b65b45cfab6f5af38ab47933833589f14346bcd7496088fee7d91cffeba76fa 2894cda36322968ea5dd612876a85d25c0011613

## Expected changes, per phase

- **preflight:** none. Its receipt records the baseline: the quillmd-cpt vhost as this installer's HTTPS stage for
  9151; 9151 held by cpt-studio-web alone and 9150 free; no cpt-studio-web-next; co-tenant routing
  and https://app.quillmd.com/health/.
- **image:** a new local image cpt-studio:`3d7c589261bd`, built from git archive of the revision's cpt-studio/ and labelled
  with the revision. The image phase's gate (Django check; the WSGI import) passes. cpt-studio:2894cda36322 is kept.
- **Before app, read-only on the database** (pre_app_h.sh): the declared baseline file, release/act/baseline-h-declared-20261123T103703Z.txt (mode 0600, which
  pre_app_h.sh demands; written by declare_baseline_h.sh), equals, exactly, the baseline part of this declaration's Baseline block (its read_at line up to the co-tenants reading); one `pg_dump -Fc` in a
  read-only transaction, 48 TABLE DATA entries; a restore on the test server migrated with the revision's image, where
  nothing applies; the baseline re-read equals the declared one (read_at, the last audit and the sign-in count aside),
  with no job active, no run reserved or sending, no run unreconciled, no reading job queued or running, and no audit
  event newer than 10 minutes. Its log ends "PRE-APP PASS"; act_h.sh's app phase requires it.
- **app (the blue/green switch):** **migrate applies nothing**; S1 cpt-studio-web-next starts on 127.0.0.1:9150
  and answers /health/ with the revision; S2 the old worker parked; S3 the vhost's proxy_pass switched to
  127.0.0.1:9150 (ops/install.py's vhost code is unchanged), `nginx -t` clean, graceful reload,
  https://cpt.quillmd.com/health/ serving the revision, the co-tenants unchanged; S4 the new worker starts with the
  coding step live, as the live worker does; S5 the old web drained, stopped and parked; S6 RECOMPUTE_STATES changes
  nothing, and the parked web and worker of 2894cda36322 are removed (retire_parked; their image is kept, and a
  switch-back recreates the pair from it). The receipt names the replaced pair, which a switch-back returns to.
- **verify:** nothing changes.

**Database deltas against the baseline:** after app and verify, none: every count, every account, membership,
workspace, operator grant, audit event count and the password-hash digest unchanged. post_check_h.sh (DECL_FILE the
committed declaration in the act checkout; it refuses a declared baseline that is not this Baseline block) judges both
directions and exits non-zero on any finding, on /health/ not answering status ok, database ok and the revision, or on
a co-tenant change; a non-zero exit stops the act until it is judged, listing every audit event since the baseline's
last one. A member's own activity in the window is named in the report, and the act continues; anything else is THE
finding.

## After the install: the console check (ordinary use, not a phase)

cpt-admin-host-20261123/release/console_check_h.py, with the act checkout's ops/verify_login.py for its transport,
against https://cpt.quillmd.com, once, WITHOUT --acts: as ops-agent (~/.cpt-studio/ops-agent-credentials.json; the
operator with no membership) it signs in (must land on /ops/), reads /ops/, /ops/people, /ops/workspaces, the first
workspace's page, /ops/spending, /ops/activity, /ops/activity/sign-ins and the newest encounter's page (each 200 with
the frame, the navigation and its heading; an Encounters page listing no encounter fails) and the four font files (200,
TrueType), signs out and proves the session ended; as Gastroenterology's review-agent
(~/.cpt-studio/agent-credentials.json) it signs in and gets 404 for every console page and for the workspace page and
the encounter page the operator read and that encounter's original, by their real ids (an open gate on the encounter
page would also write an operator.viewed row, which the post-check counts; the original's probe can fail only when the
encounter page links a stored original, and the check grades it soft and says so when it does not), and 404 for the
console's own acts posted with
ids that name nothing (an open gate there writes nothing); the encounter acts (reconcile, retry, release the holds) are
not posted on live, since an open gate there would act (tests/test_operator_console.py covers them). Then it signs out.
It is given --admin-loopback http://127.0.0.1:9150 and --admin-release 3d7c589261bd3370a3f1178de1f03c3bef98334e: the web the act installed, asked on
the loopback with Host admin.quillmd.com, since the front end does not route admin.quillmd.com to it yet. BEFORE any
request to https://cpt.quillmd.com it reads /health/ there: unless that names the revision, the run stops with nothing
asked of live and no evidence written (a malformed --admin-loopback, credentials in it included, is refused before any
request at all). After the two arms above it probes the admin host read-only: /health/ again (the arm stops if it names
another release); GET and HEAD / 302 to /login/; GET /api/session 404 (cpt.quillmd.com's 401 from the same web the
control); GET /login/ 200 with the operator sign-in; GET /ops/people 302 to /login/?next=%2Fops%2Fpeople; GET /ops 302 to
/ops/; then PUT /login/ and POST /ops/people/add, each carrying a valid CSRF token and cookie with Origin
https://cpt.quillmd.com - an origin Django's own check accepts - so each 403 comes from the admin host's own-origin rule,
before any view. No row is written by any of them, and none could be were that rule missing: the sign-in answers a PUT
405 and the console sends a signed-out POST to the sign-in (303) - measured on the revision served with live's flags,
with the rule removed, every table unchanged. Every admin request is listed in the evidence before it is sent (method,
host, path, then status and location), 11 on the loopback in all, and a final check requires all ten admin checks to
have run.
No act is posted on live. Its database footprint, exactly: studio_loginattempt +2 (set aside by the comparison and named
here); last_login set on ops-agent and review-agent; two session rows created and deleted by the sign-outs; audit_event
operator.viewed +1 (the encounter page read; 131 to 132 on the rehearsal copy, beside studio_auditevent 1494 to 1495, studio_loginattempt +2 and the two last sign-ins, the sessions unchanged; the admin probes wrote no row); nothing else - measured on the rehearsal copy by a run
without --acts, exactly as on live, with every table's exact row count, the sessions, every account's last sign-in, the
encounter states and the password digest compared before and after. post_check_h.sh runs once more after it with
release/act/expected-after-check-20261123T103703Z.txt (derived from the declared baseline by declare_baseline_h.sh: audit_events 1494 1495; audit_event operator.viewed 131 132).

## Must not change

Every encounter and every row of every table apart from the check's rows above; every account, membership, workspace,
category and operator grant, and every password hash (the digest); the decisions, coding rounds, exports, reference
sources, facts and passages; the database container and its volumes; every file in /etc/cpt-studio/; the co-tenants'
HTTP answers and https://app.quillmd.com/health/; every other nginx vhost; every image (nothing is removed).

## Validation per phase

Each receipt is read before the next phase: preflight exit 0 with the baseline above; image exit 0 with the image id
recorded; pre_app_h.sh ending PRE-APP PASS; app exit 0 with migrate applying nothing, the switch applied and
https://cpt.quillmd.com/health/ serving the revision; verify exit 0; post_check_h.sh after verify with no
expected-deltas file: exit 0, 0 unexpected; the console check passing, its admin.arm_complete check included;
post_check_h.sh again with
release/act/expected-after-check-20261123T103703Z.txt: exit 0, 0 unexpected; scripts/check-cotenants.sh.

## Rollback per phase, and its limits

- preflight, verify, image: nothing to undo.
- app before the switch: the installer's own undo stops the incoming web and restarts the parked worker.
- app after the switch: the installer's own undo switches back on failure. After a successful app, the incident path is
  `switch-back` (a fresh preflight, then act_h.sh switch-back with SWITCH_BACK_DECISION recorded). The 2894cda36322 pair
  returns with its own modes. Both revisions share the schema, so no coding job is closed and no state changes; rows
  the new console wrote (accounts, memberships, workspaces, audit events) are plain rows the previous revision reads
  (rehearsed: on the copy, after the acts, the switch-back closed no stage and changed no state, and the previous revision read all 97 encounters 200 as the customer). Under the previous revision the admin host's urlconf is gone; nothing public changes,
since the front end does not route admin.quillmd.com to the app before release 2.
- The receipts, the pre-app dump and the images stay; the parked containers do not (retire_parked), and a switch-back
  recreates them from cpt-studio:2894cda36322.

## What is not claimed

- admin.quillmd.com reaching the console in public: release 2 moves the web front end, with the QuillMD checks that
  expect a notice there; this release changes nothing a browser can see.
- That the admin host's sign-in was used on live: it is rehearsed on a restored copy only (the operator lands in the
  console, a member is refused); on live only its read-only probes run.
- That a server provisioning run keeps a role the console changed on the owner account it provisioned (provision
  promotes its workspace owner back to Owner when it runs; written limit).
- Past the known limits written in cpt-studio/ARCHITECTURE.md, API.md and ops/INSTALL.md, and in the refutation
  dispositions.

## Stop conditions

- Any phase exiting non-zero.
- A receipt or reading that differs from this declaration: a difference not declared here is THE finding, whatever its
  explanation - apart from a member's own activity, identified from the audit events and named in the report.
- migrate applying anything.
- An encounter's stored state changing in app.
- The citation not success in both views.
- A held declaration found.
- Preflight BLOCK, or the installer's preflight refusing.
- The door's ceiling reached.
- A co-tenant's or app.quillmd.com's answer changing.
- The console check failing: judged, then reported. A defect found there is fixed and installed under a new
  declaration, or the site is switched back. It is never patched in place.
