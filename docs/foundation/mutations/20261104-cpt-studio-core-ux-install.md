# Prospective declaration: CPT Studio core repair and customer interface at cpt.quillmd.com (41e03656df61 to 24c49a5032d5bb0185e5efda08ebe71f54a2845f), installed blue/green with the demo kept serving

Authority: the owner's directive of 2026-11-03 ("Implement the CPT Studio core repair and customer-interface
improvements below on https://cpt.quillmd.com. Complete the work through installation and verification."), recorded
verbatim in docs/foundation/rulings/2026-10-23-cpt-studio-gi.md with this session's interpretations (on receipt; after
mapping main and its completeness critique: decisions (a) to (m); during the integration: decisions (n) and (o)). Session a12d8fb3 is the integration and deployment
owner for that directive. The directive's install rule governs every phase here: "Keep the existing website and demo
accessible while you work. Do not pause the demo, introduce a maintenance page, or disable customer access as the
default approach." The install is also governed by the 2026-10-23 directive cited in
docs/foundation/mutations/20261023-cpt-studio-install.md: a protected synthetic demonstration, provider credentials
server-side, app.quillmd.com and unrelated services preserved. CPT Studio stays standalone: no QuillMD source, database,
users, files, units or environment are shared, promoted or edited. No purchase, agreement, new ACME account, new key or
payment change is part of this act. D3 to D5 stay open as recorded; nothing here accepts an agreement or infers a
licensing permission, and decision (m) (privacy and subprocessor disclosures) stays the owner's open question.

Revision to install: 24c49a5032d5bb0185e5efda08ebe71f54a2845f, the merge commit of PR #1466 (branch fix/cpt-studio-label-binding-20261104, R1a-r5).
It carries PR #1465 (branch feat/cpt-studio-core-ux-20261103, merged as 20a64b8601380f716fb47dd68ada4f7c83de5ffc). That
merge was never installed: this session's verification of it found the four false READYs R1a-r5 closes. Image tag
cpt-studio:24c49a5032d5. Its citation, on 24c49a5032d5bb0185e5efda08ebe71f54a2845f: CI run 41933393287 success; secrets-scan run 41933393216 success; cpt-studio run 41933393311: its checks, migrations and every test pass (5,812 Django, 524 ops, 41 verification, node 118), and its dependency audit stays red on pypdf 6.21.2's seven advisories (interpretation 68), as on #1465's merge commit 20a64b86. It replaces the live revision
41e03656df617d5fab4a551ba7a0d7aea5ca3380, installed 2026-11-03 under
docs/foundation/mutations/20261103-cpt-studio-harness-install.md, which runs image cpt-studio:41e03656df61. That
declaration and its receipts stay as they are.

Execute each phase separately through scripts/run-ruled-mutation.sh with
`python3 -B cpt-studio/ops/install.py --phase <phase> --revision 24c49a5032d5bb0185e5efda08ebe71f54a2845f --receipts /home/claude/cpt-studio-install-20261023`,
in this order: preflight, image, app (with `--provider-mode live --astra-mode live --fable-mode live
--authorization-ref docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`, and no `--access-check`), passages,
license-note, operators, verify, then reassess (`--encounter effe4d0b-b449-4efd-b208-635ca1d09984 --dry-run`, then the
same without `--dry-run`). Run them from a clean, detached checkout of the merge commit that lands this declaration: a
descendant of the revision that changes nothing under cpt-studio/, scripts/run-ruled-mutation.sh or scripts/lib/. Read
each receipt before the next phase. The receipts directory is the live install's own (it holds the live vhost's
receipts); no receipt there is changed: each file is created once.

Not run: secrets, db, reference, provision, http-vhost, cert, https-vhost, rollback-vhost, whose objects exist and do
not change. Between 41e03656df61 and 24c49a5032d5bb0185e5efda08ebe71f54a2845f these are byte-identical: cpt-studio/deploy/ (Dockerfile, entrypoint,
gunicorn, nginx templates, .dockerignore), cpt-studio/requirements.txt, requirements.in and requirements-dev.txt,
cpt-studio/cptstudio/settings.py, scripts/run-ruled-mutation.sh, scripts/lib/ and scripts/check-cotenants.sh. The
installer (cpt-studio/ops/install.py, ops/INSTALL.md) DIFFERS: this act runs this revision's installer, whose app phase
is the blue/green switch (ops/INSTALL.md "Phases": S1 to S5 and the availability record), and which adds the operators,
reassess and switch-back phases and two undo hazards. Before preflight the operator runs, in the act's checkout,
`git diff --quiet 41e03656df617d5fab4a551ba7a0d7aea5ca3380 HEAD -- scripts/check-cotenants.sh cpt-studio/deploy
cpt-studio/requirements.txt cpt-studio/cptstudio/settings.py`; any difference is a stop.

## Delta shipped (41e03656df61 to 24c49a5032d5bb0185e5efda08ebe71f54a2845f)

PRs #1465 and #1466. Their bodies, cpt-studio/CORE-UX-DESIGN.md, ARCHITECTURE.md's appended sections,
ACCURACY-RESIDUALS.md and CPT-CORE-UX-CHECKLIST.md list every change and measurement. For this act:

- Migrations 0009 to 0012 (studio_migrations 8 to 12), each additive under the installer's gate and each safe for the
  previous web serving on the migrated schema during S1 to S5: 0009 adds Decision.modifiers (JSON, NOT NULL, with a
  database default '[]'); 0010 creates OperatorGrant and OperatorRevocation and adds ReportArtifact.audience (default
  'operator' at the database level, so a report the previous web writes in the window is operator-only); 0011 creates
  MemberAnswer and MemberAnswerRevocation, adds Encounter.client_key (nullable, with a partial unique index) and
  EncounterContext.document_date (nullable); 0012 creates WorkerBeat. No data migration: existing rows gain only
  those defaults.
- Reader labels: gi-routing@5 to @6, gi-services@2 to @3, cpt-studio-validation@5 to @6; gi-context@4 unchanged (its
  facts are unchanged). No stage branches on the three moved labels and no fingerprint reads one; new readings apply to
  new uploads, addenda, member saves, the stages they queue, and the one reassessment below. No existing encounter is
  re-assessed or re-sent by the install, and every stored list state recomputes unchanged (predicted below).
- The shared reader's repairs (P1, P2, the lead's L1 to L3; declarations cux-bind.json, cux-hold.json, cux-lead.json):
  statements bound to their procedure, lesion and time; copular negation kept in its scope; combined report titles
  bind no single service; an explicit "no separate office E/M" statement negates the visit; the previously reported
  false READYs (R8 register D1 to D10, D12, D13, D15) held; a separate same-day note's acts its own; a pathology
  heading no procedure title; an attributive act compound no act at the own-passage release.
- The customer interface (P3 to P6): the customer API is an allowlist (studio/customer_api.py) - no provider or model
  identity, usage, run or request id, hash, rule id, trace or peer machinery reaches a customer response, bundle,
  download or error; the platform operator's diagnostics move to /ops/ (404 to every account without an operator grant,
  workspace owners included); the codes-first result list, "Why this code?", the "A few details needed" panel (member
  answers stored apart from the document, attributed and audited; "Not documented" or "Cannot confirm" excludes the
  code, never releases it); staged progress with elapsed time, no percentage or ETA, a paused state from the worker
  heartbeat; approved exports list exactly the persisted approved decisions and are refused once they change; the
  client contract (409 client_outdated to a tab opened on the previous release).
- Sends: an answer whose outcome cannot be recorded is recorded unknown, and a run left 'sending' blocks every send
  (decision (k)); an upload attempt carries a client key, so a retried upload reaches the same document.
- The integration's own repairs:
  - the bounded second review the installed page offers is kept on the customer page as "Check what is still open
    again" (decision (n)): offered only when one can be asked and only to owners and reviewers, sending nothing by the
    offer;
  - the customer queue lists exactly what its badge counts (decision (o): `in_queue` on every list row, the rule
    unchanged);
  - an addendum sent from a details row is accepted (the row id the contract names);
  - progress reads `paused` while the worker's heartbeat is older than 120 s (decision (j));
  - the walk and the download check accept CPT Studio's own act evidence as support.
- R1a-r5, hold-only (PR #1466, declaration cux-r5-binding.json and its hold-only amendment): where more than one
  procedure is read performed, a lesion's name alone never makes an act support a code. Every act keeps the binding and
  placement #1465 gives it, so base codes, bundling, conflicts and unresolved items read exactly what they read before. A
  performed act whose service only a lesion's name gives carries a marker: its own clause names no site, its part names
  no service, and it is not a clip or a cannulation. A code all of whose supporting acts carry the marker is held for the
  reviewer ("performed_status"), and no release or exclusion path reads that hold.
  - It closes the four false READYs this session found on #1465's merge commit, each worse than installed: 45380 for an
    upper-exam biopsy bound by a colon polyp's label, with the upper exam told by a bare endoscope, by "Upper
    endoscopy was then performed", or by the gastroscope before "after withdrawal of the colonoscope"; and 45382 for a
    prophylactic hemostatic clip at a labelled polyp in a combined note.
  - Measured over 2,396 cases built by three refutation rounds: no cell moves toward READY against main, no violation
    main or installed lacks, and 100 of main's violations are fixed.
  - Its cost, all in the hold direction: one battery row (R8 R3 A3's control, 45385 held), and 308 of those cells, 208
    of them READY on installed too, in its one declared class: a combined note whose lesion is acted on by its name
    alone outside any heading naming the service.
  - Not shipped, each refuted: the word-list repairs of rounds 4 and 4b (12 of 12 findings reproduced), and an
    unbinding form of R1a-r5. Removing the act released diagnostic base codes and dropped a conflict.
- pypdf stays 6.21.2 and the document reader's extraction is byte-identical; its seven known advisories stand and the
  cpt-studio job's dependency audit stays red on them - stated here, not waived (interpretation 68).

## Baseline (read-only, 2026-11-04T23:55:03Z; re-read immediately before the commit that lands this declaration; this act's preflight receipt is binding)

Read by /home/claude/cpt-studio-ux-20261103/install/live_baseline.sh (SELECT only, in a read-only transaction, through
the database container's own psql; output kept 0600):
    read_at 2026-11-04T23:55:03Z
    transaction_read_only on
    encounters 49
    revisions 49
    source_files 43
    contexts 64
    routing_runs 57
    provider_runs 80
    provider_runs_sent 74
    assessments 71
    proposals 872
    clarifications 97
    decisions 28
    decision_invalidations 0
    audit_events 490
    reports 122
    jobs 247
    jobs_active 0
    users 3
    memberships 3
    workspaces 1
    login_attempts 50
    reference_sources 2
    reference_facts 34665
    studio_migrations 8
    studio_migration_last 0008_harness2_exchanges_tools_confirmations
    studio_providerexchange 33
    studio_toolcall 20
    studio_findingconfirmation 0
    studio_passagesource 3
    studio_referencepassage 62
    studio_memberanswer absent
    studio_memberanswerrevocation absent
    studio_operatorgrant absent
    studio_operatorrevocation absent
    studio_workerbeat absent
    run_participant astra independent succeeded 6
    run_participant astra peer_review succeeded 6
    run_participant fable independent succeeded 6
    run_participant fable peer_review succeeded 4
    credits_sum 2.480259999999999893
    usage_keys astra input_tokens,input_tokens_details,output_tokens,output_tokens_details,total_tokens
    usage_keys corti creditsConsumed
    usage_keys fable cache_creation,cache_creation_input_tokens,cache_read_input_tokens,inference_geo,input_tokens,output_tokens,output_tokens_details,service_tier,speed
    encounter_state needs_clarification 27
    encounter_state no_codes 4
    encounter_state ready_for_review 3
    encounter_state reviewed 15
    run astra independent succeeded t f 6
    run astra peer_review succeeded t f 6
    run corti primary not_sent f f 2
    run corti primary succeeded f t 4
    run corti primary succeeded t f 51
    run corti second_review succeeded t f 1
    run fable independent succeeded t f 6
    run fable peer_review succeeded t f 4
    job analyze succeeded 49
    job assess succeeded 71
    job astra succeeded 6
    job astra_peer succeeded 6
    job extract succeeded 49
    job fable succeeded 6
    job fable_peer succeeded 4
    job predict succeeded 55
    job review2 succeeded 1
    runs_unreconciled_unknown 0
    runs_reserved_or_sending 0
    last_audit assessment.created 2026-11-04T16:12:43Z 27740
    account demo-reviewer human t reviewer t
    account owner human t owner t
    account review-agent agent t reviewer t
    reference_source cms-mue-practitioner-2026q4 cms-mue-practitioner 2026-Q4 15212 40a09bcd128dd18569a0a01e4fc4cffe
    reference_source cms-pfs-rvu26d cms-pfs RVU26D 19453 40a09bcd128dd18569a0a01e4fc4cffe
    assessments_by_engine cpt-studio-validation@3 12
    assessments_by_engine cpt-studio-validation@4 46
    assessments_by_engine cpt-studio-validation@5 13

## Expected changes, per phase

- preflight: none. One random ACME probe file is written and removed.
- image: a new local image cpt-studio:24c49a5032d5, built from git archive of 24c49a5032d5bb0185e5efda08ebe71f54a2845f cpt-studio/, labelled with the revision,
  user 10150, CPT_STUDIO_RELEASE_SHA=24c49a5032d5bb0185e5efda08ebe71f54a2845f. The apt, user, WORKDIR, requirements and pip steps are expected CACHED: the
  Dockerfile, .dockerignore and requirements are byte-identical to 41e03656df61's. Measured, not assumed (2026-11-04
  15:04Z): a candidate built the installer's way (install.extract_archive of git archive 20a64b86, the same .dockerignore
  copy and build arguments, tag cpt-studio-precheck:20a64b860138, no installer labels;
  /home/claude/cpt-studio-ux-20261103/install/precheck_image.py and its log) reported steps 2/8 to 6/8 CACHED, and its
  first 9 of 11 layers are identical to cpt-studio:41e03656df61's. The builder is not pruned between that measurement and
  the image phase. By the operator, offline, after the
  phase: pypdf 6.21.2 in the new image; `dpkg-query -W -f '${Package} ${Version}\n'` read from cpt-studio:41e03656df61
  and from the new image: identical. A build log showing apt or pip ran is a stop before app.
- Before app, outside the installer and read-only on the database: one `pg_dump -Fc` of the cptstudio database through
  the database container's own pg_dump, to /home/claude/cpt-studio-install-20261023/pre-app-24c49a5032d5-<UTC>.dump (0600);
  its `pg_restore --list` shows 34 TABLE DATA entries. The only data-level way back; synthetic documents,
  responses and password hashes; kept until a separate, recorded decision removes it.
- app (the blue/green switch; ops/INSTALL.md "Phases"):
  - the application's loader parses the Corti credentials and each participant's credentials file in the worker's mount
    layout with no network; migrate (a one-shot) applies exactly 0009_cux_review, 0010_cux_operator, 0011_cux_flow and
    0012_cux_worker_beat; the queue read finds 0 stages this revision cannot run;
  - S1: cpt-studio-web-next starts on the idle port (9151 if the live web is on 9150) and answers /health/ with release
    24c49a5032d5bb0185e5efda08ebe71f54a2845f, its sign-in page and every static file that page names; S2: the 41e03656df61 worker is parked (its current
    stage finishes; none is expected running); S3: the quillmd-cpt vhost's upstream is switched to the idle port - its
    sha256 goes from 259b895dd1307e81b8fbcb5439874477daf71eba63c9b996b3bdfc572bf71a0c to f816a27de9e64af51d6a905484e22fdfc5f13a941a246931261bfc0df1e3ca65, the two differing in their proxy_pass line alone - `sudo -n nginx
    -t` passes with no new warning and `sudo -n systemctl reload nginx` reloads gracefully, and
    https://cpt.quillmd.com/health/ serves 24c49a5032d5bb0185e5efda08ebe71f54a2845f; S4: the new worker starts; S5: the old web is drained (at least 130 s,
    at most 600 s), stopped, parked as cpt-studio-web-previous, and the incoming web renamed cpt-studio-web;
  - availability (the public /health/ every 0.5 s from before S1 to the end): every sample 200; releases_seen
    41e03656df61 then 24c49a5032d5bb0185e5efda08ebe71f54a2845f; non_200_count 0;
  - states_recomputed {"encounters": 49, "changed": {}} (predicted below). This revision re-derives every state by
    its own rules: an unreconciled unknown or orphaned sending outcome now outranks a failure, and a reservation left
    behind is settled not_sent. A read-only count on the live database (2026-11-04) found 0 encounters with such an
    outcome beside a failed state and 0 reserved runs, so nothing moves. The parked pair is removed;
  - nothing is sent: no access check is run (the participant adapters are byte-identical to 41e03656df61's, and the walk
    below exercises them), and the installer's one-shots run with every provider disabled;
  - read only, the phase reads /proc for the host nginx master's worker pids, to verify that a reload took effect. A
    failing S3 or the S4 undo's switch back restores the vhost and then runs one more `sudo -n /usr/sbin/nginx -t` and
    `sudo -n /usr/bin/systemctl reload nginx` (settle_vhost), whatever the earlier reload's outcome. The incoming web is
    never removed while nginx may route to it.
  Counts after app: every count equals the pre-app reading (no data migration, nothing re-assessed); studio_migrations
  12; the five new tables exist and are empty; the four new columns exist.
- passages and license-note: idempotent, no file or row changes ({"imported": 0}-shaped answers; the 3 passage sources,
  62 reference passages and the 2 licence notes as installed).
- operators: two accounts created - ops-agent (agent) and platform-operator (human) - each with an operator grant and
  no workspace membership, granted by the application's own command with an explicit `--by` (it never looks up the
  one-shot's uid); users +2, operator grants +2, memberships +0; ops-agent's login written to this user's
  /home/claude/.cpt-studio/ops-agent-credentials.json (0600, top-level username and password) and platform-operator's
  to the root-only /etc/cpt-studio/operator-credentials.json (0600), neither printed. Every other count unchanged.
- verify: no difference from the preflight baseline but the quillmd-cpt vhost's proxy_pass line (sha256 f816a27de9e64af51d6a905484e22fdfc5f13a941a246931261bfc0df1e3ca65,
  as S3 wrote it); https://cpt.quillmd.com/health/ serves 24c49a5032d5bb0185e5efda08ebe71f54a2845f under normal certificate verification; the security
  headers once each.
- reassess (Mara, encounter effe4d0b-b449-4efd-b208-635ca1d09984): the dry run names the plan (the final assessment
  82679b83-..., Corti's run 4eba15ee-..., Astra's and Fable's runs and peer runs by id) and queues nothing; the real run
  queues exactly one assess job (key ending ':c:' plus the tag's 12 hex), which the running worker makes from the
  retained answers: provider runs +0, provider exchanges +0, tool calls +0, assessments +1, audit 'assessment.refreshed'
  +1. Mara then reads ready_for_review with 43239, 45380 and 45385 selected and ready, no open question and no office
  E/M question (predicted below). The phase passes `--participants astra,fable` from this install's app receipt.
- Image cpt-studio:41e03656df61 is kept: it is the rollback image. Nothing removes any image.

Predicted with this revision's own code (2026-11-04T22:50:56Z, run on 97ab8d60548195a8075dbda72527fe468d807a49, PR
#1466's head, whose cpt-studio/ tree 49b037df1de6816532d5efe5e2fd10b2eb497f69 is byte-for-byte the merge commit
24c49a5032d5bb0185e5efda08ebe71f54a2845f's (git rev-parse <commit>:cpt-studio), over the read-only live dump of that minute
(sha256 b6df177ec4faccbf7422e365ea52e8d972db67d67f2abc39e05905b8a050345f, 34 TABLE DATA); /home/claude/cpt-studio-ux-20261103/install/predict.sh, kept with its
outputs) restored into scratch databases on the test server: migrate applies 0009 to 0012; RECOMPUTE_STATES
{"encounters": 49, "changed": {}}; the installed revision's RECOMPUTE on the same dump the same; a control with an
unknown outcome planted on one sent run of a reviewed encounter turns that encounter to provider_unknown; the rollback
hazard read {"hazards": {}}; Mara's reassessment as the phase makes it, made by run_worker --once with Astra and Fable
live and no credential file: runs 80 to 80, exchanges 33 to 33, assessments +1, state needs_clarification
to ready_for_review, 43239, 45380 and 45385 selected/ready, 0 open clarifications. The prediction holds only while the
re-read baseline shows no live activity.

## What the install sends

Nothing. No access check is run; every one-shot runs with Corti and the participants disabled; the reassessment
builds and sends no request. Immediately before app: jobs_active 0; no provider run reserved or sending; no unreconciled
unknown outcome; no audit event newer than 10 minutes. Checked after app and after reassess: provider runs, sent runs,
provider exchanges, tool calls and credits_sum equal their pre-app reading, and no provider run has a created_at at or
after the app receipt's started_at.

## After the install: the acceptance walk (ordinary use, not a phase)

All through https://cpt.quillmd.com, through the agent account review-agent (its decisions labelled agent-executed
synthetic review, never a doctor's clinical approval; decision (i)), with the ops-agent operator session beside it for
everything a customer must not be shown. One document, then the read-only checks:

    node ops/verify_browser.cjs --base-url https://cpt.quillmd.com --credentials <0600 review-agent file> \
      --operator-credentials /home/claude/.cpt-studio/ops-agent-credentials.json \
      --docs /home/claude/cpt-studio-ux-walk-docs-20261104 \
      --manifest /home/claude/cpt-studio-ux-walk-20261104/manifest.json \
      --out /home/claude/cpt-studio-ux-walk-evidence-20261104 --deadline-seconds 1500 --allow-live-provider
    python3 -B ops/verify_downloads.py --evidence <out>/evidence.json --json-out <out>/downloads.json
    python3 -B ops/scan_customer.py ... (GET only, apart from sign-in and sign-out)

The walk's inputs, written after the code froze on main (24c49a50) and before the declaration:
- the manifest (sha256 0176f87ebc106674..., one document, fresh-f2), assembled from the expectations recorded before
  unsealing, with the review plan approve_codes [45385, 45380], stop_and_resume, and modifiers {45380: XS}. XS is
  chosen only where the dialog offers the separate-lesion choice: an agent-executed synthetic choice, never a payer
  validation;
- the delivery file, generated by ops/verification/generate.py: the walk copy, sha256 79481ec01fc3724d....

Read offline on the merge commit's own tree under four citation patterns, f2 gives 45385 and 45380 selected/ready.
There is no question, no office E/M question and no conflict, and each code carries the separate-lesion consideration.
This matches the author's expectations, which were written before unsealing.

The walk's document is the second fresh one. The first (written and sealed 2026-11-03, before any code of PR #1465 was
measured against it) was unsealed once #1465's code froze. Read offline, it held all three of its codes on main and on
the installed revision alike. That is how this session found the two gaps recorded in ACCURACY-RESIDUALS.md, round 5.
The refutation of a repair for them then found main's four false READYs, which R1a-r5 closes. So the first document is
now a development input and is not walked as held-out evidence. The second (fresh-f2, a surveillance colonoscopy with a
cold snare polypectomy and a jumbo cold forceps removal) was written and sealed (mode 000) at 2026-11-04T13:29:08Z,
before any of the round-4 or round-5 repairs began. It was read by no repair, refutation or verification agent. Its
author's expectations were written at 2026-11-04T15:01:02Z, before unsealing
(/home/claude/cpt-studio-ux-walk-20261104/fresh-f2-expectations.json, mode 0400). It is unsealed only after this
declaration's code is frozen, with its sha256 checked against 0a4de732df9a36223108c2a7655cab3472d318cf876cb19f557e11ff53eb4023.
The walk's generator requires the exact synthetic banner on line 1, so the uploaded file is that original with only line
1 replaced. Both sha256s are recorded, and lines 2 onward are byte-identical.
The walk approves only ready selected codes its plan names, chooses a modifier only where its plan names one, makes no
rejection, confirms no exclusion, asks no second review and makes no confirmation. Mara is read (GET only) through the
customer page and the operator view: nothing is decided, answered or exported on it.

Bounds for the document (database counts, SELECT only, before and after): encounters +1, revisions +1, source files +1
(0 for a paste); provider runs at most +5 (Corti's primary, Astra's and Fable's first readings, their two peer reviews),
each sent at most once; provider exchanges at most +16 and their tool calls; jobs at most +11; assessments at most +3;
member answers + what the evidence records as saved; decisions and reports + what the evidence records as HTTP 201;
second-review runs +0; finding confirmations +0; jobs_active back to 0. Cost: about 0.04 Corti credits and an estimated
US$0.40-1.50 from the participants, a record, not a gate; the walk stops if the estimate exceeds US$10.

## Must not change

- The quillmd vhost and every other sites-available file but quillmd-cpt's proxy_pass line; nginx.conf, conf.d and every
  sites-enabled entry; the local routing of every co-tenant name/port pair and of an unknown host.
- app.quillmd.com /health/ and the check-cotenants.sh results; every container outside CPT Studio running at preflight
  (same id, still running); every existing volume; every Let's Encrypt lineage and renewal config; the ACME account set.
- The QuillMD rebuild, its database, users and files. /etc/cpt-studio/ and its six files as the secrets receipts record
  them (the operators phase adds a seventh, operator-credentials.json) and /etc/cpt-studio-provider-sources/.
- cpt-studio-db: the same container, image, port and restart policy, running throughout; volumes cpt-studio-pg and
  cpt-studio-files; network cpt-studio-net.
- The two ReferenceSource rows, their licence notes and 34,665 reference facts; the 3 passage sources and 62 passages;
  the three existing accounts and their memberships.
- Every existing encounter, revision, source file, context, routing run, provider run, exchange, tool call, assessment,
  proposal, decision, clarification, audit event, report and job: no data migration, nothing re-assessed by app, every
  stored state recomputed unchanged. The one exception is the reassess phase's own declared rows for Mara.

## Validation per phase

Each phase's own checks (ops/INSTALL.md) must pass and its receipt must say ok, with tree.mode
descendant-without-runtime-change, tree.head the merge commit that lands this declaration, door.declaration this file,
door.declaration_commit the commit that last touched it. app additionally: the availability record as above, the
switch's vhost sha256 before and after as above, the drain's outcome recorded. After app, by the operator: /health/
through the new port {status ok, service cpt-studio, data_mode synthetic-only, database ok, release 24c49a5032d5bb0185e5efda08ebe71f54a2845f}; a
signed-in GET of /api/session without the client header answers 409 client_outdated and with it 200; every /ops/ URL
answers 404 to review-agent and 200 to ops-agent.

## Rollback per phase, and its limits

- preflight, image, passages, license-note, verify change nothing that serves. A failed image leaves at most an unused
  image.
- app fails before S3 (a credentials parse, migrate, the queue read, the incoming web's health or smoke): the
  41e03656df61 web never stopped serving; the incoming web is removed and the old worker restarted (ops/INSTALL.md,
  the app phase's undo). Migrations 0009 to 0012 are additive: once applied they stay, and 41e03656df61 runs on that
  schema.
- app fails at or after S3: exactly as ops/INSTALL.md and the receipt set out (the vhost put back, the stages the new
  pair queued closed, the list states put back, or the new pair left serving with its worker held while a person
  decides). Each failure is a stop: the pair that is running serves while it is judged, and no remedy is taken without
  a decision recorded under this declaration.
- After a successful app: `--phase switch-back --provider-mode live --astra-mode live --fable-mode live
  --authorization-ref docs/foundation/rulings/2026-10-23-cpt-studio-gi.md` returns to 41e03656df61 without stopping the
  serving web first. A preflight is run immediately before it, because switch-back refuses on a stale ingress baseline
  before it closes anything. It and refuses while this revision recorded what an older revision would act on or show wrongly -
  now including a member's standing answer and a chosen modifier (UNDO_HAZARDS member_answer, modifier). The walk's
  agent approvals with a modifier, and its saved details, are such records: clearing them is "Change this answer" and
  "Undo decision" on this revision's web, each a recorded decision. A switch-back also returns the customer page to
  41e03656df61's, which names the providers: the §2 removal goes with it.
- The pre-app dump is the only data-level way back; restoring it deletes every row made after it and is a separate
  declared act. Image cpt-studio:41e03656df61 and its receipts are kept.

## What is not claimed

- No coding-accuracy figure and no reliable-coding claim. Clinical validation is NOT established: no qualified coder
  has adjudicated a predeclared set; the register's truths and the walk's expectations are PROVISIONAL. A passing
  synthetic case is not guaranteed accuracy.
- Functional completion, clinical accuracy validation and content-use permissions are reported separately: CPT
  descriptors, guidelines and NCCI procedure-to-procedure edits stay not verified (D3, D4 open), no CPT descriptor text
  is shown, and no payer validation is claimed for a modifier.
- Privacy and subprocessor disclosures (decision (m)): no customer screen names a provider after this change and CPT
  Studio has no disclosure page; whether one is legally required, and what it says, is the owner's open question.
- pypdf 6.21.2 and its advisories stay (interpretation 68); the dependency audit stays red.
- The existing encounters other than Mara are neither re-assessed nor re-sent; how the new screens present each of them
  is not walked.

## Stop conditions

Stop and diagnose on any of these; do not rerun a phase and do not upload the walk document:
- any non-zero phase exit or a receipt that does not say ok; a tree mode other than descendant-without-runtime-change;
- any non-200 in the app phase's availability record; a /health/ release other than 41e03656df61 or 24c49a5032d5bb0185e5efda08ebe71f54a2845f; any 5xx;
- a routing, health, check-cotenants or file-hash difference other than quillmd-cpt's proxy_pass line, or a new nginx
  warning;
- a new image whose pypdf is not 6.21.2 or whose package list differs; a build log showing apt or pip ran;
- a migrate log that applies anything but 0009 to 0012; a stage this revision cannot run;
- before app: jobs_active not 0, a reserved or sending run, an unreconciled unknown outcome, or an audit event under
  10 minutes old; across app, operators or reassess: a count moving that the phase does not declare, or a provider run
  created;
- states_recomputed naming any changed encounter (predicted none); a leftover *-previous or *-next container after app;
- operators: an account that is not read back as an active operator with no membership, or a credential value in any
  output;
- reassess: a dry run followed by a job; more than one job; a provider run, exchange or tool call created; Mara not
  ready_for_review with exactly 43239, 45380 and 45385 ready and no open question;
- during the walk: more provider runs, exchanges or jobs than the bounds above; a second-review run; a finding
  confirmation; a decision or modifier its plan does not name; an unknown provider outcome (reconciling it is a
  separate, recorded decision); a provider authentication, quota or payment failure; verify_downloads or scan_customer
  exiting non-zero; jobs_active not returning to 0 within the stage deadlines; a downloaded report that misstates the
  persisted decisions; any customer-visible provider identity or diagnostic; any action on an encounter the walk did
  not create (Mara is read only).

## Decision after the app phase (2026-11-05, appended before the next phase)

**What the record showed.** The app phase receipt (app-20261105T003351011802Z.json, ok) matches every declared row:
- migrate applied exactly 0009 to 0012;
- the switch went 9150 to 9151, the vhost 259b895d... to f816a27d..., https 200;
- availability: 301 samples, 0 not 200, releases 41e03656df61 then 24c49a50;
- drain 130.6 s;
- states_recomputed {"encounters": 49, "changed": {}};
- no unrunnable stage, no leftover container.

The read-only counts after app (live_baseline.sh) equal the pre-app reading in every count, with migrations at 12, the
four new columns present and four of the five new tables empty. **One count differs from this declaration:**
`studio_workerbeat` holds 1 row, where the declaration says the five new tables are empty. That is a count the phase
did not declare, so the phase was stopped and diagnosed before anything else ran.

**Diagnosis (read-only).**
- The row: name 'worker', revision 24c49a5032d5bb0185e5efda08ebe71f54a2845f, pid 1, beat_at 2026-11-05T00:34:26Z.
- It is the new worker's own heartbeat (decision (j), studio/models.py WorkerBeat). A thread of the worker process
  writes one row per worker name (jobs.start_heartbeat, update_or_create) every jobs.HEARTBEAT_SECONDS, from the moment
  S4 starts the worker. The progress panel reads it to say "paused" when no worker beats.
- It carries no document, answer, decision or usage. No provider run was created; provider runs, exchanges, tool calls,
  assessments, decisions and audit events are unchanged.

**Decision.** The declaration's "the five new tables exist and are empty" was wrong for `studio_workerbeat`. It is
corrected here: four new tables are empty, and `studio_workerbeat` holds exactly the running worker's one heartbeat row.
The row's count stays 1 and its beat_at advances on its own. No undeclared row of any other kind exists. Every later
phase's count check reads `studio_workerbeat` as 1 row, name 'worker', revision 24c49a50. The remaining phases run, in
the declared order, from a clean detached checkout of the commit that lands this decision: passages, license-note,
operators, verify, then reassess (dry run, then real). Nothing else in this declaration changes.
