# Prospective declaration: CPT Studio harness repair 3 at cpt.quillmd.com (e6d451f03d86 to fd8040d71e44), installed blue/green with the demo kept serving, and 88d9db32 and 39f0ac49 re-assessed from their retained responses

Authority: the owner's second message of 2026-11-05, recorded verbatim in
docs/foundation/rulings/2026-10-23-cpt-studio-gi.md with this session's interpretations (a) to (k). Its words: "Astra and
Fable are primary code-finding participants. Corti remains another contributor, not a whitelist or veto over their
proposals. I want the complete harness working before calling the GI release complete." Its item 8 asks for "a declared,
reversible install; retained cases reassessed with sends disabled; then a fresh Word/PDF acceptance set", and its rules
say "keep cpt.quillmd.com accessible". Session a12d8fb3 is the integration and deployment owner for that directive.

The install is also governed by the 2026-10-23 directive cited in docs/foundation/mutations/20261023-cpt-studio-install.md:
- a protected synthetic demonstration;
- provider credentials server-side;
- app.quillmd.com and unrelated services preserved.

CPT Studio stays standalone: no QuillMD source, database, users, files, units or environment are shared, promoted or
edited. No purchase, agreement, new ACME account, new key or payment change is part of this act. D3 to D5 stay open as
recorded, and decision (m) stays the owner's open question.

Revision to install: fd8040d71e448c31ca6762e92ed9714e57aef4e5, the merge commit of PR #1477 (branch fix/cpt-studio-harness3-20261105, head
84707acd53ffab5cabb71a7a4478a37b5e14c0bd). Its cpt-studio/ tree is 0eac8315dd89aa12f1adffe5359c3c15d7204af7, byte for byte the branch head's. Image tag
cpt-studio:fd8040d71e44. Its citation, on fd8040d71e448c31ca6762e92ed9714e57aef4e5: CI run 42159987582 success (Fresh application tests; Marketing build; Private browser and accessibility); secrets-scan run 42159987651 success; cpt-studio run 42159987583: its checks, migrations and every test pass (6,011 Django, 524 ops, 43 verification), and its dependency audit is red on pypdf 6.21.2's seven advisories, accounted for and not resolved (docs/cpt-harness/repair3-20261105/pypdf-advisories-accounting.md); cpt-studio is not a required check.

The PR carries harness repair 3 and its four refutation cycles: 18 lens runs in sealed sandboxes, 127 findings, each
reproduced before its repair and every input pinned (cpt-studio/HARNESS.md, "Harness repair 3" to "Harness repair 3,
refutation cycle 4"). Under the two-cycle rule F-TIME R, F-SECTIONS T and L (cycle 2) and F-ACTS (cycle 4) are dropped
and read as the base reads them.

It replaces the live revision e6d451f03d86f11e8454c46e14cda6337bdbef23, installed 2026-11-05 under
docs/foundation/mutations/20261105-cpt-studio-harness-repair-install.md, which runs image cpt-studio:e6d451f03d86. That
declaration and its receipts stay as they are, and that image is kept as the rollback image.

Execute each phase separately through scripts/run-ruled-mutation.sh with
`python3 -B cpt-studio/ops/install.py --phase <phase> --revision fd8040d71e448c31ca6762e92ed9714e57aef4e5 --receipts /home/claude/cpt-studio-install-20261023`.

Phases, in this order:
1. preflight;
2. image;
3. app, with `--provider-mode live --astra-mode live --fable-mode live --authorization-ref
   docs/foundation/rulings/2026-10-23-cpt-studio-gi.md` and no `--access-check`;
4. verify;
5. reassess, with `--encounter 88d9db32-65b5-4a55-98ee-b82ce0da8941 --encounter 39f0ac49-eecc-4c72-bd23-9d542f7f4aa3
   --dry-run`, then the same without `--dry-run` (one phase run names both; the installer runs reassess_retained for
   each in its own one-shot and reads each encounter's jobs before and after).

Run them from a clean, detached checkout of the merge commit that lands this declaration. That commit must be a
descendant of the revision that changes nothing under cpt-studio/, scripts/run-ruled-mutation.sh or scripts/lib/. Read
each receipt before the next phase. The receipts directory is the live install's own, and no receipt there is
changed: each file is created once.

Not run: secrets, db, reference, provision, http-vhost, cert, https-vhost, rollback-vhost, passages, license-note,
operators and switch-back. Their objects exist and do not change, and nothing in this revision asks for them.

Between e6d451f03d86f11e8454c46e14cda6337bdbef23 and fd8040d71e448c31ca6762e92ed9714e57aef4e5, these are byte-identical:
- the installer, cpt-studio/ops/install.py and ops/INSTALL.md;
- cpt-studio/deploy/ (Dockerfile, entrypoint, gunicorn, nginx templates, .dockerignore);
- cpt-studio/requirements.txt, requirements.in and requirements-dev.txt;
- cpt-studio/cptstudio/;
- cpt-studio/studio/models.py and every migration under cpt-studio/studio/migrations/;
- scripts/run-ruled-mutation.sh, scripts/lib/ and scripts/check-cotenants.sh.

Before preflight the operator runs, in the act's checkout,
`git diff --quiet e6d451f03d86f11e8454c46e14cda6337bdbef23 HEAD -- scripts/check-cotenants.sh scripts/run-ruled-mutation.sh scripts/lib cpt-studio/deploy cpt-studio/requirements.txt cpt-studio/requirements.in cpt-studio/requirements-dev.txt cpt-studio/cptstudio cpt-studio/ops/install.py cpt-studio/ops/INSTALL.md cpt-studio/studio/migrations cpt-studio/studio/models.py`.
Any difference is a stop.

## Delta shipped (e6d451f03d86 to fd8040d71e44)

    git diff --stat e6d451f03d86f11e8454c46e14cda6337bdbef23 fd8040d71e448c31ca6762e92ed9714e57aef4e5 -- cpt-studio: 66 files changed, 18385 insertions(+), 362 deletions(-)

The files that change what the service does are nineteen, all Python under cpt-studio/studio/:
- **studio/validation/engine.py:**
  - P-ADMIT2 (a participant's code admitted on CPT Studio's own reading, whatever Corti did) and the provider-neutral
    admission (held, as Corti's code is, for an act stated done inside a service documented in doubt);
  - competition, erring toward competing;
  - the participants' wording.
- **studio/gi/services.py, the act reader** (gi-services@5):
  - F-TIME's negation, time, place, source, condition, infinitive and later-failure readings, each narrowed or recorded
    as the four cycles decided;
  - F-NEG S (tattoo versus resection);
  - the fronted frame.

  F-ACTS is dropped: the foreign-body reading is the base's.
- **studio/jobs.py, studio/participants/ (loop, reading, peer, prompt, replay, openai_astra, anthropic_fable),
  studio/review.py, studio/reports.py, studio/serializers.py, studio/answers.py, studio/customer_api.py,
  studio/validation/review_view.py, studio/validation/checks.py, studio/validation/reconcile.py and
  participant_access_check.py:**
  - F-STOP (a recoverable Stop and Resume from the verified record, one chain's usage and cost, no live/replay mixing);
  - F-CONTRACT (anthropic-messages@cptstudio-harness-4: an undeclared field set aside before validation, never read);
  - the competing row's review overlay;
  - the API row's chain usage.

There is no migration, no model change and no new dependency.
- **Reader labels:** gi-services@4 to @5, cpt-studio-validation@7 to @8. gi-routing@7, gi-context@4 and
  gi-catalogue@1 are unchanged: detect.py, cues.py, sections.py and context.py are byte-identical to the live
  revision's.
- **New readings** apply to new uploads, addenda, member saves, the stages they queue, and the two reassessments below.
  The install re-assesses or re-sends no other encounter.

## Measured before this declaration

**Image precheck** (2026-11-06T03:08Z, /home/claude/cpt-studio-ux-tools-20261105/precheck_image.py, which builds exactly
as the image phase does, without its labels):
- the image is cpt-studio-precheck:84707acd53ff
  (sha256:5dbbecc34cca8120d16a2bedd03b80543b6de63e78ef02975c68ce3805258b93), built from the branch head;
- steps 2/8 to 6/8 (apt, user, WORKDIR, requirements, pip) are CACHED; only the application copy and collectstatic ran;
- its `dpkg-query` list (166 packages, sha256 prefix 500b6abda58b9a3e) is identical to cpt-studio:e6d451f03d86's;
- pypdf is 6.21.2 and the uid is 10150.

The builder is not pruned between that measurement and the image phase.

**Offline predictions** with this revision's own code (/home/claude/cpt-studio-harness3-20261105/install/predict_h3.sh
84707acd53ffab5cabb71a7a4478a37b5e14c0bd; output install/predict.out). They run over one read-only `pg_dump -Fc` of the
live database:
- taken 2026-11-06T03:08:47Z through the database container's own pg_dump in a read-only transaction;
- sha256 prefix 64f2a230e54d4d92, 39 TABLE DATA entries;
- restored into throwaway databases on the test server gi4-cpt-test-pg (127.0.0.1:55461), never the live port.

The installer's own one-shot scripts run as its app phase runs them, with every provider disabled:
- **migrate:** applies nothing ("No migrations to apply").
- **RECOMPUTE_STATES:** {"encounters": 59, "changed": {}} with this revision and with e6d451f03d86's code. It is the
  same again after the two reassessments below.
- **The control:** one sent run of a reviewed encounter planted 'unknown' turns that encounter to provider_unknown, so
  the measurement can see a change.
- **The reassessments of 88d9db32 and 39f0ac49,** as the reassess phase makes them: reassess_retained --participants
  astra,fable, then run_worker --once with Astra and Fable live, no credential file, and Corti disabled. Each dry run
  names its plan and queues nothing:
  - 88d9db32: final assessment 4657b3cd-a7e2-47c5-bc77-8f412e0c12f5, Astra's run f4167034-2d38-4688-a4e1-034b1d11bef2
    with its peer run 3fc81ee9-9c2b-4123-bd4c-8a7916ecc5e6, and Fable's runs as the dry run lists them;
  - 39f0ac49: final assessment e0c1c149-bb68-49f4-b81f-c56ee90d7397, Astra's run
    a873ac6a-d28d-4c55-bd1c-923bb6f3c8b1 with its peer run 6b3e413f-a546-4ca6-8fcc-27d316868b98, and Fable's runs as
    the dry run lists them.

  The real runs queue one assess job each, and the worker makes them from the retained answers:
  - nothing is sent: provider runs 124 to 124, sent 113 to 113, provider exchanges 83 to 83, tool calls 57 to 57;
  - tables: studio_assessment +2, studio_proposal +39, studio_clarification +6, studio_job +2, studio_auditevent +4. No
    other table moves;
  - **88d9db32** goes from needs_clarification to **ready_for_review**. Ready: 45380, 45381 and 43239 (Corti, with Astra
    and Fable), and 43249, 45390 and 45385 (Astra and Fable alone), all selected. There is no open question; the
    alternatives are informational; the decompression stays unsupported and uncoded;
  - **39f0ac49** stays reviewed, and its current assessment becomes the new one:
    - 43239, 45380 and 45385 (Corti, with Astra and Fable) are held, each by two open questions, performed_status and
      extent, because its labelled procedure paragraphs inside the Indications read as the base reads them (F-SECTIONS
      L dropped);
    - Astra's and Fable's 43247 is listed: "the bolus was removed" is no documented act, F-ACTS being dropped;
    - the owner's six earlier answers stay on the earlier assessment as recorded.

The predictions hold only while the re-read baseline shows no live activity on 88d9db32 or 39f0ac49.

## Baseline (read-only, 2026-11-06T04:37:46Z; re-read immediately before the commit that lands this declaration; this act's preflight receipt is binding)

    read_at 2026-11-06T04:37:46Z
    transaction_read_only on
    encounters 59
    revisions 59
    source_files 53
    contexts 75
    routing_runs 69
    provider_runs 124
    provider_runs_sent 113
    assessments 94
    proposals 1209
    clarifications 142
    decisions 39
    decision_invalidations 0
    audit_events 692
    reports 139
    jobs 333
    jobs_active 0
    users 5
    memberships 3
    workspaces 1
    login_attempts 74
    reference_sources 2
    reference_facts 34665
    studio_migrations 12
    studio_migration_last 0012_cux_worker_beat
    studio_providerexchange 83
    studio_toolcall 57
    studio_findingconfirmation 0
    studio_passagesource 3
    studio_referencepassage 62
    studio_memberanswer 14
    studio_memberanswerrevocation 0
    studio_operatorgrant 2
    studio_operatorrevocation 0
    studio_workerbeat 1
    column studio_decision.modifiers present
    column studio_encounter.client_key present
    column studio_encountercontext.document_date present
    column studio_reportartifact.audience present
    run_participant astra independent failed 1
    run_participant astra independent not_sent 1
    run_participant astra independent succeeded 13
    run_participant astra peer_review succeeded 15
    run_participant fable independent succeeded 14
    run_participant fable peer_review succeeded 11
    credits_sum 3.062703999999999865
    usage_keys astra input_tokens,input_tokens_details,output_tokens,output_tokens_details,total_tokens
    usage_keys corti creditsConsumed
    usage_keys fable cache_creation,cache_creation_input_tokens,cache_read_input_tokens,inference_geo,input_tokens,output_tokens,output_tokens_details,service_tier,speed
    encounter_state extraction_failed 1
    encounter_state needs_clarification 29
    encounter_state no_codes 4
    encounter_state ready_for_review 4
    encounter_state reviewed 21
    run astra independent failed t f 1
    run astra independent not_sent f f 1
    run astra independent succeeded t f 13
    run astra peer_review succeeded f t 1
    run astra peer_review succeeded t f 14
    run corti primary not_sent f f 4
    run corti primary succeeded f t 4
    run corti primary succeeded t f 59
    run corti second_review succeeded t f 2
    run fable independent succeeded t f 14
    run fable peer_review succeeded f t 1
    run fable peer_review succeeded t f 10
    job analyze succeeded 58
    job assess succeeded 94
    job astra cancelled 2
    job astra succeeded 14
    job astra_peer succeeded 15
    job extract succeeded 59
    job fable cancelled 1
    job fable succeeded 14
    job fable_peer succeeded 11
    job predict succeeded 63
    job review2 succeeded 2
    runs_unreconciled_unknown 0
    runs_reserved_or_sending 0
    last_audit detail.answered 2026-11-05T20:12:09Z 30338
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
    assessments_by_engine cpt-studio-validation@6 15
    assessments_by_engine cpt-studio-validation@7 8

## Expected changes, per phase

- **preflight:** none. One random ACME probe file is written and removed.
- **image:** a new local image cpt-studio:fd8040d71e44.
  - It is built from git archive of fd8040d71e448c31ca6762e92ed9714e57aef4e5 cpt-studio/, labelled with the revision, user 10150,
    CPT_STUDIO_RELEASE_SHA=fd8040d71e448c31ca6762e92ed9714e57aef4e5.
  - The apt, user, WORKDIR, requirements and pip steps are CACHED, as measured above.
  - The operator checks offline, after the phase: pypdf 6.21.2 in the new image, and its
    `dpkg-query -W -f '${Package} ${Version}\n'` identical to cpt-studio:e6d451f03d86's.
  - A build log showing apt or pip ran is a stop before app.
- **Before app, outside the installer and read-only on the database:** one `pg_dump -Fc` of the cptstudio database,
  through the database container's own pg_dump, to
  /home/claude/cpt-studio-install-20261023/pre-app-fd8040d71e44-<UTC>.dump (0600). Its `pg_restore --list` shows 39 TABLE
  DATA entries. It holds synthetic documents, responses and password hashes, and is kept until a separate, recorded
  decision removes it.
- **app (the blue/green switch; ops/INSTALL.md "Phases"):**
  - the loader parses the Corti credentials and each participant's credentials file in the worker's mount layout, with
    no network; migrate (a one-shot) applies nothing; the queue read finds 0 stages this revision cannot run;
  - S1: cpt-studio-web-next starts on the idle port and answers /health/ with release fd8040d71e448c31ca6762e92ed9714e57aef4e5, its sign-in page, and
    every static file that page names;
  - S2: the e6d451f03d86 worker is parked; its current stage finishes; none is expected running;
  - S3: the quillmd-cpt vhost's upstream is switched to the idle port, and the vhost differs in its proxy_pass line
    alone. `sudo -n nginx -t` passes with no new warning, `sudo -n systemctl reload nginx` reloads gracefully, and
    https://cpt.quillmd.com/health/ serves fd8040d71e448c31ca6762e92ed9714e57aef4e5;
  - S4: the new worker starts;
  - S5: the old web is drained (at least 130 s, at most 600 s), stopped and parked as cpt-studio-web-previous; the
    incoming web is renamed cpt-studio-web;
  - availability (the public /health/ every 0.5 s, from before S1 to the end): every sample 200; releases_seen
    e6d451f03d86f11e8454c46e14cda6337bdbef23 then fd8040d71e448c31ca6762e92ed9714e57aef4e5; non_200_count 0;
  - states_recomputed {"encounters": <the baseline's encounters>, "changed": {}} (predicted above). The parked pair is
    removed;
  - nothing is sent: no access check is run, and the installer's one-shots run with every provider disabled;
  - counts after app: every count equals the pre-app reading, apart from a member's own use during the act.
    - That use is identified read-only by encounter and acting account, recorded, and set aside before the comparison.
    - Any other movement is the act's and a stop.
    - studio_workerbeat stays 1 row named 'worker'. Its revision becomes fd8040d71e448c31ca6762e92ed9714e57aef4e5, and its beat_at advances once the new
      worker beats (S4).
- **verify:** no difference from the preflight baseline except the quillmd-cpt vhost's proxy_pass line.
  https://cpt.quillmd.com/health/ serves fd8040d71e448c31ca6762e92ed9714e57aef4e5 under normal certificate verification, with the security headers once
  each.
- **reassess (88d9db32-65b5-4a55-98ee-b82ce0da8941 and 39f0ac49-eecc-4c72-bd23-9d542f7f4aa3, one run each for the dry run and the real one):**
  - each dry run names its plan above (the final assessment, Astra's and Fable's first readings and peer reviews by id)
    and queues nothing;
  - each real run queues exactly one assess job, which the running worker makes from the retained answers:
    - nothing is sent: provider runs +0, sent runs +0, provider exchanges +0, tool calls +0, credits_sum unchanged;
    - tables, together, as predicted above: studio_assessment +2, studio_proposal +39, studio_clarification +6,
      studio_job +2, studio_auditevent +4;
  - the prior assessments, their proposals and clarifications, the encounters' decisions and the owner's answers stay as
    they are. Each new assessment is added beside them and becomes current. The act creates, removes or invalidates no
    decision;
  - 88d9db32 then reads ready_for_review and 39f0ac49 reviewed, with the codes above, as predicted.
- Image cpt-studio:e6d451f03d86 is kept: it is the rollback image. Nothing removes any image.

## What the install sends

Nothing. No access check is run, every one-shot runs with Corti and the participants disabled, and the reassessments
build and send no request (their participants' readings are the retained ones).

Immediately before app:
- jobs_active 0;
- no provider run reserved or sending;
- no unreconciled unknown outcome;
- no audit event newer than 10 minutes.

Checked after app and after each reassess:
- provider runs, sent runs, provider exchanges, tool calls and credits_sum equal their pre-app reading;
- no provider run has a created_at at or after the app receipt's started_at.

## After the install: the fresh acceptance walk (ordinary use, not a phase)

The directive's item 8 runs as ordinary use of the installed service, after verify and reassess. The synthetic agent
accounts review-agent and ops-agent carry it out.
- **Its inputs:** two synthetic documents (h3a, an upper endoscopy and colonoscopy; h3b, a colonoscopy, with a Stop and
  Resume) and their expectations, kept in /home/claude/cpt-studio-harness3-20261105/acceptance/sealed/. They were
  written and sealed (mode 0400, modified 2026-11-05T22:27:01Z) before any code read them. Their sha256 prefixes,
  taken from the bytes for this declaration, are 5bbbc6b6c5465ca1 (h3a-egd-colonoscopy.txt), 30b557b48defa847
  (h3b-colonoscopy.txt) and 3cb92ddac087a666 (expectations-h3.json), and the walk checks them before it reads anything.
- **What it sends:** real requests to Corti, Astra and Fable through the existing authorized accounts. Its usage and
  cost are recorded from the provider runs it creates.
- **What it claims:** the report labels agent-executed approvals as such, and claims no human clinical review.

## Must not change

- Every other encounter's assessments, proposals, clarifications, decisions, reports and audit rows.
- The reference sources (cms-pfs-rvu26d, cms-mue-practitioner-2026q4) and their facts.
- Users, memberships, workspaces, operator grants, the credentials files and their modes.
- app.quillmd.com, quillmd.com and every co-tenant's status (scripts/check-cotenants.sh before and after).
- The live database's schema (studio_migrations 12, last 0012_cux_worker_beat).

## Validation per phase

Each phase's receipt is read before the next:
- preflight: every check passes;
- image: CACHED steps and the dpkg list as declared;
- app: availability, releases_seen, states_recomputed and the counts as declared;
- verify: the vhost and health as declared;
- reassess: each dry run's plan, then the job, the counts and the encounter's reading as declared.

## Rollback per phase, and its limits

- image: nothing to undo; the new image is unused until app.
- app: the installer's own undo restores the e6d451f03d86 web and worker (rollback-app), and the vhost's proxy_pass;
  the rolled-back revision recomputes states. If reassess ran, its added assessments stay, as every assessment does,
  and the rolled-back revision reads the encounters' current assessments as it reads any assessment it did not make.
- reassess: an added assessment is never removed; a wrong reassessment is answered by a new one, never by deleting
  rows.

## What is not claimed

Functional completion on the installed site is judged by verify, reassess and the acceptance walk. Clinical accuracy,
billing readiness and complete three-engine operation are not claimed, and this act establishes none of them.
- NCCI PTP stays unconnected: modifiers are considerations only.
- D3 to D5 and decision (m) stay open.
- **Undelivered, because their rules were dropped under the two-cycle rule:**
  - directive item 4's "completed marking versus future localization";
  - the Word walk's title routing;
  - the food-bolus act, so 39f0ac49's 43247 stays listed.
- **The base's own false READYs that this release does not close** (HARNESS.md, cycles 3 and 4) stand, among them "The
  polyp was left in place." under a procedure line naming the polypectomy. So do the recorded false holds.
- The cpt-studio workflow's dependency audit stays red on pypdf 6.21.2's seven advisories. They are accounted for in
  docs/cpt-harness/repair3-20261105/pypdf-advisories-accounting.md, not resolved; it is not a required check; and no
  readiness for wider or untrusted uploads is claimed.

## Stop conditions

Any of these stops the act:
- an undeclared count movement;
- a provider run, exchange or tool call created by app, verify or reassess;
- a non-200 availability sample, or a releases_seen other than the two declared;
- states_recomputed naming any changed encounter;
- a build log showing apt or pip ran;
- a leftover *-previous or *-next container after app;
- a dry run that queues a job, or a reassess that queues more than one;
- 88d9db32 or 39f0ac49 not reading as predicted.
