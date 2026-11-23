# Prospective declaration: the admin dashboard at cpt.quillmd.com/ops (3ce5383ce485 to 2894cda36322), installed blue/green with the site kept serving: no migration, no new dependency, the operator console in the new design with people and roles, workspaces, spending and activity

Authority: the owner's direction of 2026-11-22 recorded verbatim, with this programme's interpretation (a)-(d), in
docs/foundation/rulings/2026-10-23-cpt-studio-gi.md (its D395 section, landed with the change in PR #1512) and a
RULINGS.md row:

- D395: "i rather to hold on for now just release the admin dashbaord from the new design i need admi ndashbaord to
  control everything strat only for admin dashboard"; the controls chosen, verbatim: "People and roles, Workspaces,
  Spending and usage, Activity log"; the address chosen, verbatim: "Build now, move later (Recommended)" - the console
  released at cpt.quillmd.com/ops first, admin.quillmd.com later in a release of its own that changes the QuillMD checks
  expecting a notice there. Interpretation (d): "just release" is the owner's direction to install it by the standing
  process.

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

Revision to install: `2894cda36322968ea5dd612876a85d25c0011613`, the merge commit of PR #1512 (branch feat/cpt-studio-admin-console-20261122, head
`4bba9467427f93e0fb145c4515b4801f5e04ead1`; its tree e3f6dc5d828f291c6e5a4fdb09771161db6282b7 equals the head's; its first parent fc916bb8b81b, main before the merge, carries nothing under cpt-studio/ since the live revision). Image tag cpt-studio:`2894cda36322`. Its citation, on the revision: `CI 45108957893, cpt-studio 45108957970 and secrets-scan 45108957993, each completed success, read by commit (full sha) and by branch (main), twice, 2026-11-23`. The PR head's
citation: `CI 45106442968, cpt-studio 45106442960 and secrets-scan 45106442913, each completed success, read by commit and by branch`. cpt-studio is not a required check; it is required here.

It replaces the live revision 3ce5383ce485c39339a839d1f8f8468c41ef9a53 (image cpt-studio:3ce5383ce485, id
sha256:9486d0bfd11149e7e87bf0781228c4ef62fad4f01999e0a822c1bf4b6bcd677c, its web on 127.0.0.1:9150 since that install's switch on 2026-11-22), installed under
docs/foundation/mutations/20261122-cpt-studio-neuro-ortho-install.md (PR #1510, 72ee24965821). That image is kept as the
rollback image (switch-back). That declaration and its receipts stay as they are.

Execute each phase separately through scripts/run-ruled-mutation.sh with `RULED_ACT_MAX_SECS=9000`, as
`python3 -B cpt-studio/ops/install.py --phase PHASE --revision 2894cda36322968ea5dd612876a85d25c0011613 --receipts /home/claude/cpt-studio-install-20261023`
plus each phase's fixed arguments (cpt-admin-console-20261122/release/act_a.sh: the Neurosurgery and Orthopedic Surgery
release's act_n.sh with this release's names and without its provisioning phases).

Phases, in this order:
1. preflight;
2. image;
3. app, with `--coding-mode live --authorization-ref docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`, the modes
   the live pair runs with;
4. verify.

act_a.sh refuses any REV other than this declaration's "Revision to install", a second run of a changing phase, and app
without pre_app_a.sh's log ending PRE-APP PASS written after preflight and image, or with the newest preflight log or the
image log not ending exit 0. The installer gives the web and the
worker the same coder settings as the live pair (the revision's settings.py defaults: effort max, the 25 US dollar
per-document ceiling, 4 documents at once).

Run them from a clean, detached checkout of the merge commit that lands this declaration
(/opt/meddoc-pro/.worktrees/cpt-admin-console-act-20261123). That commit must be a descendant of the revision that
changes nothing under cpt-studio/, scripts/run-ruled-mutation.sh or scripts/lib/. Read each receipt before the next
phase.

Not run: secrets, db, reference, passages, license-note, operators, provision, http-vhost, cert, https-vhost,
rollback-vhost, rollback-app and switch-back. switch-back is the incident path (below). No document is sent by the
install.

Between 3ce5383ce485c39339a839d1f8f8468c41ef9a53 and the revision, these are byte-identical
(`git diff --quiet 3ce5383ce485c39339a839d1f8f8468c41ef9a53 2894cda36322968ea5dd612876a85d25c0011613 -- <these paths>: exit 0, 2026-11-23; 29 pathspecs covering 84 files`):
the migrations (still 0016_fable_coding, the last), models.py, the whole coding path (studio/fable/, jobs.py, intake.py,
state.py, decisions.py, storage.py), the customer surface (customer.py, api.py, client_contract.py, views.py, access.py,
audit.py, templates/studio/index.html and login.html, static/studio/app.js, styles.css and lib/), the export path
(exports.py, physician_report.py, physician_pdf.py and every font file in report_fonts/), the management commands,
cptstudio/settings.py, deploy/ (the Dockerfile), ops/install.py and the requirements.
These change, and are named here (27 files): studio/console.py (new: the console's controls), studio/spend.py (new:
one reading of a run's cost for every console page; display only, and nothing on the coding path reads it),
cptstudio/urls.py (its eleven routes under /ops/), studio/operator.py (the Encounters list and an encounter's run cards
read their cost through spend.run_spend - a run still being sent, of unknown outcome or not priceable has no known cost
and is flagged, a run only reserved reads "nothing sent yet" - and each page names its section for the navigation;
display only), the operator templates (ops_base.html, ops_index.html and ops_encounter.html restyled, every form and
field kept, the cost cells worded by that one reading; ops_people.html, ops_people_rows.html, ops_add_person.html,
ops_password.html, ops_workspaces.html, ops_workspace.html, ops_spending.html, ops_activity.html new),
studio/static/studio/fonts/ (new: byte-identical copies of four report fonts and their two OFL texts),
studio/report_fonts/PROVENANCE.md (a note on the copies; no font changes), ops/walk.cjs and ops/test_walk.cjs (the gate
probes the new paths and a member's own ids), the tests (tests/test_admin_console.py new) and the docs
(ARCHITECTURE.md, CORE-UX-DESIGN.md); outside cpt-studio/, docs only (docs/foundation/RULINGS.md,
docs/foundation/rulings/2026-10-23-cpt-studio-gi.md). Positive control for the byte-identity command: the same
`git diff --quiet` on cpt-studio/studio/operator.py exits 1.

Before preflight the operator runs, in the act's checkout:
- `git diff --quiet 3ce5383ce485c39339a839d1f8f8468c41ef9a53 HEAD -- cpt-studio/studio/migrations cpt-studio/studio/models.py cpt-studio/studio/fable cpt-studio/studio/jobs.py cpt-studio/studio/intake.py cpt-studio/studio/state.py cpt-studio/studio/decisions.py cpt-studio/studio/storage.py cpt-studio/studio/customer.py cpt-studio/studio/api.py cpt-studio/studio/client_contract.py cpt-studio/studio/views.py cpt-studio/studio/access.py cpt-studio/studio/audit.py cpt-studio/studio/templates/studio/index.html cpt-studio/studio/templates/studio/login.html cpt-studio/studio/static/studio/app.js cpt-studio/studio/static/studio/styles.css cpt-studio/studio/static/studio/lib cpt-studio/studio/exports.py cpt-studio/studio/physician_report.py cpt-studio/studio/physician_pdf.py ':(glob)cpt-studio/studio/report_fonts/*.ttf' ':(glob)cpt-studio/studio/report_fonts/OFL*.txt' cpt-studio/studio/management cpt-studio/cptstudio/settings.py cpt-studio/deploy cpt-studio/ops/install.py ':(glob)cpt-studio/requirements*.txt'`, exit 0;
- `git diff --name-only 3ce5383ce485c39339a839d1f8f8468c41ef9a53 HEAD -- cpt-studio/studio/migrations`, printing nothing;
- `git diff --name-only 2894cda36322968ea5dd612876a85d25c0011613 HEAD -- cpt-studio scripts/run-ruled-mutation.sh scripts/lib`, printing nothing.

Any other difference is a stop.

**The deploy range against held declarations** (docs/DEPLOYMENT_RUNBOOK.md 2.5; install-judge/held_check_j.sh with this
range): `install-judge/held_check_j.sh 3ce5383ce485c39339a839d1f8f8468c41ef9a53 2894cda36322968ea5dd612876a85d25c0011613, 2026-11-23: the range's first-parent merges are #1512, #1511 and #1510; 23 runtime files, all under cpt-studio/; positive control (deploy-prod.sh named by 66 files) passed; 8 declarations and reports name a runtime file of the range, and every revision each names is an ancestor of the running revision; possibly held: 0`.

## Delta shipped (3ce5383ce485 to the revision)

**This is a TREE, not one change**, but its only runtime change is the admin dashboard: the range carries #1512 (this change) and #1510 and #1511 (the Neurosurgery and Orthopedic Surgery release's declaration and install report, docs only).

- The operator console at /ops/ takes the design of 2026-11-22 (ink, paper and citron; Manrope and IBM Plex Mono served
  by the site itself from static/studio/fonts/; a navigation bar and a sign-out). The Encounters page and an encounter's
  record keep every form, field and record; their layout changed, and their cost cells now read one rule with the
  Spending page (a run with no known cost yet is flagged and counted apart, never as zero; a run only reserved reads
  "nothing sent yet").
- People (/ops/people): every membership with role, access and last sign-in; the operators, read-only; add a person to
  one workspace (one login, one workspace), reset a password, change a membership's role (an automated agent is never
  made an owner), turn access off and on (is_active; every stored session of the person is ended at once). A new or
  reset password is generated, checked against the site's validators, stored as its hash and shown once in the POST's
  own answer. No act changes an operator's account or records or ends a grant. Nothing is deleted but sign-in state.
- Workspaces (/ops/workspaces): each with its specialty, people and documents; a new one for an existing category,
  under provisioning's lock, its name stored exactly as typed in the Western European Latin letters, digits, single
  spaces and . , ' & - / ( ), naming no other specialty and reading alike no other workspace (case, accents, modifier
  letters and punctuation aside); a workspace's page with its people.
- Spending (/ops/spending): sent coding runs priced by jobs.run_cost (the console's own figures) by UTC day, workspace
  and document; a run in flight, of unknown outcome or not priceable counted apart at its worst case; the owner's two
  figures shown, not changed.
- Activity (/ops/activity): every audit event in plain words, newest first, by workspace and kind, paged by position;
  every sign-in attempt, a name that is no account not shown.
- Every console act is audited in the workspace it concerns (operator.member_added, operator.role_changed,
  operator.password_reset, operator.access_off, operator.access_on, operator.workspace_created); those rows name no
  encounter, so the customer's activity never shows them.

## What the owner and members see after the install

- The owner, as the platform operator: https://cpt.quillmd.com/login/ with the account platform-operator (its password
  is in /etc/cpt-studio/operator-credentials.json, root-only, from the operators phase of 2026-11-05) opens /ops/ in the
  new design with the four new areas.
- Members: nothing changes - the doctor's page, the review, the approvals and the PDF report are byte-identical code.
  Every /ops/ path still answers them exactly as an unknown URL (404).

## Cost and time

No paid request. The image build reuses the cached apt and pip layers (the Dockerfile and requirements are unchanged)
and rebuilds the application layers: on this host the revision's test image, built the same way from the cached layers, took about 6 seconds (testinst/build_image.sh, started 05:03:07Z; reh_a.sh began 05:03:13Z). The app phase takes about 3 minutes (the blue/green switch; the
worker's stop bound).

## Measured before this declaration

**The full gate** (scripts/ci/verify-cpt-studio.sh on the revision's tree): on the PR head 4bba94674 (its tree e3f6dc5d828f is the revision's tree), with the CI interpreter, on a clean tree: Django suite 702 tests OK (1 skipped), ops 538 OK, verification 37 OK, walk node tests 97 of 97, pip-audit "No known vulnerabilities found"; exit 0 (cpt-admin-console-20261122/logs/gate-final.log).

**The refutation of the finished diff**: seven rounds of read-only lenses over the finished diff, each told to refute and to show a concrete input and the wrong output, every finding re-demonstrated by its own verifier before it was believed: round 1, four lenses (the gate, data and secrets, the money figures, the restyle), 22 findings, among them sessions surviving access off, a password typed as a username shown on the sign-ins page and in-flight runs priced from partial usage (repaired in 2f825286a); round 2, two lenses on the repairs, 9 (2 medium: two money figures for one run, Unicode-equivalent workspace names; 04c0e68af); round 3, 10 (1 medium; c6b441eb4); round 4, 7 (1 medium; 1e0ccfa30); round 5, 3 (1 medium; cd16862b5); round 6, 8 (2 medium; 0c9e36efd), after which the workspace name rule became a closed one; round 7 on that rule, 3 (1 medium: modifier letters and one combining mark in names provisioning stored; 4bba94674). No high finding in seven rounds; all 62 findings repaired and pinned by a test, or written down as a limit. The console is not on the coding path (D358); the pass ran because the change carries money figures, credentials and sessions (DECISIONS D395).

**The install rehearsal on a restored copy of live**, every output on file (cpt-admin-console-20261122/release/
reh-2894cda36322-20261123T050313Z/, reh_a.sh): reh_a.sh, with the package as it is committed here, began 2026-11-23T05:03:13Z with a fresh read-only dump of live (sha256 04f4c86195f827d7, 05:03:16Z) restored as cptg_jreh_20261123t050313z, the revision's test image cpt-studio-test:2894cda36322 on 127.0.0.1:9371 with every provider mode and coding disabled (migrate applied nothing; 97 encounters). console_check_a.py WITHOUT --acts, exactly as on live: 35 checks and 36 requests passed - every console page, the workspace and encounter pages with the frame, the four fonts, the session ended after the sign-out, and the member's 404 on every console page, on the workspace page, the encounter page and its stored original by their real ids (the original's probe graded hard: the encounter page links it), and on the console's own acts. Its footprint, over every table's exact row count (48 tables), the sessions, every account's last sign-in, the encounter states and the password digest: studio_auditevent 1493 to 1494 (operator.viewed 130 to 131), studio_loginattempt 128 to 130, the last sign-in of ops-agent and review-agent; nothing else (the sessions 110 before and after). Then console_check_a.py --acts: 43 checks and 63 requests passed, every act among them (a workspace, a person, their sign-in, the role, access off and on, the password reset), and the copy's deltas were exactly the acts' rows: studio_user, studio_membership and studio_workspace +1 each (the acts' Rehearsal workspace and rehearsal-person, reviewer), the audit events operator.workspace_created, member_added, role_changed, access_off, access_on and password_reset (studio_auditevent +6), studio_loginattempt +7, the password digest (the new account and its reset), three last sign-ins; nothing else. The switch-back to cpt-studio:3ce5383ce485 and forward again: no stage closed, PUT_BACK_STATES and RECOMPUTE_STATES changed nothing, and the previous revision read all 97 encounters 200 as the customer. The same rehearsal with the package before its review ran on the PR head 4bba94674 and the earlier heads, every check passing.

**The release package's review** (this declaration, act_a.sh, pre_app_a.sh, post_check_a.sh, baseline_a.sh,
declare_baseline_a.sh, console_check_a.py, reh_a.sh, fill_decl.py and the evidence, before this commit):
two rounds of read-only lenses told to refute, each on a sealed copy of the package and the revision's tree (cpt-admin-console-20261122/release-review/dispositions-r1.md and dispositions-r2.md). Round 1, two lenses: 13 findings, 7 distinct (2 medium: the declared baseline's file mode, which pre_app_a.sh would have refused between image and app; the app arm not reading how the newest preflight and the image ended), every one repaired - the app arm demands both logs ended exit 0, the live check frames the workspace and encounter pages and probes the member with real ids, the rehearsal measures the check's footprint without --acts, post_check_a.sh proves its baseline is this declaration's block, retire_parked is declared - each repair self-tested on synthetic inputs. Round 2, one lens on the repairs: 3 findings, none a regression (1 medium: the mode repair was still a procedure, now declare_baseline_a.sh, which writes the 0600 baseline and derives the expected-deltas file from it; 2 low: the fill substitutes in one pass and refuses a value holding a marker, and the original's member probe is graded soft when the encounter links no stored original), every one repaired and self-tested. No high finding in either round.

## Baseline (read-only, `2026-11-23T05:04:46Z`; re-read immediately before the commit that lands this declaration; this act's preflight receipt and pre_app_a.sh are binding)

Read with these commands, all read-only (the SQL is SELECT only, in a read-only transaction, through the database
container's own psql; counts, names and states only, never a document, response or credential):

    bash /home/claude/cpt-admin-console-20261122/release/declare_baseline_a.sh   (baseline_a.sh under umask 077, and the rest)
    bash scripts/check-cotenants.sh
    docker ps -a --filter label=org.quillmd.cpt-studio=1 --format '{{.Names}} {{.Image}} {{.Status}} {{.Ports}}'
    docker image inspect cpt-studio:3ce5383ce485 --format '{{.Id}} {{index .Config.Labels "org.opencontainers.image.revision"}}'

baseline_a.sh is install-judge/live_baseline_j.sh unchanged plus this release's rows: every category, every workspace,
every membership (account, category, workspace, role, active), one sha256 digest over every account's username and
password hash (no hash is printed), every operator grant and the audit events by name.

    read_at 2026-11-23T05:04:46Z
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
    audit_events 1493
    reports 209
    jobs 661
    jobs_active 0
    users 9
    memberships 7
    workspaces 3
    login_attempts 128
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
    last_audit account.provisioned 2026-11-22T11:23:08Z 63698
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
    audit_event operator.viewed 130
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
    cpt-studio-worker 9486d0bfd111 Up 18 hours 8000/tcp
    cpt-studio-web 9486d0bfd111 Up 18 hours (healthy) 127.0.0.1:9150->8000/tcp
    cpt-studio-db postgres:17.11-alpine Up 8 days 127.0.0.1:55451->5432/tcp
    --- image
    sha256:9486d0bfd11149e7e87bf0781228c4ef62fad4f01999e0a822c1bf4b6bcd677c 3ce5383ce485c39339a839d1f8f8468c41ef9a53

## Expected changes, per phase

- **preflight:** none. Its receipt records the baseline: the quillmd-cpt vhost as this installer's HTTPS stage for
  9150; 9150 held by cpt-studio-web alone and 9151 free; no cpt-studio-web-next; co-tenant routing
  and https://app.quillmd.com/health/.
- **image:** a new local image cpt-studio:`2894cda36322`, built from git archive of the revision's cpt-studio/ and labelled
  with the revision. The image phase's gate (Django check; the WSGI import) passes. cpt-studio:3ce5383ce485 is kept.
- **Before app, read-only on the database** (pre_app_a.sh): the declared baseline file, release/act/baseline-a-declared-20261123T050446Z.txt (mode 0600, which
  pre_app_a.sh demands; written by declare_baseline_a.sh), equals, exactly, the baseline part of this declaration's Baseline block (its read_at line up to the co-tenants reading); one `pg_dump -Fc` in a
  read-only transaction, 48 TABLE DATA entries; a restore on the test server migrated with the revision's image, where
  nothing applies; the baseline re-read equals the declared one (read_at, the last audit and the sign-in count aside),
  with no job active, no run reserved or sending, no run unreconciled, no reading job queued or running, and no audit
  event newer than 10 minutes. Its log ends "PRE-APP PASS"; act_a.sh's app phase requires it.
- **app (the blue/green switch):** **migrate applies nothing**; S1 cpt-studio-web-next starts on 127.0.0.1:9151
  and answers /health/ with the revision; S2 the old worker parked; S3 the vhost's proxy_pass switched to
  127.0.0.1:9151 (ops/install.py's vhost code is unchanged), `nginx -t` clean, graceful reload,
  https://cpt.quillmd.com/health/ serving the revision, the co-tenants unchanged; S4 the new worker starts with the
  coding step live, as the live worker does; S5 the old web drained, stopped and parked; S6 RECOMPUTE_STATES changes
  nothing, and the parked web and worker of 3ce5383ce485 are removed (retire_parked; their image is kept, and a
  switch-back recreates the pair from it). The receipt names the replaced pair, which a switch-back returns to.
- **verify:** nothing changes.

**Database deltas against the baseline:** after app and verify, none: every count, every account, membership,
workspace, operator grant, audit event count and the password-hash digest unchanged. post_check_a.sh (DECL_FILE the
committed declaration in the act checkout; it refuses a declared baseline that is not this Baseline block) judges both
directions and exits non-zero on any finding, on /health/ not answering status ok, database ok and the revision, or on
a co-tenant change; a non-zero exit stops the act until it is judged, listing every audit event since the baseline's
last one. A member's own activity in the window is named in the report, and the act continues; anything else is THE
finding.

## After the install: the console check (ordinary use, not a phase)

cpt-admin-console-20261122/release/console_check_a.py, with the act checkout's ops/verify_login.py for its transport,
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
No act is posted on live. Its database footprint, exactly: studio_loginattempt +2 (set aside by the comparison and named
here); last_login set on ops-agent and review-agent; two session rows created and deleted by the sign-outs; audit_event
operator.viewed +1 (the encounter page read; 130 to 131 on the rehearsal copy, beside studio_auditevent 1493 to 1494, studio_loginattempt +2 and the two last sign-ins, the sessions 110 before and after); nothing else - measured on the rehearsal copy by a run
without --acts, exactly as on live, with every table's exact row count, the sessions, every account's last sign-in, the
encounter states and the password digest compared before and after. post_check_a.sh runs once more after it with
release/act/expected-after-check-20261123T050446Z.txt (derived from the declared baseline by declare_baseline_a.sh: audit_events 1493 1494; audit_event operator.viewed 130 131).

## Must not change

Every encounter and every row of every table apart from the check's rows above; every account, membership, workspace,
category and operator grant, and every password hash (the digest); the decisions, coding rounds, exports, reference
sources, facts and passages; the database container and its volumes; every file in /etc/cpt-studio/; the co-tenants'
HTTP answers and https://app.quillmd.com/health/; every other nginx vhost; every image (nothing is removed).

## Validation per phase

Each receipt is read before the next phase: preflight exit 0 with the baseline above; image exit 0 with the image id
recorded; pre_app_a.sh ending PRE-APP PASS; app exit 0 with migrate applying nothing, the switch applied and
https://cpt.quillmd.com/health/ serving the revision; verify exit 0; post_check_a.sh after verify with no
expected-deltas file: exit 0, 0 unexpected; the console check passing; post_check_a.sh again with
release/act/expected-after-check-20261123T050446Z.txt: exit 0, 0 unexpected; scripts/check-cotenants.sh.

## Rollback per phase, and its limits

- preflight, verify, image: nothing to undo.
- app before the switch: the installer's own undo stops the incoming web and restarts the parked worker.
- app after the switch: the installer's own undo switches back on failure. After a successful app, the incident path is
  `switch-back` (a fresh preflight, then act_a.sh switch-back with SWITCH_BACK_DECISION recorded). The 3ce5383ce485 pair
  returns with its own modes. Both revisions share the schema, so no coding job is closed and no state changes; rows
  the new console wrote (accounts, memberships, workspaces, audit events) are plain rows the previous revision reads
  (rehearsed: on the copy, after the acts, the switch-back closed no stage and changed no state, and the previous revision read all 97 encounters 200 as the customer). Under the previous revision the console is the old two pages again.
- The receipts, the pre-app dump and the images stay; the parked containers do not (retire_parked), and a switch-back
  recreates them from cpt-studio:3ce5383ce485.

## What is not claimed

- The move to admin.quillmd.com (a later release of its own, with the QuillMD checks that expect a notice there).
- That the console's acts were used on live: they are rehearsed on a restored copy only; the owner uses them.
- That a server provisioning run keeps a role the console changed on the owner account it provisioned (provision
  promotes its workspace owner back to Owner when it runs; written limit).
- That the console takes a workspace name in another script, or Polish, Czech, Turkish or Vietnamese letters (refused;
  provisioning can still make such a workspace), or compares look-alike letters of other scripts in a name provisioning
  stored, or letters a font draws alike within its own set (I, l and 1; O and 0): written limits, in
  cpt-studio/ARCHITECTURE.md.
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
