# Prepared exact-candidate served verification — 2026-10-04

This is a bounded execution checklist for the integration owner after exact CI and source refutation pass. It was not executed by this preparation. Use the new factory archive, its generated normal launcher and its fresh synthetic database. Preserve the old 789c demo source, state, database, helpers and rollback identity. Installation on 9130/9131 and public cutover remain separate; B-W1 still blocks installed automatic/v4 promotion.

## Commands and identity gate

Replace the full commit and fresh run IDs with the actual frozen candidate values. Do not reuse old evidence names or consumed credential tickets. The factory's normal source/CI preparation commands are in `REPORT.md`; its successful output binds the complete source inventory, schema, dependency/Word receipts and helper digests.

```bash
fixture_commit=<FULL_FROZEN_CANDIDATE_SHA>
fixture_demo=/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/demo-${fixture_commit:0:8}
fixture_python=/opt/meddoc-pro/.worktrees/v1-workflow-candidate/rebuild/.venv/bin/python

# New archive/state/database only, through the fresh protected launcher.
timeout 30s python3 -B "$fixture_demo/qa_launch.py" --profile v1 -- "$fixture_python" -B "$fixture_demo/create_qa_database.py"
timeout 120s python3 -B "$fixture_demo/qa_launch.py" --profile v1 -- "$fixture_python" -B manage.py migrate --noinput
timeout 120s python3 -B "$fixture_demo/qa_launch.py" --profile v1 -- "$fixture_python" -B manage.py collectstatic --noinput
timeout 60s python3 -B "$fixture_demo/qa_launch.py" --profile v1 -- "$fixture_python" -B manage.py seed_private
```

Record each actual exit. Verify database name, migrations, immutable archive and extracted runtime hashes before starting. The seed's private-access file stays mode 0600; never print its passwords or MFA key. Record current old demo identity through its existing `stop.sh --check` before any approved handover. Prepare the new archive/database while the old demo remains available. On verified port handover, run the new `start.sh` with a 90-second deadline; capture actual source-bound doctor/admin masters, child workers and real generation-worker PID, cwd, owner and start tick. Require both `/health/` payloads to name the full candidate, correct surface and synthetic-only mode; inspect only an allowlisted redacted process profile, never dump process environments.

```bash
# After normal handover and actual process identity checks:
timeout 90s bash "$fixture_demo/start.sh"
curl --fail --silent --show-error --max-time 5 http://127.0.0.1:9160/health/
curl --fail --silent --show-error --max-time 5 http://127.0.0.1:9161/health/

# Existing served browser gate: explicit doctor AND admin URL.
EXTRA_ENV='QUILLMD_BROWSER_ADMIN_URL=http://127.0.0.1:9161' \
  timeout 300s bash "$fixture_demo/run_harness.sh" <FRESH_BROWSER_RUN_ID> /usr/bin/node browser-tests.mjs

# Existing retained signing-refusal plus independent usable export control.
timeout 30s python3 -B "$fixture_demo/qa_launch.py" --profile v1 -- "$fixture_python" -B prepare-word-authority-browser.py
timeout 300s bash "$fixture_demo/run_harness.sh" <FRESH_WORD_AUTHORITY_RUN_ID> /usr/bin/node word-authority-browser.mjs
```

The retained starter uses the existing fixed `v1-workflow-candidate` fixture interpreter. Its 89 required package METADATA versions were read on October4 and all match the target lock; no package/application/model import or mutation was performed by that observation. The task-owned dependency virtualenv is separate and is not moved here. A startup failure is not a healthy demonstration: retain its actual exit and logs, inspect only recorded owned process identities, and use the new archive's bounded `stop.sh` for a partial start before a distinct retry. Never kill a reused PID by its number alone.

For an automatic/v3 seed, `seed_private` intentionally leaves the three-field original mapping **unconfirmed**. Before the ordinary doctor/admin browser gate above, the clinician signs in to 9160, opens “Clinical assessment” in the library, inspects the original and all three destinations, and confirms mapping version 1 through actual mapping review. The browser gate then selects that unchanged approved mapping. Do not insert MappingConfirmation directly or rewrite the blank source to make the browser proceed. If coverage requires correction, retain the original automatic result and new mapping identity separately; the old gate's mapping 1 expectation must not be silently relabeled.

These existing scripts use the archive's protected synthetic seed credentials, actual browser routes and localhost-only harness. Capture their real process exits, JSON results, downloads and network records; retire any watcher when its actual child is finished. The input-workflow browser's static fixture is supplemental JavaScript evidence only. `identity-browser.mjs` assumes installed `/var/lib/quillmd` state, and `private-beta-browser.mjs` assumes a Git worktree plus environment-file bootstrap; do not run those unchanged on an archive or reinterpret their fixture assumptions as application failures. The admin console script has a separate module-resolution/seed contract; the existing doctor/admin browser gate already tests actual MFA and financial-only routes without importing those assumptions.

## Persisted acceptance record

| Actual action | Required evidence and positive/negative control |
| --- | --- |
| Profile and worker | Through the archive's launcher, read the ordinary configuration and a newly persisted job snapshot: fixture mode, configured `claude-sonnet-5-5`, explicit ordinary-v4 relations, 20k output profile and reviewed source/original/mapping identities. Real process must be that same archive/database. No provider credential, request or charge is inherited; configured fixture semantics never become a live 5.5 response claim. |
| Invitation, login and recovery | Use the source-bound outside-archive [identity sequence](IDENTITY-SERVED.md) on one new synthetic account and department. It reuses the existing record-level mail selection and application binding, accepts the actual invitation, reads persisted user/membership/welcome ledger, refuses token replay, changes only that account's password and verifies old-session invalidation plus new sign-in. It also proves an authorized patient write and a denied foreign-department write. No external mail or seeded-account password replacement. The source has six pure controls; the served flow remains unverified until its actual exit and readbacks are retained. |
| Department and host access | Reuse applicable historical 124 served evidence. Rerun affected mounted routes with an authorized doctor/owner write plus fresh stored-row read and a denied foreign-department overwrite; compare original/mapping/record and financial fingerprints before/after denial. Check admin MFA 200, password-only refusal, separate cookies, wrong public hosts 404, authorized correct-host positive, and no clinical text on financial-only admin routes. An unmounted404, screenshot or redirect is not authorization proof. |
| Built-in SOAP | `/templates/soap/` selects the permitted department and reuses the persisted immutable four-field original and latest mapping. Actual mapping review/confirmation then `/encounters/new/`; unchanged approved synthetic notes through `/generate/` and real fixture worker. Capture first answers and source spans before corrections. Reopen the saved draft, accept/edit or choose Leave blank—reviewed, save and finalize, then authenticate `/export/`. Query resulting Encounter,Job,Usage and template/version rows through the launcher; hash original and exported DOCX, verify exact four destinations and unchanged surrounding structure. No inferred diagnosis or transferred old HPI qualification. |
| Custom original | Upload a permitted synthetic original through `/templates/upload/`; retain its first hash, physical mapping and coverage issues. Review actual `v3_coverage` exclusions where needed and leave `automatic_complete=false`; confirm the same version. Generate, review, resume, finalize and export via actual routes. Preserve existing entries, choices, neighboring fields, header/footer and links. Refusal for incomplete/unreviewed mapping must leave no paid job. Corrections and manual recovery remain separate from automatic correctness and the fixed 60 corpus. |
| Audio/transcript | Own permitted synthetic audio through recording/upload, fixture transcription job, editable reviewed transcript and separate raw audio/raw transcript/edits. Route `/voice/approve/` followed by the selected SOAP/custom generation must bind that reviewed source. Retain supported/held/missing first answers, explicit review/finalization and export. Same request/retry must not duplicate jobs, reservations or charges. Fixture voice is neither live-provider usefulness nor human microphone acceptance. |
| Billing and admin history | Freshly generated simulated jobs must persist zero final charge, released reservation and explanatory ledger/usage state. Verify department/personal allocation, original balances, promo grant idempotence, search/filters/pagination and individual charge explanations. Failed/unknown jobs stay visible with honest reconciliation state. Do not invoke payment APIs or add a new sandbox payment campaign as part of demo serving. |
| Historical preservation and rollback | Old789c metadata/source/state/database and existing final downloads remain separate and unchanged; a fresh database does not prove it imported those histories. Reuse the populated 0018→leaf preservation proof, then verify this archive's own finalized download remains hash-identical after subsequent draft edits. Keep the new candidate's failure logs/state on any refusal. Stop only its verified processes with its helper; restart only the preserved compatible old demo. Never down-migrate, drop a database or restore an older incompatible clinical snapshot. |
| Operational honesty | Admin status must retain expired B2 evidence, account/covered-provider gaps, native Word/microphone unverified status and current dated ICD coverage honestly. CPT stays disabled. No new offsite drill, alert message or external monitor provisioning for this served check. |

The existing identity-bound `ops/verify_qa_authorization.py` can be reused only through its confirmed archive launcher with exact candidate, three real PIDs, new run ID and `--execute`, when the integration owner verifies its still-applicable contract. Its 180-second/150-request limits, own synthetic fixtures and retained financial fingerprints are explicit; direct synthetic final-file fixtures qualify authorization only. Its output and current active-route controls have separate denominators from the historical 124. It is not a clinical workflow or Word acceptance shortcut.

Persist evidence under the new demo's own protected directory with request IDs, job IDs, source/version hashes, first answer results, manual corrections, exports, actual exits and original failures. Claim the served revision only after those checks complete. A fixture demonstration, qualified synthetic pilot and real-patient V1 have distinct requirements; no readiness follows solely from these proposed commands.

## Actual SOAP/custom positive examples and readback

The ordinary browser creates the custom Clinical assessment example through supported patient/document/generation/review/finalization/export routes. Record its actual encounter and successful generation job IDs from that workflow, its immutable original, raw first result and downloaded DOCX. It uses these unchanged synthetic notes:

```text
History: Synthetic patient reports left wrist discomfort after a fall.
Findings: No deformity documented.
Plan: Follow-up assessment documented.
```

For SOAP, sign in as the same synthetic doctor and use **Use SOAP note**. Choose the permitted X-ray department, inspect the deterministic original and all Subjective/Objective/Assessment/Plan destinations, and approve the actual immutable mapping through its review page. Create a new document for the synthetic patient with service date today and these source notes:

```text
Subjective: cough for two days.
Objective: lungs clear.
Assessment: clinician assessed a viral upper respiratory infection.
Plan: rest, hydration and review if symptoms worsen.
```

Generate through the displayed fixture route and let the actual separately identified worker finish. Preserve the first result before editing. Inspect supported, held and missing answers with source quotations. Explicitly review or correct each answer; where appropriate use **Leave blank — reviewed**, preserving that decision separately from automatic correctness. Finalize and download through the actual doctor route. Record the encounter and generation job IDs. A meaningful positive must have useful supported first-pass answers; a zero-useful result remains failed usefulness even if manually filled and exported. Do not invent an assessment or change the source merely to satisfy a fixture.

The new default-prepared `ops.verify_fixture_persisted` reads these actual finalized records. It does not create, generate, review, finalize or charge them. It requires the new archive's exact full source inventory, confirmed doctor/admin/worker PID/cwd/start ticks, fixture profile and database, and explicit example IDs. Its database connection is read-only. Normal sign-in creates session/audit events; existing authorization checks own the password-only MFA negative, and this reader waits at most 32 seconds for an unconsumed seed-admin TOTP after the browser run. It checks actual doctor HTTP downloads against stored final bytes, original/mapping/physical bindings, raw source spans, explicit clinician review/blank decisions, ordinary-v4/20k fixture snapshots, real persisted zero simulated usage/receipt/reservation state, positive MFA financial access and denied foreign-department/admin clinical access. It retains first/final artifacts before assertions and compares financial/clinical state afterward. Holds, missing answers, corrections and reviewed blanks are counted separately. Its package/fidelity claim is limited to the two declared growing two-column examples, with no native Word or microphone claim.

```bash
fixture_doctor_pid=$(cat "$fixture_demo/state/doctor.pid")
fixture_admin_pid=$(cat "$fixture_demo/state/admin.pid")
fixture_worker_pid=$(cat "$fixture_demo/state/worker.pid")

# Fresh scoped authorization accounts/state only.
timeout 195s python3 -B "$fixture_demo/qa_launch.py" --profile v1 -- "$fixture_python" -B \
  -m ops.verify_qa_authorization --demo-dir "$fixture_demo" --expected-commit "$fixture_commit" \
  --doctor-pid "$fixture_doctor_pid" --admin-pid "$fixture_admin_pid" --worker-pid "$fixture_worker_pid" \
  --run-id <FRESH_AUTH_RUN_ID> --execute

# Read actual route-created examples, not directly fabricated records.
timeout 195s python3 -B "$fixture_demo/qa_launch.py" --profile v1 -- "$fixture_python" -B \
  -m ops.verify_fixture_persisted --demo-dir "$fixture_demo" --expected-commit "$fixture_commit" \
  --doctor-pid "$fixture_doctor_pid" --admin-pid "$fixture_admin_pid" --worker-pid "$fixture_worker_pid" \
  --soap-encounter <ACTUAL_SOAP_UUID> --soap-job <ACTUAL_SOAP_GENERATION_UUID> \
  --custom-encounter <ACTUAL_CUSTOM_UUID> --custom-job <ACTUAL_CUSTOM_GENERATION_UUID> \
  --run-id <FRESH_PERSISTED_RUN_ID> --execute

# Only the actual identified unhealthy/finished new demo, through its own helper:
timeout 35s bash "$fixture_demo/stop.sh" --check
timeout 35s bash "$fixture_demo/stop.sh"
```

The historical 124 denominator remains bound to 789c0372. New request counts and mounted-route coverage are recorded prospectively; a retired/unmounted route's404 is not an authorization result. The authorization helper's synthetic financial/finalized fixtures qualify access scope only, while this reader checks real application-generated fixture usage and actual clinical finalization. Preserve original historical failed runs. Both commands require the integration owner's coherent-source/CI/demo execution gate; neither has run as part of this preparation.
