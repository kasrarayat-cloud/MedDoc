# Prospective declaration: the CPT Studio leave-note fix and walk corrections at cpt.quillmd.com (24c49a5032d5 to b0dc3446c64c), installed blue/green with the demo kept serving, and the second acceptance walk

Authority: the owner's directive of 2026-11-03 ("Implement the CPT Studio core repair and customer-interface
improvements below on https://cpt.quillmd.com. Complete the work through installation and verification."), recorded
verbatim in docs/foundation/rulings/2026-10-23-cpt-studio-gi.md with this session's interpretations. Session a12d8fb3
is the integration and deployment owner for that directive.

The first acceptance walk of the installed core repair (24c49a50, 2026-11-05) found the page did not do one thing the
directive asks: a stopped or failed document's panel never said the member could leave the page. Section 5 asks that
"Make it clear when the user can leave the page and return". This act installs the fix. It then walks what the first
walk could not: the failure state, the "A few details needed" controls on desktop and mobile, and the stopped panel's
leave note. Evidence of the first install and walk: docs/deploy-reports/20261105-cpt-studio-24c49a50-install-and-walk.md.

The directive's install rule governs every phase here: "Keep the existing website and demo accessible while you work.
Do not pause the demo, introduce a maintenance page, or disable customer access as the default approach."

The install is also governed by the 2026-10-23 directive cited in docs/foundation/mutations/20261023-cpt-studio-install.md:
- a protected synthetic demonstration;
- provider credentials server-side;
- app.quillmd.com and unrelated services preserved.

CPT Studio stays standalone: no QuillMD source, database, users, files, units or environment are shared, promoted or
edited. No purchase, agreement, new ACME account, new key or payment change is part of this act. D3 to D5 stay open as
recorded, and decision (m) (privacy and subprocessor disclosures) stays the owner's open question.

Revision to install: b0dc3446c64c840cd01e9f37b8de3bad7aa954d4, the merge commit of PR #1469 (branch fix/cpt-studio-leave-note-20261105). Image tag
cpt-studio:b0dc3446c64c. Its citation, on b0dc3446c64c840cd01e9f37b8de3bad7aa954d4: CI run 41958845693 success; secrets-scan run 41958846065 success; cpt-studio run 41958845698: its checks, migrations and every test pass (5,812 Django, 524 ops, 43 verification, node 130), and its dependency audit stays red on pypdf 6.21.2's seven advisories (interpretation 68), as on 24c49a5032d5.

It replaces the live revision 24c49a5032d5bb0185e5efda08ebe71f54a2845f, installed 2026-11-05 under
docs/foundation/mutations/20261104-cpt-studio-core-ux-install.md, which runs image cpt-studio:24c49a5032d5. That
declaration and its receipts stay as they are, and that image is kept as the rollback image.

Execute each phase separately through scripts/run-ruled-mutation.sh with
`python3 -B cpt-studio/ops/install.py --phase <phase> --revision b0dc3446c64c840cd01e9f37b8de3bad7aa954d4 --receipts /home/claude/cpt-studio-install-20261023`.

Phases, in this order:
1. preflight;
2. image;
3. app, with `--provider-mode live --astra-mode live --fable-mode live --authorization-ref
   docs/foundation/rulings/2026-10-23-cpt-studio-gi.md` and no `--access-check`;
4. verify.

Run them from a clean, detached checkout of the merge commit that lands this declaration. That commit must be a
descendant of the revision that changes nothing under cpt-studio/, scripts/run-ruled-mutation.sh or scripts/lib/. Read
each receipt before the next phase. The receipts directory is the live install's own, and no receipt there is
changed: each file is created once.

Not run: secrets, db, reference, provision, http-vhost, cert, https-vhost, rollback-vhost, passages, license-note,
operators, reassess and switch-back. Their objects exist and do not change, and nothing in this revision asks for them.

Between 24c49a5032d5bb0185e5efda08ebe71f54a2845f and b0dc3446c64c840cd01e9f37b8de3bad7aa954d4, these are byte-identical:
- the installer, cpt-studio/ops/install.py and ops/INSTALL.md;
- cpt-studio/deploy/ (Dockerfile, entrypoint, gunicorn, nginx templates, .dockerignore);
- cpt-studio/requirements.txt, requirements.in and requirements-dev.txt;
- cpt-studio/cptstudio/;
- every Python file and every migration under cpt-studio/studio/;
- scripts/run-ruled-mutation.sh, scripts/lib/ and scripts/check-cotenants.sh.

Before preflight the operator runs, in the act's checkout,
`git diff --quiet 24c49a5032d5bb0185e5efda08ebe71f54a2845f HEAD -- scripts/check-cotenants.sh scripts/run-ruled-mutation.sh scripts/lib cpt-studio/deploy cpt-studio/requirements.txt cpt-studio/requirements.in cpt-studio/requirements-dev.txt cpt-studio/cptstudio cpt-studio/ops/install.py cpt-studio/ops/INSTALL.md ':(glob)cpt-studio/studio/**/*.py'`.
Any difference is a stop.

## Delta shipped (24c49a5032d5 to b0dc3446c64c)

    cpt-studio/studio/static/studio/app.js             (runtime: LEAVE_NOTES stopped and failed, 6 lines)
    cpt-studio/tests/frontend/app.test.cjs             (the leave-note test)
    cpt-studio/ops/verify_browser.cjs                  (the walk, held to the page and the operator view as they are;
                                                        expected_failure)
    cpt-studio/ops/verification/test_verify_browser.cjs, test_generate.py, generate.py (non-utf8-txt)
    cpt-studio/ops/verification/samples/make_samples.py and the four samples it writes
                                                       (11 files, 556 insertions, 38 deletions: git diff --stat
                                                        24c49a5032d5bb0185e5efda08ebe71f54a2845f b0dc3446 -- cpt-studio)

The one file that changes what the service does is cpt-studio/studio/static/studio/app.js. Its LEAVE_NOTES gains
`stopped` and `failed`, each "You can leave this page — the document stays in Documents." Nothing more is promised,
because a detail saved on a stopped document restarts it (jobs.change_context). Everything else is the verification
tooling and its tests:
- the walk held to what the page and the operator view really serve (the compact line, the notice, Corti's model-less
  runs, the upload's client key);
- a walk of a document that must fail (expected_failure);
- the generator's non-utf8-txt delivery;
- the samples corrected to the live shapes.

A bounded independent refutation found eight defects in the first two commits, each repaired with a failing-first
test in the third. The full account is in the PR.

## Measured before this declaration

Image precheck (2026-11-05, /home/claude/cpt-studio-ux-20261103/install/precheck_image.py, which builds exactly as the
image phase does, without its labels):
- cpt-studio-precheck:5a1dc06e6e86 (sha256:4212844e248052f414b723c509105820975c7215164577db2f49fe2344bbc804), built
  from the PR head 5a1dc06e6e86304f3f36f0c6c361e2f27ca82d42;
- its cpt-studio/ tree is 5f3e1f74d90f162860a6c7eb7519cabd6be1b511, which is byte for byte the merge commit b0dc3446c64c840cd01e9f37b8de3bad7aa954d4's (git rev-parse <commit>:cpt-studio);
- steps 2/8 to 6/8 (apt, user, WORKDIR, requirements, pip) CACHED, and only the application copy and collectstatic ran;
- its `dpkg-query` list (166 packages) is identical to cpt-studio:24c49a5032d5's;
- pypdf 6.21.2, uid 10150;
- /app/staticfiles/studio/app.js and its hashed copy carry the new stopped note.

The builder is not pruned between that measurement and the image phase.

Offline prediction of the walk's fresh-f3 (/home/claude/cpt-studio-ux-20261103/walk/predict_f3.py on the sealed export
of 24c49a50, whose reader is byte-identical to b0dc3446c64c840cd01e9f37b8de3bad7aa954d4's):
- under four citation patterns, 45385 is selected and needs one detail, `extent`;
- the date of service (2026-11-05) and the setting (asc) are read from the document;
- no office E/M question and no conflict.

This matches the author's expectations, sealed first (walk2-expectations.json, 2026-11-05T01:36:10Z).

## Baseline (read-only, 2026-11-05T03:41:09Z; re-read immediately before the commit that lands this declaration; this act's preflight receipt is binding)

    read_at 2026-11-05T03:41:09Z
    transaction_read_only on
    encounters 51
    revisions 51
    source_files 45
    contexts 67
    routing_runs 60
    provider_runs 92
    provider_runs_sent 86
    assessments 78
    proposals 964
    clarifications 117
    decisions 30
    decision_invalidations 0
    audit_events 549
    reports 127
    jobs 271
    jobs_active 0
    users 5
    memberships 3
    workspaces 1
    login_attempts 53
    reference_sources 2
    reference_facts 34665
    studio_migrations 12
    studio_migration_last 0012_cux_worker_beat
    studio_providerexchange 50
    studio_toolcall 31
    studio_findingconfirmation 0
    studio_passagesource 3
    studio_referencepassage 62
    studio_memberanswer 7
    studio_memberanswerrevocation 0
    studio_operatorgrant 2
    studio_operatorrevocation 0
    studio_workerbeat 1
    column studio_decision.modifiers present
    column studio_encounter.client_key present
    column studio_encountercontext.document_date present
    column studio_reportartifact.audience present
    run_participant astra independent succeeded 8
    run_participant astra peer_review succeeded 9
    run_participant fable independent succeeded 8
    run_participant fable peer_review succeeded 7
    credits_sum 2.585939999999999897
    usage_keys astra input_tokens,input_tokens_details,output_tokens,output_tokens_details,total_tokens
    usage_keys corti creditsConsumed
    usage_keys fable cache_creation,cache_creation_input_tokens,cache_read_input_tokens,inference_geo,input_tokens,output_tokens,output_tokens_details,service_tier,speed
    encounter_state needs_clarification 26
    encounter_state no_codes 4
    encounter_state ready_for_review 4
    encounter_state reviewed 17
    run astra independent succeeded t f 8
    run astra peer_review succeeded t f 9
    run corti primary not_sent f f 2
    run corti primary succeeded f t 4
    run corti primary succeeded t f 53
    run corti second_review succeeded t f 1
    run fable independent succeeded t f 8
    run fable peer_review succeeded t f 7
    job analyze succeeded 51
    job assess succeeded 78
    job astra cancelled 1
    job astra succeeded 8
    job astra_peer succeeded 9
    job extract succeeded 51
    job fable succeeded 8
    job fable_peer succeeded 7
    job predict succeeded 57
    job review2 succeeded 1
    runs_unreconciled_unknown 0
    runs_reserved_or_sending 0
    last_audit assessment.created 2026-11-05T02:47:40Z 3210
    account demo-reviewer human t reviewer t
    account ops-agent agent t  
    account owner human t owner t
    account platform-operator human t  
    account review-agent agent t reviewer t
    reference_source cms-mue-practitioner-2026q4 cms-mue-practitioner 2026-Q4 15212 40a09bcd128dd18569a0a01e4fc4cffe
    reference_source cms-pfs-rvu26d cms-pfs RVU26D 19453 40a09bcd128dd18569a0a01e4fc4cffe
    assessments_by_engine cpt-studio-validation@3 12
    assessments_by_engine cpt-studio-validation@4 46
    assessments_by_engine cpt-studio-validation@5 13
    assessments_by_engine cpt-studio-validation@6 7

## Expected changes, per phase

- **preflight:** none. One random ACME probe file is written and removed.
- **image:**
  - a new local image cpt-studio:b0dc3446c64c, built from git archive of b0dc3446c64c840cd01e9f37b8de3bad7aa954d4 cpt-studio/, labelled with the revision,
    user 10150, CPT_STUDIO_RELEASE_SHA=b0dc3446c64c840cd01e9f37b8de3bad7aa954d4;
  - the apt, user, WORKDIR, requirements and pip steps CACHED, as measured above;
  - by the operator, offline, after the phase: pypdf 6.21.2 in the new image, and its `dpkg-query -W -f '${Package}
    ${Version}\n'` identical to cpt-studio:24c49a5032d5's.

  A build log showing apt or pip ran is a stop before app.
- **Before app, outside the installer and read-only on the database:** one `pg_dump -Fc` of the cptstudio database,
  through the database container's own pg_dump, to
  /home/claude/cpt-studio-install-20261023/pre-app-b0dc3446c64c-<UTC>.dump (0600).
  - Its `pg_restore --list` shows 39 TABLE DATA entries (34, plus the five 0009 to 0012 added).
  - It holds synthetic documents, responses and password hashes, and is kept until a separate, recorded decision
    removes it.
  - The dump of 2026-11-05T00:30:41Z stays as it is.
- **app (the blue/green switch; ops/INSTALL.md "Phases"):**
  - The loader parses the Corti credentials and each participant's credentials file in the worker's mount layout, with
    no network. migrate (a one-shot) applies nothing: "No migrations to apply". The queue read finds 0 stages this
    revision cannot run.
  - **S1:** cpt-studio-web-next starts on the idle port 9150 (the live web is on 9151). It answers /health/ with release
    b0dc3446c64c840cd01e9f37b8de3bad7aa954d4, its sign-in page, and every static file that page names.
  - **S2:** the 24c49a5032d5 worker is parked. Its current stage finishes; none is expected running.
  - **S3:** the quillmd-cpt vhost's upstream is switched to 9150. Its sha256 goes from
    f816a27de9e64af51d6a905484e22fdfc5f13a941a246931261bfc0df1e3ca65 to
    259b895dd1307e81b8fbcb5439874477daf71eba63c9b996b3bdfc572bf71a0c, the two differing in their proxy_pass line alone
    (the reverse of the 2026-11-05 switch). `sudo -n nginx -t` passes with no new warning, `sudo -n systemctl reload
    nginx` reloads gracefully, and https://cpt.quillmd.com/health/ serves b0dc3446c64c840cd01e9f37b8de3bad7aa954d4.
  - **S4:** the new worker starts.
  - **S5:** the old web is drained (at least 130 s, at most 600 s), stopped, and parked as cpt-studio-web-previous. The
    incoming web is renamed cpt-studio-web.
  - **availability** (the public /health/ every 0.5 s, from before S1 to the end): every sample is 200; releases_seen
    are 24c49a5032d5bb0185e5efda08ebe71f54a2845f then b0dc3446c64c840cd01e9f37b8de3bad7aa954d4; non_200_count is 0.
  - **states_recomputed** is {"encounters": 51, "changed": {}}. The state rules are byte-identical (no Python
    file under studio/ changes), so nothing can move. The parked pair is removed.
  - **Nothing is sent.** No access check is run, and the installer's one-shots run with every provider disabled.
  - **Read only:** the phase reads /proc for the host nginx master's worker pids. A failing S3, or the S4 undo's
    switch back, restores the vhost and then runs one more `sudo -n /usr/sbin/nginx -t` and `sudo -n
    /usr/bin/systemctl reload nginx` (settle_vhost). The incoming web is never removed while nginx may route to it.
  - **Counts after app:** every count equals the pre-app reading, apart from a member's own use during the act. That
    use is identified read-only by encounter and acting account, recorded, and set aside before the comparison; any
    other movement is the act's and a stop. studio_workerbeat stays 1 row named 'worker'. Its
    revision becomes b0dc3446c64c840cd01e9f37b8de3bad7aa954d4 and its beat_at advances once the new worker beats (S4), because the worker heartbeat
    updates its one row (decision recorded 2026-11-05 under the first declaration). No data migration; nothing
    re-assessed.
- **verify:** no difference from the preflight baseline except the quillmd-cpt vhost's proxy_pass line (sha256
  259b895dd1307e81b8fbcb5439874477daf71eba63c9b996b3bdfc572bf71a0c, as S3 wrote it).
  https://cpt.quillmd.com/health/ serves b0dc3446c64c840cd01e9f37b8de3bad7aa954d4 under normal certificate verification, with the security headers
  once each.
- Image cpt-studio:24c49a5032d5 is kept: it is the rollback image. Nothing removes any image.

## What the install sends

Nothing. No access check is run, and every one-shot runs with Corti and the participants disabled.

Immediately before app:
- jobs_active 0;
- no provider run reserved or sending;
- no unreconciled unknown outcome;
- no audit event newer than 10 minutes.

Checked after app: provider runs, sent runs, provider exchanges, tool calls and credits_sum equal their pre-app
reading, and no provider run has a created_at at or after the app receipt's started_at.

## After the install: the second acceptance walk (ordinary use, not a phase)

All through https://cpt.quillmd.com, through the agent account review-agent. Its decisions are labelled
agent-executed synthetic review, never a doctor's clinical approval (decision (i)); this walk makes none. The ops-agent
operator session runs beside it. The walk tool is b0dc3446c64c840cd01e9f37b8de3bad7aa954d4's own (ops/verify_browser.cjs, run from the act's checkout).

    node ops/verify_browser.cjs --base-url https://cpt.quillmd.com --credentials <0600 review-agent file> \
      --operator-credentials /home/claude/.cpt-studio/ops-agent-credentials.json \
      --docs /home/claude/cpt-studio-ux-walk2-docs-20261105 \
      --manifest /home/claude/cpt-studio-ux-walk2-20261105/manifest.json \
      --out /home/claude/cpt-studio-ux-walk2-evidence-20261105 --deadline-seconds 1500 --allow-live-provider
    python3 -B ops/verify_downloads.py --evidence <out>/evidence.json --json-out <out>/downloads.json
    python3 -B ops/scan_customer.py ... --encounter <each walk encounter> (GET only, apart from sign-in and sign-out)

The inputs, written before this declaration:
- the manifest (sha256 f6ec74091740f5ab737b0b159efd3c4cf748f2b5051b6a2776cc97a03e30cc4d) with two documents, both
  UI-state cases authored to reach those states. Neither is accuracy evidence.
  - **fresh-fail.** A text file delivered with one byte that is not UTF-8 (non-utf8-txt, sha256 7c659c3b...). It must
    read extraction_failed before any provider request.
  - **fresh-f3.** A surveillance colonoscopy with a cold snare polypectomy in which the extent reached is never stated
    (txt, sha256 60b2c8a4...). Its review plan answers the `extent` detail "Not documented" through the details panel:
    the honest answer, so no clinical fact is asserted. It also stops and resumes the document, and approves nothing
    (approve_codes []).
- the author's expectations, sealed at 2026-11-05T01:36:10Z
  (/home/claude/cpt-studio-ux-walk2-20261105/walk2-expectations.json, mode 0400), before the offline prediction read
  the document.

Bounds (database counts, SELECT only, before and after):
- **fresh-fail:**
  - encounters, revisions and source files +1 each; jobs +1 (its extract);
  - provider runs, exchanges, tool calls, assessments, routing runs, proposals, decisions, member answers and reports
    +0.
- **fresh-f3:**
  - encounters, revisions and source files +1 each;
  - provider runs at most +5 (Corti's primary, Astra's and Fable's first readings, their two peer reviews), each sent
    at most once, and none created by the details save or the Resume;
  - provider exchanges at most +16, and their tool calls;
  - jobs at most +12 (11, and the details save's assess);
  - assessments at most +4 (3, and the details save's);
  - each assessment's routing run and proposals, and its audit pair;
  - member answers +1 (the one extent answer; the identical second save adds none);
  - reports + what the evidence records as HTTP 201 (the draft TXT and CSV);
  - decisions +0; second-review runs +0; finding confirmations +0.
- **jobs_active** back to 0.
- **Cost:** about 0.05 Corti credits and about 70,000 participant tokens (the first walk's measured use). A record,
  not a gate; the run bound above is the gate.
- **Mara** (effe4d0b-b449-4efd-b208-635ca1d09984) is not touched.
- **Whose rows are counted.** The bounds are read for the walk's own two encounters, created by review-agent. The
  owner uses the demo: between walk 1 and this declaration the owner account uploaded one document, and saved seven
  detail answers on it and on an older encounter (02:41 to 02:47Z), with its provider runs and assessments. Activity on
  any other encounter during the walk is ordinary use. It is identified read-only by encounter and acting account,
  reported, and never judged against these bounds or touched.

## Must not change

- **The ingress.** The quillmd vhost and every other sites-available file, except quillmd-cpt's proxy_pass line;
  nginx.conf, conf.d and every sites-enabled entry; the local routing of every co-tenant name/port pair and of an
  unknown host.
- **Co-tenants and host state.**
  - app.quillmd.com /health/ and the check-cotenants.sh results;
  - every container outside CPT Studio running at preflight (same id, still running);
  - every existing volume;
  - every Let's Encrypt lineage and renewal config, and the ACME account set.
- **QuillMD and CPT Studio's secrets.** The QuillMD rebuild, its database, users and files; /etc/cpt-studio/ and its
  seven files; /etc/cpt-studio-provider-sources/.
- **The database container.** cpt-studio-db keeps the same container, image, port and restart policy, running
  throughout; volumes cpt-studio-pg and cpt-studio-files; network cpt-studio-net.
- **Reference data and accounts.**
  - the two ReferenceSource rows, their licence notes and 34,665 reference facts;
  - the 3 passage sources and 62 passages;
  - the five accounts, their memberships and the two operator grants.
- **Every existing record.** Encounters, revisions, source files, contexts, routing runs, provider runs, exchanges, tool
  calls, assessments, proposals, decisions, member answers, clarifications, audit events, reports and jobs: no data
  migration, nothing re-assessed, every stored state recomputed unchanged.

## Validation per phase

Each phase's own checks (ops/INSTALL.md) must pass, and its receipt must say ok, with:
- tree.mode descendant-without-runtime-change;
- tree.head the merge commit that lands this declaration;
- door.declaration this file, and door.declaration_commit the commit that last touched it.

app additionally: the availability record, the switch's vhost sha256 before and after, and the drain's outcome, each
as above.

After app, by the operator:
- /health/ through the new port answers {status ok, service cpt-studio, data_mode synthetic-only, database ok, release
  b0dc3446c64c840cd01e9f37b8de3bad7aa954d4};
- the served app.js carries the two new notes, grepped in the static file the page names;
- a signed-in GET of /api/session without the client header answers 409 client_outdated, and with it 200;
- every /ops/ URL answers 404 to review-agent and 200 to ops-agent.

## Rollback per phase, and its limits

- **preflight, image and verify** change nothing that serves. A failed image leaves at most an unused image.
- **app fails before S3** (a credentials parse, migrate, the queue read, or the incoming web's health or smoke): the
  24c49a5032d5 web never stopped serving. The incoming web is removed and the old worker restarted (ops/INSTALL.md,
  the app phase's undo).
- **app fails at or after S3:** exactly as ops/INSTALL.md and the receipt set out. Each failure is a stop: the pair
  that is running serves while it is judged, and no remedy is taken without a decision recorded under this
  declaration.
- **After a successful app:** `--phase switch-back --provider-mode live --astra-mode live --fable-mode live
  --authorization-ref docs/foundation/rulings/2026-10-23-cpt-studio-gi.md` returns to 24c49a5032d5 without stopping
  the serving web first.
  - A preflight is run immediately before it.
  - b0dc3446c64c840cd01e9f37b8de3bad7aa954d4 records nothing 24c49a5032d5 would act on or show wrongly (no new record kind, no Python change), so no
    undo hazard is expected.
  - It returns the stopped and failed panels to their silence about leaving.
- **The pre-app dumps** are the only data-level way back. Restoring one deletes every row made after it, and is a
  separate declared act.

## What is not claimed

- No coding-accuracy figure and no reliable-coding claim. Clinical validation is NOT established: no qualified coder
  has adjudicated a predeclared set. The two walk documents are UI-state cases authored by the session to reach those
  states, and a passing synthetic case is not guaranteed accuracy.
- Functional completion, clinical accuracy validation and content-use permissions are reported separately. CPT
  descriptors, guidelines and NCCI procedure-to-procedure edits stay not verified (D3, D4 open), and no CPT descriptor
  text is shown.
- Privacy and subprocessor disclosures (decision (m)) stay the owner's open question.
- pypdf 6.21.2 and its advisories stay (interpretation 68); the dependency audit stays red.

## Stop conditions

Stop and diagnose on any of these. Do not rerun a phase, and do not upload a walk document.

The install:
- any non-zero phase exit, or a receipt that does not say ok;
- a tree mode other than descendant-without-runtime-change;
- the pre-preflight diff showing any difference;
- any non-200 in the app phase's availability record, a /health/ release other than 24c49a5032d5 or b0dc3446c64c840cd01e9f37b8de3bad7aa954d4, or any
  5xx;
- a routing, health, check-cotenants or file-hash difference other than quillmd-cpt's proxy_pass line, or a new nginx
  warning;
- a new image whose pypdf is not 6.21.2 or whose package list differs, or a build log showing apt or pip ran;
- a migrate log that applies anything;
- a stage this revision cannot run;
- before app: jobs_active not 0, a reserved or sending run, an unreconciled unknown outcome, or an audit event under
  10 minutes old;
- across app, a count moving that the phase does not declare, or a provider run created;
- states_recomputed naming any changed encounter;
- a leftover *-previous or *-next container after app.

During the walk:
- more provider runs, exchanges or jobs than the bounds above;
- any provider run for fresh-fail;
- a provider run created by the details save or the Resume;
- a second-review run or a finding confirmation;
- any decision;
- an unknown provider outcome (reconciling it is a separate, recorded decision);
- a provider authentication, quota or payment failure;
- verify_downloads or scan_customer exiting non-zero on anything the walk made;
- jobs_active not returning to 0 within the stage deadlines;
- any customer-visible provider identity or diagnostic;
- any action on an encounter the walk did not create.
