# Prospective declaration: admin.quillmd.com moved onto CPT Studio (3d7c589261bd to 6ab8e503a400), release 2 of the admin.quillmd.com move: the cpt-studio certificate, the ingress (two nginx files under one coupling invariant) and a blue/green app, with QuillMD's co-tenant check taught both states

Authority: the owner's direction of 2026-11-23 recorded verbatim, with this programme's interpretation (a)-(e), in
docs/foundation/rulings/2026-10-23-cpt-studio-gi.md (its D396 section, landed with release 1 in PR #1515) and a
RULINGS.md row:

- D396: "Not Found The requested resource was not found on this server. i seen this errro on the specefic url you told
  me to check bhut no problem jsut move to admin.quillmd.com and lemme walk into live one", under D392's "also admin
  dashbaord is repalce to admin.quillmd.com" (the authority to replace QuillMD's notice on that name) and D395's "Build
  now, move later". Interpretation (b): admin.quillmd.com must open the sign-in page and then the console, with no
  unexplained 404; (c): two releases, as the design refutation required (workflow wf_75dbe414-b35). Release 1 (the app
  answers the admin host; installed 2026-11-23 under docs/foundation/mutations/20261123-cpt-studio-admin-host-app-install.md)
  is live; this is release 2. The release goes by the standing process.

It stands on the standing directions this install keeps:
- D358: nothing here touches the coding path. The coding review, its instructions, the decisions, the approval rules,
  the customer API and the doctor's page are untouched (the application code is byte-identical to release 1's).
- The 2026-10-23 directive (a protected synthetic demonstration; app.quillmd.com and unrelated services preserved):
  QuillMD's vhost changes in one line only - its :443 server_name loses admin.quillmd.com - and every QuillMD host keeps
  its answer and its certificate.
- D360's install conditions: no unresolved critical or high finding; every suite green; CI green on the merged commit;
  this declaration committed before the act; the rehearsal on a restored copy of live passed; preflight not BLOCK; the
  act only through the door; a check on the live site afterwards; a report either way.

The integration and deployment owner is session `738699b2`. CPT Studio stays standalone and synthetic-only. No purchase,
agreement, key or payment change is part of this act, and no paid request is made by it; the certificate is one order
to Let's Encrypt on the host's one existing ACME account (free). No account, password or workspace is created by the
install.

Revision to install: `6ab8e503a40050c08c01c965441fa56583fb5e03`, the merge commit of PR #1518 (head `19938d109adc1332f3411144bb6f0ecf3d6bc6ae`; its tree equals the head's (git diff --quiet 19938d109 6ab8e503 exits 0); its first parent fb125ed38d6b, main before the merge, carries nothing under cpt-studio/ or scripts/ since the live revision but release 1's two documents). Image tag cpt-studio:`6ab8e503a400`.
Its citation, on the revision: `CI 45193463059, cpt-studio 45193463092 and secrets-scan 45193463097 on 6ab8e503a40050c08c01c965441fa56583fb5e03, each completed success, read by commit (full sha) and by branch (main, filtered to the sha), twice, 2026-11-23`. The PR head's citation: `CI 45189446076, cpt-studio 45189446282 and secrets-scan 45189446113, each completed success, read by commit and by branch`. cpt-studio is not a required
check; it is required here.

It replaces the live revision 3d7c589261bd3370a3f1178de1f03c3bef98334e (image cpt-studio:3d7c589261bd, id
sha256:5f440b960f8b80b1ac733f895bf37570cd44b41256c4047b61f5cf66701e054b, its web on 127.0.0.1:9150 since release 1's switch on 2026-11-23), installed under
docs/foundation/mutations/20261123-cpt-studio-admin-host-app-install.md (PR #1516, 5ee9cbbddfb1). That image is kept as
the rollback image (switch-back). That declaration and its receipts stay as they are.

Execute each phase separately through scripts/run-ruled-mutation.sh with `RULED_ACT_MAX_SECS=9000`, as
`python3 -B cpt-studio/ops/install.py --phase PHASE --revision 6ab8e503a40050c08c01c965441fa56583fb5e03 --receipts /home/claude/cpt-studio-install-20261023`
plus each phase's fixed arguments (cpt-admin-host-20261123/release2/act_i.sh: release 1's act_h.sh, reviewed and used,
with this release's names, phases and order).

Phases, in this order:
1. preflight;
2. image;
3. cert;
4. ingress;
5. preflight again (TAG after-ingress): the post-ingress baseline the app's checks compare against;
6. app, with `--coding-mode live --authorization-ref docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`, the modes
   the live pair runs with;
7. verify.

act_i.sh refuses any REV other than this declaration's "Revision to install"; a second run of a changing phase, unless
the first's failure is proven twice - its log records the door's non-zero exit, and the installer's own receipt written
inside that run says ok false - and RERUN_DECISION records the decision in words (then only after a preflight newer than
the failed run, whose log is kept as act-i-<phase>.attempt-<n>.log; a phase that ended exit 0, or whose end is unknown,
never runs again through it); image without a
preflight that ended exit 0, cert without the image log ending exit 0, ingress without the cert log ending exit 0, and
app without image, cert and ingress logs ending exit 0, a preflight after ingress ending exit 0, and pre_app_i.sh's log
ending PRE-APP PASS written after it; app after an ingress-rollback that ended exit 0 (the move undone); switch-back or
ingress-rollback without its own recorded decision in words and a preflight newer than every changing phase that ran, a
switch-back and an ingress-rollback included; and, after a successful app, ingress-rollback before a switch-back that ended exit 0. The installer gives the web and the worker the same coder
settings as the live pair.

Run them from a clean, detached checkout of the merge commit that lands this declaration
(/opt/meddoc-pro/.worktrees/cpt-admin-host-ingress-act-20261123). That commit must be a descendant of the revision that
changes nothing under cpt-studio/, scripts/run-ruled-mutation.sh, scripts/lib/ or scripts/check-cotenants.sh. Read each
receipt before the next phase.

Not run: secrets, db, reference, passages, license-note, operators, provision, http-vhost, https-vhost, rollback-vhost
and rollback-app. switch-back and ingress-rollback are the incident paths (below). No document is sent by the install.

Between 3d7c589261bd3370a3f1178de1f03c3bef98334e and the revision, the application is byte-identical
(`git diff --quiet 3d7c589261bd3370a3f1178de1f03c3bef98334e 6ab8e503a40050c08c01c965441fa56583fb5e03 -- <these paths>: exit 0, 2026-11-23`): everything under cpt-studio/ but the four paths named below (271 files): the application (studio/, cptstudio/, the templates, the static files, the migrations - still 0016_fable_coding, the last - the management commands, the coding path, the customer surface, the export path), the Dockerfile, the requirements, deploy/nginx/cpt-quillmd-http.conf (the :80 stage), ops/verify_login.py and every other ops/ tool and its tests.
These change, and are named here: cpt-studio/ops/install.py (the cert phase for a served site and the cpt-studio lineage; the ingress and ingress-rollback phases and the root helper's couple and decouple; the coupling invariant with the quillmd vhost's two pinned states, read as nginx loads quillmd-cpt; the own-host checks, revision-aware; the co-tenant check told the installer's own host), cpt-studio/deploy/nginx/cpt-quillmd-https.conf (one :443 block for both hosts, the 444 and 421 guards, Host $host, the cpt-studio certificate), cpt-studio/ops/INSTALL.md and the installer's tests (test_install.py, test_install_admin_host.py new, test_install_bluegreen.py, test_install_r3.py); outside cpt-studio/, QuillMD's scripts/check-cotenants.sh (the skip, redirect-aware expectations, admin's two states), scripts/verify-post-reboot.sh and tests/automated/monitoring/uptime-check.sh (admin's expected answer 503 to 302, ruling D395(c)) and scripts/check-ingress-tls.sh (a comment), and this range's three documents (release 1's declaration and report, and the rulings' D396 note): 14 paths in all (git diff --name-status 3d7c589261bd 6ab8e503a400). Positive control for the byte-identity command: the same
`git diff --quiet` on cpt-studio/ops/install.py exits 1.

Before preflight the operator runs, in the act's checkout:
- `git diff --quiet 3d7c589261bd3370a3f1178de1f03c3bef98334e HEAD -- 'cpt-studio' ':(exclude)cpt-studio/ops/install.py' ':(exclude)cpt-studio/ops/INSTALL.md' ':(exclude,glob)cpt-studio/ops/test_install*.py' ':(exclude)cpt-studio/deploy/nginx/cpt-quillmd-https.conf'`, exit 0;
- `git diff --name-only 3d7c589261bd3370a3f1178de1f03c3bef98334e HEAD -- cpt-studio/studio/migrations`, printing nothing;
- `git diff --name-only 6ab8e503a40050c08c01c965441fa56583fb5e03 HEAD -- cpt-studio scripts/run-ruled-mutation.sh scripts/lib scripts/check-cotenants.sh`,
  printing nothing.

Any other difference is a stop.

**The deploy range against held declarations** (docs/DEPLOYMENT_RUNBOOK.md 2.5; install-judge/held_check_j.sh with this
range): `none - install-judge/held_check_j.sh 3d7c589261bd..6ab8e503a400: first-parent merges #1516, #1517 and #1518; 5 runtime files (2 under cpt-studio/); the positive control passed (deploy-prod.sh named by 68 files); 33 declarations and reports name a runtime file of the range: 24 name full revisions, every one an ancestor of the running revision; 9 name none, so they were read: 7 QuillMD deploy declarations whose file names carry their commit (5020c68a, e1d55da3, d5b1380e, 49b66019, f00956ef, f46d828b, 087e4e40 - each an ancestor of the running revision), and QuillMD's two service-date mutation declarations of 2026-09-18 (the first act failed closed and the retry records it; the retry's migration core.0014_encounter_service_date is recorded applied in the baselines of the next two QuillMD acts that day, 20260918-quillmd-audio-submission.md and 20260918-quillmd-recording-repair.md; both declarations name scripts/check-cotenants.sh only as a check run before and after, not a file they ship). The tool itself stopped at the first declaration naming no full revision (grep's no-match under pipefail) until it was fixed to flag such a declaration for reading, 2026-11-23`.

## Delta shipped (3d7c589261bd to the revision)

**This is a TREE, not one change**: the range carries #1516 (release 1's declaration), #1517 (release 1's report) and #1518 (this release). Its runtime changes are the installer's and the web
front end's, and QuillMD's co-tenant check:

- **admin.quillmd.com** moves from QuillMD's maintenance notice (503, through QuillMD's Caddy) to CPT Studio's operator
  console: `/` answers 302 to /login/, /login/ the operator sign-in, an operator lands on the console, any other account
  is refused with the wrong-password sentence and no session; /api/session and every doctor page answer 404 there. The
  application has answered that host since release 1; this release routes it there.
- **The certificate**: a new lineage, cpt-studio, names exactly cpt.quillmd.com and admin.quillmd.com, and both names
  are served it. The cpt.quillmd.com lineage stays and keeps renewing, unused. QuillMD's quillmd.com lineage (which also
  names admin.quillmd.com) is not touched, and admin's HTTP-01 challenge for both lineages stays answered by QuillMD's :80
  block, which is unchanged.
- **QuillMD's vhost** changes in line 26 alone: `    server_name quillmd.com www.quillmd.com admin.quillmd.com;` becomes
  `    server_name quillmd.com www.quillmd.com;` (sha256 e9aa049d... to b3ab6602..., both pinned in the installer), under
  the coupling invariant with quillmd-cpt (ops/INSTALL.md): quillmd.com, www, app and pro keep their routes, answers and
  certificate. QuillMD's Caddy keeps its admin block, dormant: it is the way back (ingress-rollback).
- **cpt.quillmd.com** is unchanged for every visitor: the same application (byte-identical), the same routes; one server
  block now serves both names, a connection opened for either serves both, and a request for either on a connection
  opened for another QuillMD name is answered 421 (the browser retries on a fresh connection).
- **QuillMD's checks** (in this tree): scripts/check-cotenants.sh honours the installer's exact-host skip (admin.quillmd.com
  alone) and accepts admin's two deliberate states across the move - the 503 notice, matched by its text, or 302 to
  https://admin.quillmd.com/login/ - anything else red; scripts/verify-post-reboot.sh and
  tests/automated/monitoring/uptime-check.sh expect admin's 302 (ruling D395(c)). The shared tree's copies (/opt/meddoc-pro
  at c8b54991) predate them: until QuillMD's deploy surface is next brought to main, a run of those copies reports
  admin.quillmd.com 302 against their 503 - declared here, not a finding; the expectation table on main is the canonical
  one (ruling #265(d)). The uptime monitor (cron, from the shared tree) already reads app.quillmd.com DOWN on every run (a
  stale 503 row, reported before), so the move adds an admin line to an alert already standing. A follow-up PR narrows
  check-cotenants.sh's admin row to the console's state once the move is installed.

## What the owner and members see after the install

- The owner opens https://admin.quillmd.com/ : the operator sign-in. Signed in as platform-operator (its password is in
  /etc/cpt-studio/operator-credentials.json, root-only), the console opens: Encounters, People, Workspaces, Spending and
  Activity. https://cpt.quillmd.com/ops/ keeps working the same way.
- Members: nothing changes - the doctor's page, the review, the approvals and the PDF report are byte-identical code;
  admin.quillmd.com refuses a member's sign-in like a wrong password.
- QuillMD's visitors: nothing changes on quillmd.com, www.quillmd.com, app.quillmd.com or pro.quillmd.com.

## Cost and time

No paid request; one free certificate order. The image build reuses the cached layers: on this host the revision's test image, built the same way from the cached layers, took 7 seconds (testinst/build_image.sh, 14:22:38Z to 14:22:45Z). cert takes
about a minute, ingress under a minute (one reload), the app phase about 3 minutes (the blue/green switch; the worker's
stop bound).

## Measured before this declaration

**The full gate** (scripts/ci/verify-cpt-studio.sh on the revision's tree): on the PR head 19938d109 (its tree is the revision's when main has not moved), with the CI interpreter, on a clean tree: Django suite 722 tests OK (1 skipped), ops 615 OK, verification 37 OK, walk node tests 97 of 97, pip-audit "No known vulnerabilities found"; exit 0 (cpt-admin-host-20261123/logs/gate-r2b.log). The installer suite also ran with nginx's directories pointed nowhere, as on a CI runner (582 OK, 12 skipped).

**The design and the refutation**: a design refutation before any code (workflow wf_75dbe414-b35: it split the move into two releases); an independent read-only check of the build against the design (wf_57ddef66-e05: 29 of 33 design points implemented, 3 low defects repaired in 466dd309c); two refutation rounds of the finished diff, four distinct lenses each and a verifier per finding that reproduced it on its own copy before it was believed - round 1 (wf_48185258-02c): 20 findings, none high after verification, 9 medium, all repaired or documented (3b00e76ad; mutants R1-R13 caught and restored); round 2 on the repairs (wf_103e5dd6-0a4): 33 findings, none high, no medium regression, every one repaired or accepted with its reason (19938d109; mutants M1-M18 caught and restored) - the stopping rule met. Dispositions: cpt-admin-host-20261123/refute-r2b/dispositions.md.

**The install rehearsal on a restored copy of live**, every output on file (cpt-admin-host-20261123/release2/
reh-6ab8e503a400-20261123T182339Z/, reh_i.sh): reh_i.sh, with the package as it is committed here (the live check as repaired through the three rounds of its review, sha256 2af075e4f7eaf6dd), began 2026-11-23T18:23:39Z with a fresh read-only dump of live (sha256 79464172b52b81b1, 18:23:42Z) restored on the test server, the revision's test image cpt-studio-test:6ab8e503a400 on 127.0.0.1:9371 with every provider mode and coding disabled (migrate applied nothing; 97 encounters). console_check_i.py WITHOUT --acts and WITH --admin-walk - as on live, the walk on the loopback since the copy is not reached through the public path: 50 checks passed - the 35 of the cpt arm, the 10 loopback admin checks, the operator signing in on the admin host, reading the console and signing out (the replayed session sent to the sign-in), the member refused there with no session, and admin.arm_complete; 36 requests and 16 admin-host requests, all in the evidence. Its footprint over every table's exact row count (48 tables), the sessions, every account's last sign-in, the encounter states and the password digest: studio_auditevent 1495 to 1496 (operator.viewed 132 to 133), studio_loginattempt 133 to 137, the last sign-in of ops-agent and review-agent; nothing else. Then with --acts: 58 checks passed; no session left open. The switch-back to cpt-studio:3d7c589261bd and forward again: no stage closed, PUT_BACK_STATES and RECOMPUTE_STATES changed nothing, and the previous revision read all 97 encounters 200 as the customer. The public arm itself is proven on the HTTPS stand-in below; the cert and ingress phases are proven by the installer's suite (the real phases and the real root-helper code on temporary directories) - neither can be rehearsed on a copy. The three earlier rehearsals of the revision (14:22:45Z, dump 400b0fda9809289d, the live check before its review; 15:14:19Z, dump c3f28a6cf46c07c1, after its first round; 17:21:53Z, dump 1a2d3945f930c12c, after its second) gave the same counts and the same footprint.

**The live check's public arm, on a local HTTPS stand-in** (cpt-admin-host-20261123/release2/test-check/): console_check_i.py run in-process (test-check/run_https_cases.py) against a fake cpt site and an HTTPS fake of the public path (a synthetic CA; a certificate for exactly cpt.quillmd.com and admin.quillmd.com; every https connection to those two names sent to the fake, SNI and the host-name check unchanged; the sign-out's CSRF token checked as Django checks it): 20 cases, every one as its encoded expectation says. The correct path: 61 of 61 with --admin-public and --admin-walk, both passwords posted once each, no session left, no password in the output or the evidence. Each wrong edge fails and the walk sends no password to the admin host: QuillMD's certificate on admin, a certificate that verifies but also names app.quillmd.com, admin answered by a doctors' app, the own-origin rule missing, the public path naming another release (stopped before any request to the cpt site), a run error alone, a hard failure on the cpt arm. Each fault in the walk ends with every session it was given signed out and the sign-out proven, or a failing check that says which state the replay showed (still signed in, or unknown); the one declared exception is a sign-in whose answer is lost, listed in the evidence with its error.

**The release package's review** (this declaration, act_i.sh, pre_app_i.sh, post_check_i.sh, baseline_i.sh,
declare_baseline_i.sh, console_check_i.py, reh_i.sh, fill_decl.py and the evidence, before this commit):
three rounds on the sealed package, each with two read-only lenses (the act, the post-check, the runbook and this declaration; the live check) and a verifier per finding that reproduced it on its own copy before it was believed. Round 1 (workflow wf_d88a57fa-68f): 12 findings, no high, 2 medium - an incident path's freshness ignored the switch-back, and the printed byte-identity command did not parse in a shell - all repaired. Round 2, on those repairs (wf_c66e52c8-319): 12 findings, no high, 2 medium regressions - the app receipt's field was named wrongly, and a rerun could repeat a phase that had succeeded but lost its exit line - all repaired; a second run now needs its failure proven by its recorded exit and by the installer's own receipt. Round 3, on those (wf_40bf0a91-2f7): 13 findings, all low; the stopping rule (no high finding, no medium regression) is met, and each was repaired. Every repair is pinned by a mutant caught on the version it repaired; the final package passes a simulation of act_i.sh on a throwaway checkout whose stub door writes the installer's receipts (47 checks), the live check against HTTPS fakes with Django's CSRF rule (20 cases, each with its expected outcome encoded), the post-check's stage read with a stubbed docker port (6 combinations), and four rehearsals on restored copies of live. Dispositions: cpt-admin-host-20261123/release2-review/dispositions-pkg-r1.md, release2-review-r2/dispositions-pkg-r2.md and release2-review-r3/dispositions-pkg-r3.md. The package as reviewed and run (sha256, first 16): act_i.sh c6cad689cac33b5a, pre_app_i.sh 9748d5a32ce53859, post_check_i.sh 3608e142ea65f4be, console_check_i.py 2af075e4f7eaf6dd, baseline_i.sh fb6ae0e5f0d96fa5, declare_baseline_i.sh 5a0a3246ae365b02.

## Baseline (read-only, `2026-11-23T18:39:16Z`; re-read immediately before the commit that lands this declaration; this act's preflight receipt and pre_app_i.sh are binding)

Read with these commands, all read-only (the SQL is SELECT only, in a read-only transaction, through the database
container's own psql; counts, names and states only, never a document, response or credential):

    bash /home/claude/cpt-admin-host-20261123/release2/declare_baseline_i.sh   (baseline_i.sh under umask 077, and the rest)
    bash scripts/check-cotenants.sh
    docker ps -a --filter label=org.quillmd.cpt-studio=1 --format '{{.Names}} {{.Image}} {{.Status}} {{.Ports}}'
    docker image inspect cpt-studio:3d7c589261bd --format '{{.Id}} {{index .Config.Labels "org.opencontainers.image.revision"}}'

baseline_i.sh is install-judge/live_baseline_j.sh unchanged plus this release's rows: every category, every workspace,
every membership (account, category, workspace, role, active), one sha256 digest over every account's username and
password hash (no hash is printed), every operator grant and the audit events by name.

    read_at 2026-11-23T18:39:16Z
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
    audit_events 1495
    reports 209
    jobs 661
    jobs_active 0
    users 9
    memberships 7
    workspaces 3
    login_attempts 133
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
    last_audit operator.viewed 2026-11-23T11:07:53Z 27084
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
    audit_event operator.viewed 132
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
        🟢 admin.quillmd.com    503~QuillMD_administration_is_temporarily_unavailable,302>https://admin.quillmd.com/login/ 503
        🟢 pro.quillmd.com      410       410
    🟢 every judged co-tenant answers its expected status (4 distinct codes — the probe discriminates).
    --- containers
    cpt-studio-worker 5f440b960f8b Up 8 hours 8000/tcp
    cpt-studio-web 5f440b960f8b Up 8 hours (healthy) 127.0.0.1:9150->8000/tcp
    cpt-studio-db postgres:17.11-alpine Up 8 days 127.0.0.1:55451->5432/tcp
    --- image
    sha256:5f440b960f8b80b1ac733f895bf37570cd44b41256c4047b61f5cf66701e054b 3d7c589261bd3370a3f1178de1f03c3bef98334e
    --- ingress
    quillmd e9aa049d9190713b60e8243b56e082c3fe59e068c205e0d595407f7d08a97638
    quillmd-cpt 259b895dd1307e81b8fbcb5439874477daf71eba63c9b996b3bdfc572bf71a0c link /etc/nginx/sites-available/quillmd-cpt
    certificate admin.quillmd.com admin.quillmd.com app.quillmd.com pro.quillmd.com quillmd.com www.quillmd.com
    certificate cpt.quillmd.com cpt.quillmd.com
    certificate app.quillmd.com admin.quillmd.com app.quillmd.com pro.quillmd.com quillmd.com www.quillmd.com

## Expected changes, per phase

- **preflight:** none. Its receipt records the baseline: the coupling invariant's before state (the quillmd vhost
  e9aa049d..., quillmd-cpt this installer's HTTPS stage for 9150 behind its sites-enabled link, naming
  cpt.quillmd.com alone); 9150 held by cpt-studio-web alone and 9151 free; both names resolving to
  147.189.172.8 alone; admin's HTTP-01 route answering through QuillMD's :80 block; co-tenant routing (admin's :443
  left to the installer) and https://app.quillmd.com/health/; scripts/check-cotenants.sh honouring the skip.
- **image:** a new local image cpt-studio:`6ab8e503a400`, built from git archive of the revision's cpt-studio/ and labelled
  with the revision. The image phase's gate passes. cpt-studio:3d7c589261bd is kept.
- **cert:** one certbot run (webroot /var/www/certbot, the one existing ACME account, `--cert-name cpt-studio`, both
  names, no --expand) after both names' DNS and both challenge routes are proven. New: /etc/letsencrypt/live/cpt-studio/,
  archive/cpt-studio/ and renewal/cpt-studio.conf. Every other lineage's renewal conf unchanged (its digest compared)
  and its live directory still present (the directory names compared; no key material is opened), the ACME account set
  unchanged - the comparison cert and verify make, which sets both CPT lineages aside. The cpt.quillmd.com lineage (the
  way back's stage loads it) is not written by this run: certbot certonly --webroot with --cert-name cpt-studio and
  --keep-until-expiring, never --expand or a forced renewal; ingress-rollback refuses before any write when that
  stage's certificate files are missing. Nothing is served the new certificate yet.
- **ingress:** one root-helper operation (couple): quillmd-cpt becomes the revision's HTTPS stage for 9150 (the
  web serving, 3d7c589261bd, which answers the admin host: checked on its loopback port first), naming both hosts with
  the cpt-studio certificate, renamed first; the quillmd vhost becomes the pinned after state (line 26 alone), renamed
  second; nginx -t with no new warning; one reload; verified through the public path: admin.quillmd.com served the
  cpt-studio certificate, /api/session 404, GET and HEAD / 302 to /login/, the sign-in page and its static files 200;
  cpt.quillmd.com/health/ the live revision; 421 for either host on a connection opened for app.quillmd.com; each host
  served on the other's connection; co-tenant routing unchanged; both files read back. On any failure both files are
  written back (decouple). quillmd-cpt's sha256 after it: `d0e4fc5ca1ccec7dba52d237f9e639fef4e916f498ecca7ed51d521e21f6f7a5`
  (the revision's HTTPS stage for 9150, rendered before this declaration from the revision's template, as the
  installer renders it; the ingress receipt's vhost_sha256 must be it). Before the write it records nginx's warnings and writes its intent (receipts directory,
  intent-ingress-<stamp>.json, 0600: the stage it replaces, byte for byte), so a run killed between the write and its
  receipt is completed by a rerun; the receipt keeps the replaced stage byte for byte for ingress-rollback.
- **preflight again:** none; its receipt records the after state as the baseline.
- **Before app, read-only on the database** (pre_app_i.sh): as release 1's (the declared baseline file release2/act/baseline-i-declared-20261123T183916Z.txt
  equal to this Baseline block's database part; one pg_dump -Fc in a read-only transaction, 48 TABLE DATA; a restore on
  the test server migrated with the revision's image applying nothing; the baseline re-read equal; the gates); its log
  ends "PRE-APP PASS".
- **app (the blue/green switch, from 9150 to 9151: the receipt's details.ports):** **migrate applies nothing**; cpt-studio-web-next starts on 127.0.0.1:9151 and
  answers /health/ and the admin host's own answers on its loopback port (smoke_web); the old worker parked; quillmd-cpt
  replaced in place by the revision's HTTPS stage for 9151 (both names: the coupling stays after; the receipt's
  switch.vhost_sha_after `1672b98db8cfb9253b85187ce49bf483f47c636daae5138cadc995e5160a9bbf`, rendered the same way; its
  switch.vhost_sha_before and replacement.vhost_sha256 are the ingress's stage it replaced, d0e4fc5ca1cc...; an app
  receipt carries no top-level vhost_sha256), nginx -t clean, reload, both hosts serving the revision through the public path; the new worker starts; the old web drained,
  stopped and parked; RECOMPUTE_STATES changes nothing; the parked pair of 3d7c589261bd removed (its image kept). A
  second app (a recorded rerun, below) goes from the port the web then serves to the other: back to 9150 when the
  failure left the new pair serving (switch.vhost_sha_after d0e4fc5ca1cc..., the revision's stage for 9150), or to
  9151 again when the installer's own undo had switched back (1672b98db8cf...); both stages are named here.
- **verify:** nothing changes; it accepts the coupled after state and both CPT lineages.

**Database deltas against the baseline:** after app and verify, none. post_check_i.sh (DECL_FILE the committed
declaration in the act checkout) judges both directions, /health/, the co-tenants (the act checkout's script) and the
ingress read back (the quillmd vhost in its after pin, quillmd-cpt behind the installer's link naming both hosts on 443
and its sha256 the revision's stage for the port cpt-studio-web publishes - 9151 1672b98db8cf..., 9150
d0e4fc5ca1cc... -,
admin.quillmd.com and cpt.quillmd.com served the cpt-studio certificate, app.quillmd.com still QuillMD's,
https://admin.quillmd.com/ answering 302 to /login/), and exits non-zero on any finding.

## After the install: the live check (ordinary use, not a phase)

cpt-admin-host-20261123/release2/console_check_i.py (release 1's console_check_h.py, reviewed and used on live, with a
public arm and the operator's walk), with the act checkout's ops/verify_login.py, against https://cpt.quillmd.com, once,
WITHOUT --acts, with `--admin-loopback http://127.0.0.1:9151 --admin-release 6ab8e503a40050c08c01c965441fa56583fb5e03 --admin-public
https://admin.quillmd.com --admin-walk` (the loopback port is the one cpt-studio-web publishes, read with docker port
before the run: 9151 on the declared path). Before any request to cpt.quillmd.com it reads /health/ on the new web's
loopback and through https://admin.quillmd.com: unless both name the revision, the run stops (exit 1) with nothing asked
of cpt.quillmd.com and no evidence written (those /health/ reads the only requests made). Then release 1's two arms, unchanged: the cpt arm (the operator's console pages, fonts and
sign-out; the member's 404 on every console page and on the real ids; the console's own acts with ids that name nothing)
and the loopback admin arm (10 read-only checks). Then the public arm: https://admin.quillmd.com/health/ naming the
revision, its certificate carrying exactly cpt.quillmd.com and admin.quillmd.com (verified against the system trust store
and the host name), and the same read-only probes through the public path; then the walk: ops-agent signs in on
https://admin.quillmd.com/login/ (302 to /ops/, a session), reads /ops/people (200, the console), signs out (the
session replayed is sent to the sign-in), and review-agent's sign-in there is refused (400, no session). The walk runs
only when no hard check before it failed and the run has no error (a soft check's warning does not hold it), and the
member's sign-in only when the operator's part passed too, so the walk sends no password to the admin host after a hard
check failed (the cpt arm signs both accounts in on cpt.quillmd.com, as release 1's check does); a sign-in that gives no
session stops the walk there. A session the walk is given (the operator's, or a member's the refusal should never have
given) is signed out whatever fails after it, and a sign-out counts only when the session, replayed, is sent to the
sign-in. A close that is not proven is a failing check that says which state the replay showed: still signed in (200 for
the operator, 404 for a member on the admin host; the session stays open until it expires, 8 hours) or unknown (any
other answer, or none). A session whose sign-in answer is lost was never seen by the check and cannot be signed out by
it: the run fails and the evidence lists that request with its error.
The certificate's names are compared on the /health/ connection; every connection after it is verified against the
trust store and the host name. Every request is listed in the evidence before it is sent; a final check requires all 25
admin checks to have run.
No act is posted on live. Its database footprint, exactly: studio_loginattempt +4 (the cpt arm's two sign-ins and the
walk's two; set aside by the comparison and named here); last_login set on ops-agent and review-agent; three session rows
created and deleted by the sign-outs (after a fault mid-walk the check signs the session out and proves it, or
reports that it could not); audit_event operator.viewed +1 (the encounter page read; 132 to 133 on the rehearsal copy, beside studio_auditevent 1495 to 1496, studio_loginattempt +4 and the two last sign-ins, the sessions unchanged); nothing
else - measured on the rehearsal copy by the run that matches live (WITHOUT --acts, the walk on the loopback, since the
copy is not reached through the public path), with every table's exact row count, the sessions, every account's last
sign-in, the encounter states and the password digest compared before and after. post_check_i.sh runs once more after
it with release2/act/expected-after-check-20261123T183916Z.txt (derived from the declared baseline by declare_baseline_i.sh: audit_events 1495 1496; audit_event operator.viewed 132 133).

Then a follow-up PR (QuillMD's check only; no act): check-cotenants.sh's admin row narrowed to the console's state.

## Must not change

Every encounter and every row of every table apart from the check's rows above; every account, membership, workspace,
category and operator grant, and every password hash (the digest); the database container and its volumes; every file in
/etc/cpt-studio/; every nginx vhost but quillmd-cpt and the quillmd vhost's line 26; every other certificate lineage and
renewal conf (checked as cert and verify compare them: renewal confs by digest, live directories by name), and the ACME
account; QuillMD's :80 block, its Caddy and its containers; the HTTP answers and certificates
of quillmd.com, www.quillmd.com, app.quillmd.com and pro.quillmd.com, and https://app.quillmd.com/health/; every image
(nothing is removed).

## Validation per phase

Each receipt is read before the next phase: preflight exit 0, the coupling before, with the baseline above; image exit 0
with the image id recorded; cert exit 0 with the lineage's paths recorded and no other lineage's renewal conf or live directory changed; ingress exit
0, moved, with both quillmd shas and the replaced stage recorded, vhost_sha256 d0e4fc5ca1cc... and every public check
passing; preflight again exit 0,
the coupling after; pre_app_i.sh ending PRE-APP PASS; app exit 0 with migrate applying nothing, the switch applied (details.ports from 9150 to 9151),
switch.vhost_sha_after 1672b98db8cf... and both hosts serving the revision; verify exit 0; post_check_i.sh after verify with no expected-deltas file: exit 0, 0
unexpected, the ingress read back; the live check passing, its admin.arm_complete check included; post_check_i.sh
again with release2/act/expected-after-check-20261123T183916Z.txt: exit 0, 0 unexpected.

## Rollback per phase, and its limits

- preflight, verify, image: nothing to undo.
- cert: nothing to undo. A failed run leaves no lineage the ingress accepts. A lineage that is not used (the move
  abandoned) stays and renews; removing it is a deletion, not part of any rollback here.
- ingress before success: the installer's own undo writes both files back (decouple: the quillmd vhost first) and
  reloads; a run killed outright between the write and its receipt is completed by rerunning ingress (its intent). A
  killed run leaves no receipt, so act_i.sh will not repeat it: the rerun is decided by hand, after a fresh preflight,
  through the door with the same arguments act_i.sh prints in its log; until then no phase moves the stage. The act then
  stops before app: act_i.sh refuses app while act-i-ingress.log has no exit 0 line, so going on is decided under a new
  declaration, or the move is given back with ingress-rollback (which act_i.sh allows after a fresh preflight). After a successful ingress, the incident path is `ingress-rollback` (a fresh
  preflight, then act_i.sh ingress-rollback with INGRESS_ROLLBACK_DECISION recorded): it runs while the web the ingress
  found (3d7c589261bd) serves, before app at once; it requires QuillMD's Caddy to answer admin.quillmd.com with a
  deliberate state (its notice, or a 2xx/3xx) and the stage's certificate files (the cpt.quillmd.com lineage) present,
  then gives the quillmd vhost its before state and quillmd-cpt the saved stage byte for byte (or, on the other port,
  that revision's own stage rendered for it), and verifies admin back on Caddy's notice with QuillMD's certificate and
  cpt.quillmd.com serving. QuillMD's co-tenant row accepts both states, so nothing there is reverted unless the follow-up
  narrowing has landed (then a PR reverts it); the boot proof's and the uptime monitor's admin rows are reverted by a
  PR.
- app before the switch: the installer's own undo stops the incoming web and restarts the parked worker.
- app after the switch: the installer's own undo switches back on failure. After a successful app, the incident path is
  `switch-back` (a fresh preflight, then act_i.sh switch-back with SWITCH_BACK_DECISION recorded): the 3d7c589261bd pair
  returns on the idle port (9150 on the declared path) with its own modes, and it serves the admin host, so admin.quillmd.com keeps working; then, if
  the move itself is to be undone, a preflight newer than the switch-back and ingress-rollback as above (act_i.sh
  refuses ingress-rollback after a successful app until a switch-back has ended exit 0). Both revisions run the same application and schema
  (rehearsed: on the copy, after the acts, the switch-back to cpt-studio:3d7c589261bd closed no stage and changed no state, and that revision read all 97 encounters 200 as the customer).
- An older installer (a revision before this one) must not run any phase while admin.quillmd.com is moved (its
  preflight and vhost phases refuse; its rollback-app and app do not read the coupling): the way back to one is this
  revision's switch-back, then its ingress-rollback, then the older installer (ops/INSTALL.md, Reinstalling an older
  revision).
- A changing phase whose failure is proven twice (its log records the door's non-zero exit, and the installer's receipt
  written inside that run says ok false) runs again only through act_i.sh with RERUN_DECISION recorded in words, after a
  preflight newer than the failed run (for app, pre_app_i.sh again with TAG, as its own advice says); the failed run's
  log is kept as act-i-<phase>.attempt-<n>.log. A phase that ended exit 0 never runs again. A run whose end is unknown -
  no exit line (act_i.sh stopped while the installer ran on), no receipt (a killed installer), or a receipt saying ok -
  is never repeated by act_i.sh: it is a stop, its outcome read from the receipts and decided by hand.
- The receipts, the pre-app dump and the images stay; the parked containers do not (retire_parked).

## What is not claimed

- That the renewal of the cpt-studio lineage has run: it renews with the host's certbot timer and deploy hook like every
  lineage; the first renewal is about 60 days out, and nothing here watches it (a known limit in ops/INSTALL.md).
- That admin's HTTP-01 route stays: it is QuillMD's :80 block (line 13 of its vhost), unchanged here and watched only by
  this installer's preflight, cert, ingress and verify (a known limit in ops/INSTALL.md).
- That the shared tree's copies of QuillMD's checks agree before QuillMD's deploy surface is next brought to main (see
  Delta shipped).
- That every recovery path after a kill was exercised on this host: the intent, the completion and the ordered refusals
  are proven by the installer's suite (the real phases and the real root-helper code on temporary directories) and by
  mutation proofs, not by a kill on live.
- That every session the live check is given ends with it: a session whose sign-in answer is lost is never seen by the
  check and expires after 8 hours (the run fails); one whose sign-out cannot be proven is reported as such.
- That a server provisioning run keeps a role the console changed on the owner account it provisioned (written limit).
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
- quillmd.com, www.quillmd.com, app.quillmd.com or pro.quillmd.com changing its answer or certificate, or
  app.quillmd.com's health; admin.quillmd.com answering anything but its declared states (QuillMD's notice and
  certificate before the ingress; after it, the console's 302 to /login/ with the cpt-studio certificate).
- The live check failing: judged, then reported. A defect found there is fixed and installed under a new declaration,
  or the move is rolled back. It is never patched in place.
