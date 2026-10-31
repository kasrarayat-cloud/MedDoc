# Prospective declaration: CPT Studio GI round 3 narrow release at cpt.quillmd.com (90377ec6f413 to 80df1831d168c4ee83d83c37bac9860690986cf3)

Authority: the owner's directive of 2026-10-29 and his decision of 2026-10-30, "Narrow release (Recommended)", both recorded
verbatim in docs/foundation/rulings/2026-10-23-cpt-studio-gi.md: "Ship only the h2-08 fix, built on the installed revision.
Where installed silently drops a plan-section date of service, a charge or billing block's date now becomes a question
instead; nothing new is ever sent. Add the context re-read and disabled-provider safeguards, run one focused refutation of
that small diff, then PR, install and the live walk." Session interpretations 53 to 61 record how that went, and interpretation
53(e) why the standing rule required more than one refutation. Interpretation 61 records why the service keeps pypdf 6.21.2.
Seven advisories against that version failed the required dependency audit, which reads the rebuild's pins and was cleared by
PR #1449. A refutation of moving CPT Studio found 34 differences in how its reader reads uploads. Session 1bf3b49c is the single
integration and deployment owner:
it took over session 7c8d38da's work after the host reboot of 2026-10-30 22:00:21Z (ruling file, interpretation 56). The install
itself is governed by the 2026-10-23 directive cited in docs/foundation/mutations/20261023-cpt-studio-install.md: a protected
synthetic demonstration that uses the existing authorized Corti account, keeps provider credentials server-side and preserves
app.quillmd.com and unrelated services ("Keep app.quillmd.com, VoiceAssistMain and unrelated server resources unchanged",
2026-10-27). CPT Studio stays standalone: no QuillMD source, database, users, files, units or environment are shared, promoted
or edited. No purchase, agreement, new ACME account, new key, payment change or real-patient processing is part of this act.
The installer sends no provider request (see "What the install sends").

Revision to install: 80df1831d168c4ee83d83c37bac9860690986cf3, the merge commit of PR #1448 (branch
fix/cpt-studio-gi3-narrow-20261030); image tag cpt-studio:80df1831d168. Its cpt-studio/ differs from b5ddc4d32 only in
cpt-studio/ACCURACY-RESIDUALS.md. b5ddc4d32 is the frozen code on which that file's figures were measured. Its citation, on
80df1831: CI run 41190384588 (Fresh application tests, Marketing build, Private browser and accessibility) and secrets-scan
41190384614 (TruffleHog) pass; they are the required checks. The cpt-studio run 41190384598 passes its Django checks, its
migration check, 3,585 Django tests, the ops suites (211 with 1 skipped, and 37) and node's 61 of 61. It then fails at its last
step, the dependency audit of pypdf 6.21.2, on the seven advisories (interpretation 61). It replaces the live revision
90377ec6f413ac6cf1601836a286f45e2af53e37, installed 2026-10-29 07:19:28Z-07:20:28Z under
docs/foundation/mutations/20261029-cpt-studio-gi2-upgrade.md. It runs image cpt-studio:90377ec6f413 (sha256:0b95b5113214), web
5916ab772b79, worker 6158f6e95bd4 and database 1c5498b3aacc. That declaration and its receipts stay as they are.

Execute each install phase separately through scripts/run-ruled-mutation.sh with
`python3 -B cpt-studio/ops/install.py --phase <phase> --revision 80df1831d168c4ee83d83c37bac9860690986cf3 --receipts /home/claude/cpt-studio-install-20261023`,
in this order: preflight, image, app (with `--provider-mode live --authorization-ref
docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`), verify. Run them from a clean, detached checkout of the merge commit that
lands this declaration: a descendant of the revision that changes nothing under cpt-studio/, scripts/run-ruled-mutation.sh or
scripts/lib/. Read each receipt before the next phase. No receipt in that directory is changed: each file is created once.

Not run, because their objects exist and this revision does not change them: secrets, db, reference, provision, http-vhost, cert
and https-vhost. No step D: the demo reviewer account exists from the last install. Between 90377ec6f413 and
80df1831d168c4ee83d83c37bac9860690986cf3 these are byte-identical: cpt-studio/deploy/, cpt-studio/requirements.txt,
requirements.in and requirements-dev.txt, cpt-studio/ops/install.py, cpt-studio/ops/INSTALL.md, cpt-studio/cptstudio/,
scripts/run-ruled-mutation.sh and scripts/lib/. So the installer, the image recipe and its pinned dependencies, the vhost and
the rollback rules are those that installed 90377ec6f413.

## Delta shipped (90377ec6f413 to 80df1831d168c4ee83d83c37bac9860690986cf3)

PR #1448. Its body and cpt-studio/ACCURACY-RESIDUALS.md ("GI round 3 (2026-10-29/30): the narrow release") list every change,
measurement and limit. PR #1449 also reaches this tree, through main. It changes only rebuild/requirements.txt and two documents
under docs/rebuild/, none of which the service reads or builds from. For this act:

- No migration: `makemigrations --check` reports no changes, and cpt-studio/studio/migrations/ is byte-identical. studio_migrations
  stays 6.
- cpt-studio/studio/models.py, audit.py and types.py are byte-identical. review.py adds three lines: an import, and two in
`_fact_value`, which words a change reason. The stored list state's derivation (`_state_and_run`, `refresh_state`) is untouched,
so the stored states recompute as they are (predicted below).
- CONTEXT_VERSION becomes gi-context@3, with @1 and @2 earlier. That changes no stored row at the install. A stage that next runs
  for an encounter recorded before this install remakes its context before it sends or assesses.
- New readings apply to new uploads, new addenda, member saves and the stages they queue. No existing encounter is re-assessed or
  re-sent by the install.
- pypdf stays 6.21.2 and the reader is byte-identical, so every upload reads as installed reads it. A new upload records
  {"ingest": "cpt-studio-ingest@3", "pypdf": "6.21.2"}, as now (interpretation 61).
- The API adds `date_asked` to a context fact and `service_date_asked` to a list row, and `service_date_conflict` is false for this
  release's question. A tab open across the install reads an old page beside the new API until it reloads: a list date may read
  "Not documented" there.

## Baseline (read-only, 2026-10-31T10:10:29Z; re-read immediately before the commit that lands this declaration; this act's preflight receipt is binding)

- Live database (SELECT only): bc7df129's tools/live_counts.sh at 2026-10-31T09:22:57Z, identical at the re-read of 10:10:29Z: encounters 36,
  revisions 36, source_files 32, provider_runs 38, provider_runs_sent 34, assessments 39, proposals 479, decisions 24,
  clarifications 35, audit_events 308, reports 96, jobs 148, jobs_active 0, users 3, reference_sources 2, reference_facts
  34665, studio_migrations 6, credits_sum 1.478504.
- States (SELECT only): the same readings:
  - provider runs: 38.
    - 34 succeeded and sent (33 primary, 1 second review).
    - 3 primary succeeded without a send, each reusing the answer of an identical recorded request (reused_from
      set).
    - 1 primary not_sent (held).
    - None reserved or sending; no unknown outcome.
  - encounters: needs_clarification 19, reviewed 12, no_codes 3, ready_for_review 2. e084b793 is needs_clarification with
    0 decisions.
  - the last audit event is the agent's report.generated at 2026-10-29T07:28:00Z, from the round-2 walk; idle 182,549 s
    at the re-read.
  - accounts: users 3, all active, each with one active membership:
    - demo-reviewer: human, reviewer;
    - owner: human, owner;
    - review-agent: agent, reviewer.
  - the Gastroenterology category (slug gastroenterology) reads profiles_version gi-profiles@3; workspace
    ac7def49-7a0e-4db2-bf1b-8efe9fbfa0a8.
- Containers and images (docker inspect, read-only):
  - cpt-studio-web 5916ab772b79 and cpt-studio-worker 6158f6e95bd4 on image 0b95b5113214 (cpt-studio:90377ec6f413);
  - cpt-studio-db 1c5498b3aacc (postgres:17.11-alpine pinned, 127.0.0.1:55451);
  - images kept: cpt-studio:90377ec6f413 (0b95b5113214), cpt-studio:2b82889fea58 (544d8dd263ef), cpt-studio:2734a6f31ce0
    (36c5bf19ff2a), cpt-studio:29e4d1f52939, cpt-studio-fixcheck:8a06fd08c9a2, cpt-studio:dev-build and cpt-studio:emulation-stub;
  - the disposable test database cpt-studio-test-pg (127.0.0.1:55452), not part of the service and touched by no phase.
- The host rebooted at 2026-10-30 22:00:21Z, unplanned. Every service container came back with its own id. /tmp was wiped.
- nginx, routing, DNS, ACME, co-tenants and host resources: read by the preflight phase, whose receipt is binding. The quillmd-cpt
  vhost must still be 259b895dd1307e81b8fbcb5439874477daf71eba63c9b996b3bdfc572bf71a0c and quillmd
  e9aa049d9190713b60e8243b56e082c3fe59e068c205e0d595407f7d08a97638.
  scripts/check-cotenants.sh: rc 0 at 2026-10-31T09:22Z and 10:10Z (quillmd.com 200, www 200, app 302, admin 503, pro 410).
- Host: at 2026-10-31T10:10Z: 31 GiB RAM (32,093 MiB), 4 GiB swap (4,095 MiB, none used), 14 CPUs; 104 GiB free on / (82%
  used). The preflight phase requires at least 10 GiB free.

## Expected changes, per phase

- preflight: none. One random ACME probe file is written to /var/www/certbot/.well-known/acme-challenge/ and removed.
- image: a new local image, cpt-studio:80df1831d168, built from git archive of 80df1831d168c4ee83d83c37bac9860690986cf3 cpt-studio/. It carries label revision 80df1831d168c4ee83d83c37bac9860690986cf3, user
  10150 and CPT_STUDIO_RELEASE_SHA=80df1831d168c4ee83d83c37bac9860690986cf3.
  - Expected, from the reading at 2026-10-31T09:55Z: the build cache holds 517 MB, last used four to seven days ago, so the steps of
    the 2026-10-29 build of 90377ec6f413 are not cached. Then apt and pip run again:
    - every Python requirement is pinned with == and fetched from PyPI (no provider);
    - apt is unpinned, from the pinned base image's bookworm sources;
    - only the base image's own layers are expected to equal 0b95b5113214's.
    The receipt's build log shows which steps ran, and the image's own checks decide.
  - By the operator, after the phase, with no network and in a throwaway container:
    - `pypdf.__version__` inside the new image reads 6.21.2;
    - the image's package list (`dpkg-query -W`) is compared with the installed image's, which lists 166 packages, its sha256
      beginning 6f1b61f6480b5987. That list includes tesseract-ocr 5.3.0-2, tesseract-ocr-eng 1:4.1.0-2, libtesseract5 5.3.0-2,
      liblept5 1.82.0-3+b3, poppler-utils 22.12.0-2+deb12u3 and libpoppler126 22.12.0-2+deb12u3. Every difference is recorded
      with both versions. A Debian security revision of those six is recorded, not a stop; any other change to them is a stop
      before app, because OCR reads scanned uploads with them.
- Before app, outside the installer and read-only on the database: one `pg_dump -Fc` of the cptstudio database through the database
  container's own pg_dump, written to /home/claude/cpt-studio-install-20261023/pre-app-80df1831d168-YYYYMMDDTHHMMSSZ.dump (0600); its
  `pg_restore --list` must show the table data (29 TABLE DATA entries at the last reading). It is the only data-level way back. It
  holds synthetic documents, provider responses and the accounts' password hashes, and is kept until removed by a separate,
  recorded decision.
- app (provider mode live; the same authorization reference as now):
  - the application's own loader parses the Corti credentials in the worker's mount layout, with no network;
  - migrate applies nothing: its log reads "No migrations to apply.";
  - the queue read finds 0 stages this revision cannot run;
  - the 90377ec6f413 pair (worker 6158f6e95bd4, web 5916ab772b79) is stopped (worker first, up to 150 s) and parked as *-previous; it
    is removed only after the new pair is ready and the stored states are recomputed;
  - a new cpt-studio-web and cpt-studio-worker run on the new image with the same hardening, mounts, limits, labels and ports;
  - /health/ reports release 80df1831d168c4ee83d83c37bac9860690986cf3;
  - every encounter's stored list state is recomputed with this revision's derivation, the provider disabled. Expected receipt
    `states_recomputed`: {"encounters": 36, "changed": {}}. Predicted by running this revision's code (b5ddc4d32, byte-identical in
    cpt-studio/studio/ and ops/) under pypdf 6.21.2 over the live rows dumped read-only at 2026-10-31T09:21:53Z, in a scratch database on the
    test server: RECOMPUTE {"encounters": 36, "changed": {}}, with a positive control (a planted unknown outcome turned one encounter's
    state from reviewed to provider_unknown); installed's code gives the same. The prediction holds only while the re-read baseline
    shows no live activity;
  - if the phase stops after the swap with an error or an interrupt, the receipt is ok false, and each such case is a stop under this
    declaration, judged before any rerun (the 90377ec6f413 app phase took 28 s).

  Counts after app: every count equals the pre-app reading (no migration, nothing re-assessed).
- verify: none.
- Image 0b95b5113214 (cpt-studio:90377ec6f413) is kept: it is the rollback image. Nothing removes it or any other image.

## What the install sends to the provider: nothing

- install.py sends no request. Its one-shot containers run with CPT_STUDIO_PROVIDER_MODE=disabled, and the credentials parse has
  --network none.
- Only work in flight at the swap could send. So, immediately before app, all of these must hold: jobs_active (queued plus running)
  is 0; no provider run is reserved or sending; no unknown provider outcome is unreconciled; no audit event is newer than 10 minutes.
  CPT Studio has no maintenance mode, so a member could still act. The window is short and is measured, not assumed.
- Checked after app: provider_runs, provider_runs_sent, credits_sum, jobs and audit_events equal their pre-app reading, and no
  provider run has a created_at at or after the app receipt's started_at. Any difference is the finding, whatever explains it.

## The one existing encounter this release changes

Of the 36 live encounters, the release asks exactly one: e084b793 (h2-08's earlier upload; no decisions, one succeeded run; state
needs_clarification), read from the same read-only dump. Its stored context is gi-context@2 and says 2026-10-05 as documented.
- It shows its recorded reading until a member's action or a stage reads it again. A reload runs no stage.
- A member's save on it that does not settle the date would send one dateless request, the limit "gi3 a save that leaves the question
  open". It has no decisions to invalidate. The walk does not open, save or re-read it, and this act makes no member action on it.

## After the install: the acceptance walk (ordinary use, not a phase)

All through https://cpt.quillmd.com. One document per invocation, strictly in sequence; the next starts only when jobs_active is 0
again.

1. The demo reviewer's login, once, with ops/verify_login.py --base-url https://cpt.quillmd.com --username demo-reviewer
   --password-file /home/claude/.cpt-studio/demo-reviewer-password --workspace Gastroenterology --out <a fresh evidence directory>.
   Its five requests make no decision, read no encounter
   and print no password. The password file is passed by path and never read by a session tool. Expected: signed in, a human reviewer in
   an active membership, signed out, and the session refused after. Counts unchanged except any audit row the sign-in writes, read and
   recorded; users and memberships +0.
2. Seven synthetic documents as the agent account review-agent, ops/verify_browser.cjs --allow-live-provider --no-auto-approve
   --deadline-seconds 900 --only <id>, then ops/verify_downloads.py on the evidence:
   - h2-08, fresh, as a PDF (manifest /home/claude/cpt-studio-gi3-walk/h2/manifest.json, sha256 f32010dbf71722ea3cb540c30b4f93a9268f45d7ed9ca2fb2b184e212a5b99a5). Expected: the date is asked and
     the primary request carries no date line; review_plan.context_edit answers 2026-10-05, the date the question names, and sends
     exactly one dated request; the identical second save sends nothing. 99215 stays held on the installed reading (performed_status,
     em_basis), so no decision is made and the walk records reviewed_withheld.
   - h4-01 to h4-06, the sealed acceptance set (manifest /home/claude/cpt-studio-gi3-walk/h4/manifest.json, sha256 3cce1a9dd68ba555b0b2d3fbb8a285ad35980c7f56ade700fb356e528b873973). h4 was written
     by an author who read neither the code nor the repairs, and read by this session only after the code froze. It was rebuilt after
     the reboot from its author's tool calls: its manifest matches the pin f8985709d985eb1d, and its six renders are byte-identical to the
     hashes its author's run printed. The walk's amendment adds review_plan.approve_codes from the author's source-reviewed codes and
     review_plan.context_edit with the date each source states, where the frozen reader leaves it asked, chosen before any provider answer.
     Offline, the frozen tree reads the same 1 of 6 dates and the same routing as installed, so most of the author's expectations are
     expected to fail. A failed expectation is a result, recorded and reported, not a stop.
   The second sealed set, h3, could not be rebuilt after the reboot and is not used. Decisions are recorded and labelled as agent review; a
   code the plan names but the document does not make ready stays undecided, and that document's reviewed report is withheld.
- Bounds for each document (database counts, SELECT only, before and after each):
  - encounters +1 and revisions +1; source_files +1, or 0 for a paste;
  - h4-05, whose date the reader reads: provider_runs +1, provider_runs_sent +1 at most, jobs +4;
  - each of the six others: provider_runs +2 and provider_runs_sent +2 at most (the dateless primary, then the answered date's one primary;
    the identical save adds none), jobs +6 at most;
  - second-review runs +0; jobs_active back to 0; users, reference_sources, reference_facts and studio_migrations +0;
  - decisions and reports +(what the walk's evidence records as HTTP 201).
- For the whole walk: provider_runs +13 and provider_runs_sent +13 at most, about 0.6 credits at the 0.046 each so far. credits_sum rises by
  the provider's own reported usage: a record, not a gate.

## Must not change

- The quillmd vhost (e9aa049d…7638) and every other sites-available file, quillmd-cpt (259b895d…) included.
- nginx.conf and conf.d, and every sites-enabled entry.
- The local routing of every co-tenant name/port pair and of an unknown host (status and certificate per SNI).
- app.quillmd.com /health/ (status and release) and the check-cotenants.sh results.
- Every container outside CPT Studio running at preflight (same id, still running), and every existing volume.
- Every Let's Encrypt lineage and renewal config, and the ACME account set.
- The QuillMD rebuild, its database, users and files. /etc/cpt-studio/ and its files.
- cpt-studio-db: the same container, image, port and restart policy, running throughout. The volumes cpt-studio-pg and cpt-studio-files, and
  network cpt-studio-net.
- The two ReferenceSource rows and 34,665 reference facts; the three accounts and their memberships.
- Every existing encounter, revision, source file, provider run, assessment, proposal, decision, clarification, audit event, report and job:
  no migration, nothing re-assessed, and every stored state recomputed unchanged. e084b793 is touched by nothing in this act.
- No `nginx -t` warning may be added: the operator runs the installer's read-only nginx_test probe after verify and compares it with the two
  known warnings.

## Validation per phase

Each phase's own checks (ops/INSTALL.md) must pass and its receipt must say ok. Every receipt must also show: tree.mode
descendant-without-runtime-change; tree.head equal to the merge commit that lands this declaration; door.declaration equal to this file;
door.declaration_commit equal to the commit that last touched it.

- preflight: the nginx files above; exactly the two known warnings; check-cotenants exit 0; app.quillmd.com 200 JSON; ports 9150 and 55451
  published only by cpt-studio-web and cpt-studio-db; no task outside CPT Studio as uid 10150; A 147.189.172.8 only; one ACME account; at least
  10 GiB free.
- image: the revision label, user 10150, the baked release, English OCR, pdftoppm, `manage check`, and a WSGI load as its own user on a
  read-only root; then the pypdf and package comparison above.
- app: the migrate log reads "No migrations to apply."; unrunnable_stages.stuck is 0; replaced names the two 90377ec6f413 container ids;
  states_recomputed {"encounters": 36, "changed": {}}; ok true. Then, by the operator: /health/ through 127.0.0.1:9150 is {status ok, service
  cpt-studio, data_mode synthetic-only, database ok, release 80df1831d168c4ee83d83c37bac9860690986cf3}, and `docker ps` shows the new worker up.
- verify: no difference from the preflight baseline; the deployed containers' hardening; https://cpt.quillmd.com/health/ serves 80df1831d168c4ee83d83c37bac9860690986cf3 under
  normal certificate verification; one copy each of HSTS, nosniff, Referrer-Policy and X-Robots-Tag; a mismatched SNI is closed.

## Rollback per phase, and its limits

The installer is byte-identical to the one that installed 90377ec6f413, so its rollback rules are unchanged, and they still read every hazard as
057a7d39 (2734a6f3's tree) reads the rows.
- preflight, image and verify change nothing that serves. A failed image leaves at most an unused image.
- app fails inside the phase: the new pair is stopped, the stages it queued, ran or left resumable since the swap are closed as failed naming
  the revision, the provider runs it left unsettled are settled as the stale-stage sweep settles them, and only then is the 90377ec6f413 pair
  restored, with the receipt naming the encounters. If the stages cannot be closed or the put-back fails, the new pair is left stopped and the old
  pair parked: run rollback-app under this declaration, then rename the parked pair back and start it.
- After a successful app there is no parked pair. Going back to 90377ec6f413 is: reconcile every unknown provider outcome; run rollback-app under
  this declaration, which refuses while the installer's hazard read names any encounter; then a separately declared reinstall of 90377ec6f413
  from a checkout whose cpt-studio/ is 90377ec6f413's. Image 0b95b5113214 and its image receipt are kept for it.
- Limits, each found by the sixth to eighth refutations with real rows on the test server, never on this host:
  - rows this release writes read back on installed with no crash: the stored question reads "conflicting documentation", and the list "In conflict";
  - after a rollback, a member's save on an encounter the release asked sends the dated request installed sends at upload, because installed reads
    the document's own date again (pipe6-3). That date is installed's own reading: a rollback returns to it;
  - an assess in flight at the swap on an asked document, then a rollback, can read 'Provider not run' beside a recorded run, recovered by a save
    (pipe6-6);
  - records the new revision made stay, and installed reads them under its own rules; requests already sent and their usage stay; rollback-app and the
    failure path are proven by ops tests only, never exercised on this host; restoring the pre-app dump would delete data, so it is a separate declared
    act; rollback-vhost is not part of this act.

## What is not claimed

- No coding-accuracy figure and **no reliable-coding claim**. Other contradicted-date shapes stay known limits, extent, scope and inventory repairs did not
  ship, and on the independent set h4 this release changes nothing offline: both trees read 1 of 6 service dates and the same routing.
- The install prevents no member action: "nothing sent" is measured over the install window only.
- The 36 existing encounters are neither re-assessed nor re-sent. How the new screens present them is not verified by the walk, which creates new
  encounters only.
- CPT edition, descriptors and NCCI PTP stay not verified (interpretations 1-3). Data at rest is unencrypted and there is no scheduled database backup; the
  one-off pre-app dump is not a backup scheme.
- Co-tenants and app.quillmd.com are judged only by routing, health and check-cotenants equality.
- CPT Studio keeps pypdf 6.21.2 and its seven advisories. They are denial of service from a crafted PDF, which the ingest child's
  limits contain. Its own workflow's dependency audit stays red until a later round moves it with its reader repaired.
- The live QuillMD rebuild is outside this act. Since PR #1449, `main` pins pypdf 6.21.4 for it, but it keeps the version its image
  was built with until its own install, and this act did not read that version. Its open upload-check finding
  (docs/rebuild/security-readiness.md, 2026-10-31) is not this act's.

## Stop conditions

Stop and diagnose on any of the following. Do not rerun a phase, and do not upload the next walk document:
- any non-zero phase exit or a receipt that does not say ok;
- a tree mode other than descendant-without-runtime-change;
- a routing, health, check-cotenants or file-hash difference, or any new nginx warning;
- a quillmd vhost sha256 other than e9aa049d…7638;
- DNS other than A 147.189.172.8 alone, or anything other than exactly one ACME account;
- a new image whose pypdf is not 6.21.2, or whose OCR packages (the six named under image) changed other than by a Debian
  security revision;
- a migrate log that applies any migration;
- a stage this revision cannot run;
- before app: jobs_active not 0, a reserved or sending run, an unreconciled unknown outcome, or an audit event under 10 minutes old;
- across app: any count moving, or a provider run created during the install;
- the app receipt's states_recomputed naming any changed encounter (predicted none);
- a leftover *-previous container;
- ports 9150 or 55451 held by anything but cpt-studio-web and cpt-studio-db;
- any task outside CPT Studio running as uid 10150;
- during the walk:
  - a request carrying a date the document's reading and the declared answer do not give; on h2-08, any request carrying 2026-10-06;
  - a run other than the dateless primary before the answer, or more than one request after it, or any run on the identical save;
  - a second-review run;
  - an unknown provider outcome: stop. Reconciling it is a separate, recorded decision;
  - a provider authentication, quota or payment failure;
  - jobs_active not returning to 0 within the stage deadlines;
  - a /health/ release other than 80df1831d168c4ee83d83c37bac9860690986cf3, or any 5xx from the site;
  - a downloaded report that misstates the persisted decisions;
  - any action on e084b793.
