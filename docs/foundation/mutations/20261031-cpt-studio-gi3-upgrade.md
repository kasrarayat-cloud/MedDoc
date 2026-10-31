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
the rollback rules are those that installed 90377ec6f413. So is scripts/check-cotenants.sh, which preflight and verify run from
the act's checkout. It is blob 35a01b2e at ca2247e5 (the checkout that installed 90377ec6f413) and at 80df1831. The tree check
does not cover it, so before preflight the operator runs `git diff --quiet 80df1831d168c4ee83d83c37bac9860690986cf3 HEAD --
scripts/check-cotenants.sh` in the act's checkout; any difference is a stop.

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
- pypdf stays 6.21.2 and the reader is byte-identical, so text-layer PDF, DOCX, text and paste uploads read as installed reads
  them. A new upload records {"ingest": "cpt-studio-ingest@3", "pypdf": "6.21.2"}, as now (interpretation 61). Pages read by OCR
  also depend on the image's Debian packages, which apt does not pin. The image check below requires them to be identical to
  installed's.
- The API adds `date_asked` to a context fact and `service_date_asked` to a list row, and `service_date_conflict` is false for this
  release's question. A tab open across the install reads an old page beside the new API until it reloads: a list date may read
  "Not documented" there.

## Baseline (read-only, 2026-10-31T10:56:49Z; re-read immediately before the commit that lands this declaration; this act's preflight receipt is binding)

- Live database (SELECT only): bc7df129's tools/live_counts.sh at 2026-10-31T09:22:57Z, identical at the re-reads of 10:10:29Z and 10:56:49Z: encounters 36,
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
  - the last audit event is the agent's report.generated at 2026-10-29T07:28:00Z, from the round-2 walk; idle 185,329 s
    at the 10:56:49Z re-read.
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
  scripts/check-cotenants.sh: rc 0 at 2026-10-31T09:22Z, 10:10Z and 10:56Z (quillmd.com 200, www 200, app 302, admin 503, pro 410).
- Host, at 2026-10-31T10:56:49Z: 32,093 MiB RAM (31 GiB as `free -g` rounds it), 25,698 MiB available; 4,095 MiB swap, 0 MiB
  used; 14 CPUs; 104 GiB free on / (82% used). The preflight phase requires at least 10 GiB free.

## Expected changes, per phase

- preflight: none. One random ACME probe file is written to /var/www/certbot/.well-known/acme-challenge/ and removed.
- image: a new local image, cpt-studio:80df1831d168, built from git archive of 80df1831d168c4ee83d83c37bac9860690986cf3 cpt-studio/. It carries label revision 80df1831d168c4ee83d83c37bac9860690986cf3, user
  10150 and CPT_STUDIO_RELEASE_SHA=80df1831d168c4ee83d83c37bac9860690986cf3.
  - Expected: steps 2 to 6 (apt, the user, WORKDIR, `COPY requirements.txt` and `pip install`) are CACHED again, as in the builds
    of 2026-10-26 22:19Z, 10-28 and 10-29, whose logs in the receipts directory show them CACHED. Three things support it:
    - the Dockerfile, .dockerignore, requirements.txt and installer are byte-identical to 90377ec6f413's;
    - REVISION is declared after every RUN;
    - the build cache has held 516.9 MB in every preflight report since the 10-29 build, with no prune.
    So nothing is fetched, and only `COPY . .`, collectstatic and the image metadata differ from 0b95b5113214. If the build log
    shows that apt or pip ran, that is recorded, and the package comparison below decides.
  - By the operator, after the phase, with no network, each in a throwaway container (`docker run --rm --network none
    --read-only --pull=never`):
    - `pypdf.__version__` in the new image reads 6.21.2;
    - the package list is read with `dpkg-query -W -f '${Package} ${Version}\n'`. It is read first from the kept image
      0b95b5113214, where it must reproduce the recorded list: 166 lines, sha256
      6f1b61f6480b598761c5e9e9af22c901c8cfde16cadb83fe5c23b1b749b07ed8. It is then read from the new image, and the two must be
      identical, because OCR renders scanned pages with poppler and reads them with tesseract through these packages. They
      include tesseract-ocr 5.3.0-2, tesseract-ocr-eng 1:4.1.0-2, libtesseract5 5.3.0-2, liblept5 1.82.0-3+b3, poppler-utils
      and libpoppler126 22.12.0-2+deb12u3, and the image libraries they use. Any difference is a stop before app.
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
  - any failure of the phase is a stop under this declaration, judged before any rerun. What each failure leaves is set out under
    "Rollback per phase" (the 90377ec6f413 app phase took 28 s).

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
- A member's save on it that leaves the question open (a save of something else, such as the setting) makes one dateless request
  for its text (request sha256 eb6c0047…), the limit "gi3 a save that leaves the question open". That request is sent unless the
  workspace already holds a succeeded answer to the identical request, in which case the predict stage reuses it and sends
  nothing. Once the walk's fresh h2-08 dateless primary has succeeded, that answer will exist, since it has the same text and the
  same request. A save entering a date other than 2026-10-05 is held as a member conflict and sends nothing. It has no decisions to
  invalidate. The walk does not open, save or re-read it, and this act makes no member action on it.

## After the install: the acceptance walk (ordinary use, not a phase)

All through https://cpt.quillmd.com. One document per invocation, strictly in sequence; the next starts only when jobs_active is 0
again.

1. The demo reviewer's login, once, with ops/verify_login.py --base-url https://cpt.quillmd.com --username demo-reviewer
   --password-file /home/claude/.cpt-studio/demo-reviewer-password --workspace Gastroenterology --out <a fresh evidence directory>.
   Its five requests make no decision, read no encounter and print no password. The password file is passed by path and never read
   by a session tool. Expected: signed in, a human reviewer in an active membership, signed out, and the session refused after.
   Counts are unchanged, audit_events included: the sign-in writes no audit row, so any audit_events movement in this step is a
   finding. It writes one studio_loginattempt row and a django_session row that its own sign-out deletes, and sets demo-reviewer's
   last_login. None of these is a declared count. Users and memberships +0.
2. Seven synthetic documents as the agent account review-agent, one per invocation, from cpt-studio/ of the install checkout:
   `node ops/verify_browser.cjs --base-url https://cpt.quillmd.com --credentials <the review-agent credentials file, passed by path
   and never read by a session tool> --docs D --manifest M --out E --only <id> --deadline-seconds 900 --allow-live-provider
   --no-auto-approve`. Then, offline: `python3 -B ops/verify_downloads.py --evidence E/evidence.json --only <id> --json-out
   E/downloads.json`.
   - E is a fresh evidence directory for each document.
   - M is the manifest named below for each set.
   - D is /home/claude/cpt-studio-gi3-walk/h2-docs-final for h2-08, and /home/claude/cpt-studio-gi3-walk/h4-docs for h4.
   - Each D's generated.json binds its manifest by sha256, and verify_browser refuses a mismatch.
   - Each invocation signs review-agent in through the same form and never signs out. It leaves one studio_loginattempt row and
     one django_session row, and moves review-agent's last_login. None of these is a declared count.
   - h2-08, fresh, as a PDF (manifest /home/claude/cpt-studio-gi3-walk/h2/manifest.json, sha256
     f32010dbf71722ea3cb540c30b4f93a9268f45d7ed9ca2fb2b184e212a5b99a5; h2-08-hepatology-note.pdf sha256 17fc34fa…). Expected:
     - The date is asked, and the primary request carries no date line. That request (sha256 eb6c0047…) is new and is sent.
     - review_plan.context_edit answers 2026-10-05, the date the question names, which makes exactly one dated primary run. Its
       request is the text (sha256 958b4a31…, 1,913 characters) plus "Date of service: 2026-10-05", request sha256 5349c1cb…. It is
       byte-identical to the request 90377ec6f413 sent for e084b793 on 2026-10-29. So the predict stage reuses that retained answer
       and sends nothing (duplicate protection), and h2-08's answered assessment reads e084b793's recorded response. The tool's
       one_request check passes on a reuse.
     - This walk therefore exercises the release's question and its answer on h2-08, but not a live dated send. The h4 answers
       exercise live dated sends.
     - The manifest's own purpose sentence ("sends exactly one dated request") is superseded here. It is not edited, because
       generated.json pins the manifest.
     - The identical second save sends nothing.
     - 99215 is expected to stay as installed reads it: selected, needs_clarification and undecided, with its performed_status and
       em_basis questions open. The walk does not test this: with review_plan.approve_codes [] and no reject plan it approves and
       rejects nothing, and records reviewed_withheld whatever the E/M's status. The operator judges it from the walk's final API
       snapshot of h2-08.
   - h4-01 to h4-06, the sealed acceptance set (manifest /home/claude/cpt-studio-gi3-walk/h4/manifest.json, sha256
     3cce1a9dd68ba555b0b2d3fbb8a285ad35980c7f56ade700fb356e528b873973).
     - Its author, by the manifest's own account, read none of the service's code, tests, architecture notes or residual lists,
       nor the repair work. The one exception: for the manifest's format, the author read a pre-repair copy of
       ops/verify_browser.cjs, as h4-03's walk_note records.
     - This session read h4 only after the code froze.
     - It was rebuilt after the reboot from its author's tool calls: its manifest matches the pin f8985709d985eb1d, and its six
       renders are byte-identical to the hashes its author's run printed.
     - The walk's amendment adds review_plan.approve_codes from the author's source-reviewed codes. It also adds
       review_plan.context_edit with the date each source states where the frozen reader leaves the date asked (all but h4-05),
       chosen before any provider answer. h4-02 also carries the author's designated rejection, the gi.flex_sig family with 45331
       preferred.
     - Offline, the frozen tree reads the same 1 of 6 dates and the same routing as installed, so most of the author's
       expectations are expected to fail. A failed expectation is a result, recorded and reported, not a stop.
   The second sealed set, h3, could not be rebuilt after the reboot and is not used.

   Decisions are recorded and labelled as agent review, with the manifest's review notes:
   - The walk approves only a ready selected code that review_plan.approve_codes names, and never a code of a must_not_code
     family.
   - On h4-02 it also makes one designated rejection in gi.flex_sig. That is 45331 if ready: one of the author's two
     source-reviewed codes, so it is rejected rather than approved, with the note "designated rejection exercising the reject path;
     not a clinical judgement". Otherwise it is the family's last ready code, or none if the family has no ready code.
   - On every document it confirms each undecided reinstatable exclusion in a family that document's must_not_code lists.
   - Every other ready code, named or not, and every other exclusion, stays undecided and withholds that document's reviewed
     report. So does a named code that is proposed but not ready. On h2-08 nothing is approved or rejected.
- Bounds for each document (database counts, SELECT only, before and after each):
  - encounters +1 and revisions +1; source_files +1, or 0 for a paste;
  - h4-05, whose date the reader reads: provider_runs +1, provider_runs_sent +1 at most, jobs +4 (extract, analyze, predict,
    assess);
  - h2-08: provider_runs +2, provider_runs_sent +1 at most (the dated request is a reuse), jobs +7 at most;
  - h4-01 to h4-04 and h4-06: provider_runs +2 and provider_runs_sent +2 at most (the dateless primary, then the answered date's
    one primary; the identical save adds none), jobs +7 at most. The 7 are: the upload's extract, analyze, predict and assess; the
    answer's predict and assess; and the identical save's one assess on the run already in use, which sends nothing. That last one
    was measured live on round 2's h2-10, encounter f514e436. Fewer jobs only when a stage fails or a save is not accepted;
  - second-review runs +0; jobs_active back to 0; users, reference_sources, reference_facts and studio_migrations +0;
  - decisions and reports +(what the walk's evidence records as HTTP 201).
- For the whole walk: provider_runs +13 and provider_runs_sent +12 at most, about 0.5 credits at 0.0435 per sent request so far
  (1.478504 over 34). credits_sum rises by the provider's own reported usage: a record, not a gate.

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
- The two ReferenceSource rows and 34,665 reference facts. The three accounts' usernames, kinds and active flags, and their
  memberships' roles and active flags (last_login moves with the walk's sign-ins).
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
- app fails before the swap (the credentials parse, migrate or the queue read refuses): nothing is replaced, and the 90377ec6f413
  pair keeps running.
- app fails after the 90377ec6f413 pair is parked and before the new pair is ready. First:
  - the new pair is stopped;
  - the stages it queued, ran or left resumable since the swap, and every open stage of a kind the parked worker cannot run, are
    closed as failed naming the revision;
  - the provider runs they left unsettled are settled as the stale-stage sweep settles them.

  What follows depends on the close's hazard read (UNDO_HAZARDS):
  - it names no hazard: the stored states are put back, the new pair is removed, and the 90377ec6f413 pair is renamed back and
    started. The receipt carries only the original failure (after an interrupt reaching the installer, ok false with no error) and
    names no encounter. The close and the put-back are in app-<stamp>-NN-undo.log in the receipts directory (closed stages and
    encounters as counts), which the receipt does not point to;
  - it names records the 90377ec6f413 worker would act on (unknown, outcome, conflict, second_review): as above, except that the
    worker is renamed back and left stopped, so nothing can be sent, and details.hazards names the encounters. That worker is not
    started by hand: this revision is installed again once its failure is fixed;
  - it names a second review the 90377ec6f413 web would show wrongly (second_review_refused, second_review_unread): nothing is
    restored. The new pair is left stopped, the old pair parked, and nothing serves. details.hazards names the encounters, and
    rollback-app refuses while they stand. The ways on, each a separate recorded decision, are: start the new pair, clear them on
    its web, run rollback-app and then rename the parked pair back; or keep this revision.

  If the stages cannot be closed or the put-back fails, the new pair is left stopped and the old pair parked: run rollback-app under
  this declaration, then rename the parked pair back and start it.
- app stops after the new pair is ready, because the recompute fails, the parked pair cannot be removed, or an interrupt reaches the
  installer itself: nothing is stopped or restored.
  - The 80df1831d168 pair keeps serving, with the provider live.
  - The 90377ec6f413 pair stays parked (*-previous), or only its web, if its worker was already removed.
  - The receipt is ok false, and details.states_recomputed says whether the states were recomputed.
  - Its message names INSTALL.md's two remedies: remove the parked pair by hand and rerun app, or run rollback-app and then rename
    the parked pair back.
- An installer killed outright (the door's 3600 s ceiling, or any SIGTERM or SIGKILL) writes no receipt and runs no restore. The
  containers stay as the kill left them; read them with `docker ps -a`.
- Each of these is a stop. The pair that is running serves while it is judged, and no remedy (rerun app, rollback-app, rename back)
  is taken without a decision recorded under this declaration.
- After a successful app there is no parked pair. Going back to 90377ec6f413 has three steps:
  1. reconcile every unknown provider outcome;
  2. run rollback-app under this declaration, which refuses, stopping nothing, while the installer's hazard read names any
     encounter;
  3. a separately declared reinstall of 90377ec6f413, from a checkout whose cpt-studio/ is 90377ec6f413's.

  Image 0b95b5113214 and its image receipt are kept for it. That hazard read (this revision's UNDO_HAZARDS_READ) was run read-only
  over the 2026-10-31T09:21:53Z dump in a scratch database on the test server, the same way as the state prediction. It names
  nothing: {"hazards": {}}. Its control, an unknown outcome planted on 5e02eb08, is named ("unknown"). The read covers every
  encounter, including those the walk adds. An encounter it names for a reason other than "unknown" is cleared on this revision's
  web by a Resume, a date answer or an addendum (ops/INSTALL.md, "Reinstalling an older revision"). An addendum can send a request,
  so it is a separate recorded decision, and until it is taken this revision stays installed.
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
- scripts/check-cotenants.sh in the act's checkout differing from 80df1831's;
- a new image whose pypdf is not 6.21.2, or whose package list differs from the installed image's, or a list read from
  0b95b5113214 that does not reproduce the recorded one;
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
  - on each document with a review_plan.context_edit (h2-08, h4-01 to h4-04 and h4-06): a run other than the dateless primary
    before the answer, more than one request after it, or any run on the identical save;
  - on h2-08: a dated request that is sent rather than reused, or a final snapshot in which 99215 is not selected,
    needs_clarification and undecided with both of its questions open;
  - on h4-05, which has no context_edit and whose date the reader reads: any run other than its one primary, or a primary whose
    request does not carry "Date of service: 2026-10-15" (a dateless one included);
  - a decision of a kind, or on a code, that the walk's decisions above do not name;
  - a second-review run;
  - an unknown provider outcome: stop. Reconciling it is a separate, recorded decision;
  - a provider authentication, quota or payment failure. This stop acts from the next document, not inside the failing one. The
    walk tool has no stop of its own on a provider failure, and it counts a failed or unknown dateless primary as answered. So when
    the coding endpoint refuses that primary (recorded failed and sent), the walk still saves the declared date, and the server
    sends that date's one request within the bounds. A refusal at the token endpoint is recorded not sent, and the walk then makes
    no edit. After an unknown outcome, the walk still saves, decides and exports, and the server sends nothing. Those in-document
    actions are recorded as part of the stopped document;
  - verify_downloads exiting 1 (a report check failed) or 2 (a check could not be performed) for a document. Exit 2 is never a
    pass;
  - jobs_active not returning to 0 within the stage deadlines;
  - a /health/ release other than 80df1831d168c4ee83d83c37bac9860690986cf3, or any 5xx from the site;
  - a downloaded report that misstates the persisted decisions;
  - any action on e084b793.
