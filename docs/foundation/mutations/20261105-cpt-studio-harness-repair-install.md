# Prospective declaration: the CPT Studio GI core and multi-agent harness repair at cpt.quillmd.com (b0dc3446c64c to e6d451f03d86), installed blue/green with the demo kept serving, and 88d9db32 re-assessed from its retained responses

Authority: the owner's directive of 2026-11-05 ("Complete the CPT Studio GI core and multi-agent harness repair, install
it on https://cpt.quillmd.com, and verify the actual customer workflow. Fix the shared system, not just one document."),
recorded verbatim in docs/foundation/rulings/2026-10-23-cpt-studio-gi.md with this session's interpretations (a) to (k).
Session a12d8fb3 is the integration and deployment owner for that directive.

The directive's install rule governs every phase here: "Keep the existing site accessible while working. Use the normal
installation and rollback process. Do not pause the demo by default, weaken clinical safeguards, or call incomplete work
finished." Its item 9: "Merge through the required project gates and install using a declared, reversible deployment
that keeps the site available. Reassess the affected encounter from retained responses with provider sends disabled.
Preserve the prior assessment and decisions. Verify the actual served behavior and explain any remaining omissions."

The install is also governed by the 2026-10-23 directive cited in docs/foundation/mutations/20261023-cpt-studio-install.md:
- a protected synthetic demonstration;
- provider credentials server-side;
- app.quillmd.com and unrelated services preserved.

CPT Studio stays standalone: no QuillMD source, database, users, files, units or environment are shared, promoted or
edited. No purchase, agreement, new ACME account, new key or payment change is part of this act. D3 to D5 stay open as
recorded, and decision (m) (privacy and subprocessor disclosures) stays the owner's open question.

Revision to install: e6d451f03d86f11e8454c46e14cda6337bdbef23, the merge commit of PR #1473 (branch fix/cpt-studio-marked-adverb-20261105, head
9d8357f3ada59bf736f410421c782cc9687fb025: its round-7 commit 3928de405f46 with main's runner pin, PR #1474, merged
in). It carries PR #1472, the GI core and harness repair, merged as 92b24d3b9f5b80cc819a952cc480004f62e5fa55, and
refutation rounds 4 to 7 over it. Image tag cpt-studio:e6d451f03d86. Its
citation, on e6d451f03d86f11e8454c46e14cda6337bdbef23: CI run 42081865874 success (Fresh application tests, on ubuntu-24.04 since PR #1474; Marketing build; Private browser and accessibility); secrets-scan run 42081865855 success; cpt-studio run 42081866049: its checks, migrations and every test pass (5,905 Django, 524 ops, 43 verification, node 131), and its dependency audit is red on pypdf 6.21.2's seven advisories (interpretation 68), as on main since 2026-10-31; cpt-studio is not a required check

92b24d3b9f5b is not installed on its own. Before this declaration was written, refutation round 4 found a released
earlier-time marking form in it. Rounds 4 to 6 then found the repair package's two releasing readings releasing tattoos
placed at another time or by another provider. Round 6 dropped both readings under the two-cycle rule, so they read as
the live revision reads them. Round 7, a lens over the whole remaining diff, found two more:
- the withheld listing's kindless branch, dropped;
- a second lesion's act bundled into another lesion's, now bundled only at one certain lesion.

See HARNESS.md "Refutation round 4" to "Refutation round 7".

It replaces the live revision b0dc3446c64c840cd01e9f37b8de3bad7aa954d4, installed 2026-11-05 under
docs/foundation/mutations/20261105-cpt-studio-leave-note-install.md, which runs image cpt-studio:b0dc3446c64c. That
declaration and its receipts stay as they are, and that image is kept as the rollback image.

Execute each phase separately through scripts/run-ruled-mutation.sh with
`python3 -B cpt-studio/ops/install.py --phase <phase> --revision e6d451f03d86f11e8454c46e14cda6337bdbef23 --receipts /home/claude/cpt-studio-install-20261023`.

Phases, in this order:
1. preflight;
2. image;
3. app, with `--provider-mode live --astra-mode live --fable-mode live --authorization-ref
   docs/foundation/rulings/2026-10-23-cpt-studio-gi.md` and no `--access-check`;
4. verify;
5. reassess, with `--encounter 88d9db32-65b5-4a55-98ee-b82ce0da8941 --dry-run`, then the same without `--dry-run`.

Run them from a clean, detached checkout of the merge commit that lands this declaration. That commit must be a
descendant of the revision that changes nothing under cpt-studio/, scripts/run-ruled-mutation.sh or scripts/lib/. Read
each receipt before the next phase. The receipts directory is the live install's own, and no receipt there is
changed: each file is created once.

Not run: secrets, db, reference, provision, http-vhost, cert, https-vhost, rollback-vhost, passages, license-note,
operators and switch-back. Their objects exist and do not change, and nothing in this revision asks for them.

Between b0dc3446c64c840cd01e9f37b8de3bad7aa954d4 and e6d451f03d86f11e8454c46e14cda6337bdbef23, these are byte-identical:
- the installer, cpt-studio/ops/install.py and ops/INSTALL.md;
- cpt-studio/deploy/ (Dockerfile, entrypoint, gunicorn, nginx templates, .dockerignore);
- cpt-studio/requirements.txt, requirements.in and requirements-dev.txt;
- cpt-studio/cptstudio/;
- cpt-studio/studio/models.py and every migration under cpt-studio/studio/migrations/;
- scripts/run-ruled-mutation.sh, scripts/lib/ and scripts/check-cotenants.sh.

Before preflight the operator runs, in the act's checkout,
`git diff --quiet b0dc3446c64c840cd01e9f37b8de3bad7aa954d4 HEAD -- scripts/check-cotenants.sh scripts/run-ruled-mutation.sh scripts/lib cpt-studio/deploy cpt-studio/requirements.txt cpt-studio/requirements.in cpt-studio/requirements-dev.txt cpt-studio/cptstudio cpt-studio/ops/install.py cpt-studio/ops/INSTALL.md cpt-studio/studio/migrations cpt-studio/studio/models.py`.
Any difference is a stop.

## Delta shipped (b0dc3446c64c to e6d451f03d86)

    git diff --stat b0dc3446c64c840cd01e9f37b8de3bad7aa954d4 e6d451f03d86 -- cpt-studio: 42 files changed, 3496 insertions(+), 391 deletions(-)
      runtime, cpt-studio/studio/ (8 files, 620 insertions, 104 deletions):
        validation/engine.py 355, gi/services.py 207, validation/reconcile.py 104, validation/checks.py 28,
        gi/catalogue.py 17, operator/ops.js 6, customer_api.py 5, gi/detect.py 2 (its version label only)
      tests, cpt-studio/tests/ (27 files: 24 Python test modules, tests/operator/ops.test.cjs and two battery
        declarations under tests/fixtures/gi4/declarations/; 2059 insertions, 277 deletions)
      verification tooling (4 files, from 29a0c460f, PR #1471, merged to main after b0dc3446 and before this change):
        ops/verify_browser.cjs, ops/verification/test_verify_browser.cjs, ops/verification/samples/make_samples.py and
        customer-encounter-details.json
      records: cpt-studio/HARNESS.md, ACCURACY-RESIDUALS.md, COVERAGE.md
    outside cpt-studio (10 files): .github/workflows/test.yml (PR #1474: the rebuild's "Fresh application tests" job
      pinned to ubuntu-24.04; CI only), and records only: CPT-HARNESS-CHECKLIST.md, CPT-CORE-UX-CHECKLIST.md,
      docs/cpt-harness/repair-20261105/ (2), docs/deploy-reports/ (2), docs/foundation/RULINGS.md, the rulings file
      docs/foundation/rulings/2026-10-23-cpt-studio-gi.md and docs/foundation/mutations/20261105-cpt-studio-leave-note-install.md

The files that change what the service does are eight, all Python or JavaScript under cpt-studio/studio/:
- studio/validation/engine.py:
  - P-ADMIT, which replaces D14: an independent participant's first-reading proposal is admitted through the proposal
    provider's own path;
  - the own-passage release's included-act rule;
  - the refused-response completeness rule;
  - per-act competition;
  - the whole-service own-role rule.

  The routing-era negation release is the live revision's rule (refutation round 3 dropped stage 3's change to it).
- studio/validation/reconcile.py:
  - the act-included and unsupported-act rules;
  - the resection's technique and a biopsy of a removed lesion, bundled only at one certain lesion (round 7);
  - the lift injection's site agreement;
  - a failed attempt listed;
- studio/validation/checks.py: the participants' check wording under P-ADMIT;
- studio/gi/services.py and studio/gi/catalogue.py:
  - the repair package's reader patch (applied verbatim at 70f18d1bb), less its two releasing readings and its bare
    "excised", which rounds 5 and 6 dropped;
  - the holding repairs of refutation rounds 1 to 5 (HARNESS.md "GI core and harness repair (2026-11-05)" and
    "Refutation round 1" to "Refutation round 6");
- studio/gi/detect.py: its version label only (gi-routing@7);
- studio/customer_api.py: a code the numbered list suggests is never listed again as not suggested;
- studio/operator/ops.js: the operator console's "Independent participant" badge.

There is no migration, no model change and no new dependency.
- Reader labels: gi-routing@6 to @7, gi-services@3 to @4, cpt-studio-validation@6 to @7. gi-context@4 and gi-catalogue@1
  are unchanged; the catalogue's content changes ride on cpt-studio-validation@7, as in every earlier round.
- No fingerprint reads a label (engine._fingerprint reads each check's id and status only).
- New readings apply to new uploads, addenda, member saves, the stages they queue, and the one reassessment below. The
  install re-assesses or re-sends no other encounter.

## Measured before this declaration

**Image precheck** (2026-11-05T16:52Z, /home/claude/cpt-studio-ux-tools-20261105/precheck_image.py, which builds exactly
as the image phase does, without its labels):
- cpt-studio-precheck:3928de405f46
  (sha256:00c0bd21fd57b2b73ccc346d3359a523be2ae754460a95ba2ead01f10fbc14b3), built from PR #1473's round-7 commit
  3928de405f4699093cb557c3a0d1682f7816047e;
- its cpt-studio/ tree is 81327159c7c48715c39262f0e6a33530a1b25044, byte for byte e6d451f03d86f11e8454c46e14cda6337bdbef23's
  (git rev-parse <commit>:cpt-studio);
- steps 2/8 to 6/8 (apt, user, WORKDIR, requirements, pip) CACHED; only the application copy and collectstatic ran;
- its `dpkg-query` list (166 packages) is identical to cpt-studio:b0dc3446c64c's;
- pypdf 6.21.2, uid 10150;
- the image carries round 7's `_one_lesion` and none of the dropped code (the templates, the kindless branch);
- /app/studio/operator/ops.js, which the console's view serves, carries the new badge.

The builder is not pruned between that measurement and the image phase.

**Offline predictions** with this revision's own code (/home/claude/cpt-studio-harness2-20261105/tools/predict_h2.sh
3928de405f4699093cb557c3a0d1682f7816047e; output install/predict-3928de405f46.txt). They run over one read-only
`pg_dump -Fc` of the live database:
- taken 2026-11-05T16:48:07Z through the database container's own pg_dump in a read-only transaction;
- sha256 prefix 583bd8d5363e421e, 39 TABLE DATA entries;
- restored into throwaway databases on the test server gi4-cpt-test-pg (127.0.0.1:55461), never the live port.

The installer's own one-shot scripts run as its app phase runs them, with every provider disabled:
- **migrate:** applies nothing ("No migrations to apply").
- **RECOMPUTE_STATES:** {"encounters": 55, "changed": {}} with this revision, and the same with b0dc3446c64c's code. It
  is the same again after the reassessment below.
- **The control:** one sent run of a reviewed encounter planted 'unknown' turns that encounter to provider_unknown, so
  the measurement can see a change.
- **The reassessment of 88d9db32,** as the reassess phase makes it: reassess_retained --participants astra,fable, then
  run_worker --once with Astra and Fable live, no credential file, and Corti disabled.
  - The dry run names the plan:
    - final assessment 0e7c965b-2c69-4898-862f-5fbe3d3fd65d;
    - Astra's run f4167034-2d38-4688-a4e1-034b1d11bef2 and its peer run 3fc81ee9-9c2b-4123-bd4c-8a7916ecc5e6;
    - Fable's run 437e6278-4bbc-4b0b-b4a9-727482b7fdbf and its peer run d6a8101c-14fe-4136-ab10-1cabe93a336d.

    It queues nothing.
  - The real run queues one assess job, and the worker makes it from the retained answers.
  - Nothing is sent: provider runs 107 to 107, sent 97 to 97, provider exchanges 63 to 63.
  - Tables: studio_assessment +1, studio_proposal +26, studio_clarification +1, studio_job +1, studio_routingrun +1,
    studio_auditevent +2. No other table moves.
  - 88d9db32 reads needs_clarification before and after.
    - Ready: 45380 and 43239 (Corti), and 43249, 45390 and 45385 (Astra and Fable, admitted under P-ADMIT), all
      selected.
    - Held: 45381 (Corti), selected, with one open question, the tattoo conflict. This is the live revision's own
      reading: the repair package's coordinated reading of the impression's "marked with submucosal tattoo ... and not
      resected today" was dropped in refutation round 6.
    - Listed as unsupported: the decompression, an act no upper-endoscopy code accounts for.
    - Informational: the 20 alternatives, which are raw lists and never promoted.
    - Completeness reads: "Coding for this encounter is incomplete: 1 documented service or act without a supported
      proposal; 2 conflicts in the record; 1 open question." The two conflicts are the injection and the tattoo, each
      stated both as performed and as not.

The predictions hold only while the re-read baseline shows no live activity on 88d9db32.

## Baseline (read-only, 2026-11-05T18:45:54Z; re-read immediately before the commit that lands this declaration; this act's preflight receipt is binding)

    read_at 2026-11-05T18:45:54Z
    transaction_read_only on
    encounters 55
    revisions 55
    source_files 49
    contexts 71
    routing_runs 64
    provider_runs 107
    provider_runs_sent 97
    assessments 86
    proposals 1068
    clarifications 127
    decisions 30
    decision_invalidations 0
    audit_events 604
    reports 129
    jobs 300
    jobs_active 0
    users 5
    memberships 3
    workspaces 1
    login_attempts 67
    reference_sources 2
    reference_facts 34665
    studio_migrations 12
    studio_migration_last 0012_cux_worker_beat
    studio_providerexchange 63
    studio_toolcall 40
    studio_findingconfirmation 0
    studio_passagesource 3
    studio_referencepassage 62
    studio_memberanswer 8
    studio_memberanswerrevocation 0
    studio_operatorgrant 2
    studio_operatorrevocation 0
    studio_workerbeat 1
    column studio_decision.modifiers present
    column studio_encounter.client_key present
    column studio_encountercontext.document_date present
    column studio_reportartifact.audience present
    run_participant astra independent succeeded 10
    run_participant astra peer_review succeeded 12
    run_participant fable independent succeeded 10
    run_participant fable peer_review succeeded 10
    credits_sum 2.832087999999999877
    usage_keys astra input_tokens,input_tokens_details,output_tokens,output_tokens_details,total_tokens
    usage_keys corti creditsConsumed
    usage_keys fable cache_creation,cache_creation_input_tokens,cache_read_input_tokens,inference_geo,input_tokens,output_tokens,output_tokens_details,service_tier,speed
    encounter_state extraction_failed 1
    encounter_state needs_clarification 28
    encounter_state no_codes 4
    encounter_state ready_for_review 4
    encounter_state reviewed 18
    run astra independent succeeded t f 10
    run astra peer_review succeeded f t 1
    run astra peer_review succeeded t f 11
    run corti primary not_sent f f 4
    run corti primary succeeded f t 4
    run corti primary succeeded t f 55
    run corti second_review succeeded t f 2
    run fable independent succeeded t f 10
    run fable peer_review succeeded f t 1
    run fable peer_review succeeded t f 9
    job analyze succeeded 54
    job assess succeeded 86
    job astra cancelled 1
    job astra succeeded 10
    job astra_peer succeeded 12
    job extract succeeded 55
    job fable cancelled 1
    job fable succeeded 10
    job fable_peer succeeded 10
    job predict succeeded 59
    job review2 succeeded 2
    runs_unreconciled_unknown 0
    runs_reserved_or_sending 0
    last_audit assessment.created 2026-11-05T07:43:47Z 39727
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

## Expected changes, per phase

- **preflight:** none. One random ACME probe file is written and removed.
- **image:** a new local image cpt-studio:e6d451f03d86.
  - It is built from git archive of e6d451f03d86f11e8454c46e14cda6337bdbef23 cpt-studio/, labelled with the revision, user 10150,
    CPT_STUDIO_RELEASE_SHA=e6d451f03d86f11e8454c46e14cda6337bdbef23.
  - The apt, user, WORKDIR, requirements and pip steps are CACHED, as measured above.
  - The operator checks offline, after the phase: pypdf 6.21.2 in the new image, and its
    `dpkg-query -W -f '${Package} ${Version}\n'` identical to cpt-studio:b0dc3446c64c's.
  - A build log showing apt or pip ran is a stop before app.
- **Before app, outside the installer and read-only on the database:** one `pg_dump -Fc` of the cptstudio database,
  through the database container's own pg_dump, to
  /home/claude/cpt-studio-install-20261023/pre-app-e6d451f03d86-<UTC>.dump (0600). Its `pg_restore --list` shows 39 TABLE
  DATA entries. It holds synthetic documents, responses and password hashes, and is kept until a separate, recorded
  decision removes it.
- **app (the blue/green switch; ops/INSTALL.md "Phases"):**
  - the loader parses the Corti credentials and each participant's credentials file in the worker's mount layout, with
    no network; migrate (a one-shot) applies nothing; the queue read finds 0 stages this revision cannot run;
  - S1: cpt-studio-web-next starts on the idle port and answers /health/ with release e6d451f03d86f11e8454c46e14cda6337bdbef23, its sign-in page, and
    every static file that page names;
  - S2: the b0dc3446c64c worker is parked; its current stage finishes; none is expected running;
  - S3: the quillmd-cpt vhost's upstream is switched to the idle port, and the vhost differs in its proxy_pass line
    alone. `sudo -n nginx -t` passes with no new warning, `sudo -n systemctl reload nginx` reloads gracefully, and
    https://cpt.quillmd.com/health/ serves e6d451f03d86f11e8454c46e14cda6337bdbef23;
  - S4: the new worker starts;
  - S5: the old web is drained (at least 130 s, at most 600 s), stopped and parked as cpt-studio-web-previous; the
    incoming web is renamed cpt-studio-web;
  - availability (the public /health/ every 0.5 s, from before S1 to the end): every sample 200; releases_seen
    b0dc3446c64c840cd01e9f37b8de3bad7aa954d4 then e6d451f03d86f11e8454c46e14cda6337bdbef23; non_200_count 0;
  - states_recomputed {"encounters": <the baseline's encounters>, "changed": {}} (predicted above). The parked pair is
    removed;
  - nothing is sent: no access check is run, and the installer's one-shots run with every provider disabled;
  - counts after app: every count equals the pre-app reading, apart from a member's own use during the act.
    - That use is identified read-only by encounter and acting account, recorded, and set aside before the comparison.
    - Any other movement is the act's and a stop.
    - studio_workerbeat stays 1 row named 'worker'. Its revision becomes e6d451f03d86f11e8454c46e14cda6337bdbef23, and its beat_at advances once the new
      worker beats (S4).
- **verify:** no difference from the preflight baseline except the quillmd-cpt vhost's proxy_pass line.
  https://cpt.quillmd.com/health/ serves e6d451f03d86f11e8454c46e14cda6337bdbef23 under normal certificate verification, with the security headers once
  each.
- **reassess (88d9db32-65b5-4a55-98ee-b82ce0da8941):**
  - the dry run names the plan above (the final assessment, Astra's and Fable's first readings and peer reviews by id)
    and queues nothing;
  - the real run queues exactly one assess job, which the running worker makes from the retained answers:
    - nothing is sent: provider runs +0, sent runs +0, provider exchanges +0, tool calls +0, credits_sum unchanged;
    - tables, as predicted above: studio_assessment +1, studio_proposal +26, studio_clarification +1, studio_job +1,
      studio_routingrun +1, studio_auditevent +2;
  - the prior assessment, its proposals and clarifications, and the encounter's decisions stay as they are. The new
    assessment is added beside them and becomes current. The act creates, removes or invalidates no decision;
  - 88d9db32 then reads needs_clarification, with the five codes above ready, 45381 held with one open tattoo-conflict
    question, and the decompression listed, as predicted.
- Image cpt-studio:b0dc3446c64c is kept: it is the rollback image. Nothing removes any image.

## What the install sends

Nothing. No access check is run, every one-shot runs with Corti and the participants disabled, and the reassessment
builds and sends no request (its participants' readings are the retained ones).

Immediately before app:
- jobs_active 0;
- no provider run reserved or sending;
- no unreconciled unknown outcome;
- no audit event newer than 10 minutes.

Checked after app and after reassess:
- provider runs, sent runs, provider exchanges, tool calls and credits_sum equal their pre-app reading;
- no provider run has a created_at at or after the app receipt's started_at.

## After the install: the fresh acceptance walk (ordinary use, not a phase)

The directive's item 10 runs as ordinary use of the installed service, after verify and reassess. The synthetic agent
accounts review-agent and ops-agent carry it out.
- **Its inputs:** three synthetic documents (h2a as PDF, h2b and h2c as Word) and their expectations, kept in
  /home/claude/cpt-studio-harness2-20261105/acceptance/sealed/.
  - They were written and sealed (mode 0400) at 2026-11-05T09:49:56Z and 09:50:29Z, before any code read them.
  - Their sha256 prefixes are 20b68bd98351a212, b901d3ea5c11ab18, c11af6bec5de63f6 and 5abde4e99e4d032d.
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
- reassess: the dry run's plan, then the job, the counts and the encounter's reading as declared.

## Rollback per phase, and its limits

- image: nothing to undo; the new image is unused until app.
- app: the installer's own undo restores the b0dc3446c64c web and worker (rollback-app), and the vhost's proxy_pass;
  the rolled-back revision recomputes states. If reassess ran, its added assessment stays, as every assessment does,
  and the rolled-back revision reads 88d9db32's current assessment as it reads any assessment it did not make.
- reassess: an added assessment is never removed; a wrong reassessment is answered by a new one, never by deleting
  rows.

## What is not claimed

Functional completion on the installed site is judged by verify, reassess and the acceptance walk. Clinical accuracy
and content-use permissions are separate verdicts, and this act establishes none of them.
- NCCI PTP stays unconnected: modifiers are considerations only.
- D3 to D5 and decision (m) stay open.
- The readers' recorded residuals stand (ACCURACY-RESIDUALS.md, "Harness repair, refutation round 1" to "round 7"). They
  include 88d9db32's 45381 tattoo conflict and round 4's earlier-time injection forms ("was already tattooed", "already
  injected"), which read as at the live revision.
- Directive item 3's "tattoo versus resection negation" and "future localization versus future performance" are not
  delivered: refutation round 6 dropped both readings.
- The cpt-studio workflow's dependency audit stays red on pypdf 6.21.2's seven advisories (interpretation 68). It is not
  a required check, and this revision does not move pypdf.

## Stop conditions

Any of these stops the act:
- an undeclared count movement;
- a provider run, exchange or tool call created by app, verify or reassess;
- a non-200 availability sample, or a releases_seen other than the two declared;
- states_recomputed naming any changed encounter;
- a build log showing apt or pip ran;
- a leftover *-previous or *-next container after app;
- a dry run that queues a job, or a reassess that queues more than one;
- 88d9db32 not reading as predicted.
