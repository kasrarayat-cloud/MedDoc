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

These existing scripts use the archive's protected synthetic seed credentials, actual browser routes and localhost-only harness. Capture their real process exits, JSON results, downloads and network records; retire any watcher when its actual child is finished. The input-workflow browser's static fixture is supplemental JavaScript evidence only. `identity-browser.mjs` assumes installed `/var/lib/quillmd` state, and `private-beta-browser.mjs` assumes a Git worktree plus environment-file bootstrap; do not run those unchanged on an archive or reinterpret their fixture assumptions as application failures. The admin console script has a separate module-resolution/seed contract; the existing doctor/admin browser gate already tests actual MFA and financial-only routes without importing those assumptions.

## Persisted acceptance record

| Actual action | Required evidence and positive/negative control |
| --- | --- |
| Profile and worker | Through the archive's launcher, read the ordinary configuration and a newly persisted job snapshot: fixture mode, configured `claude-sonnet-5-5`, explicit ordinary-v4 relations, 20k output profile and reviewed source/original/mapping identities. Real process must be that same archive/database. No provider credential, request or charge is inherited; configured fixture semantics never become a live 5.5 response claim. |
| Invitation, login and recovery | Create one own synthetic invitation through `/team/`; read only its new file-mail record through the existing protected procedure, accept it, and independently query persisted user/membership/welcome ledger. Token replay refuses; recovery changes that user's password and revokes its old session. No external mail, seeded-account password replacement or unrelated invitation mutation. If no compatible prepared helper exists, retain these steps as unverified instead of running an installed-state harness. |
| Department and host access | Reuse applicable historical 124 served evidence. Rerun affected mounted routes with an authorized doctor/owner write plus fresh stored-row read and a denied foreign-department overwrite; compare original/mapping/record and financial fingerprints before/after denial. Check admin MFA 200, password-only refusal, separate cookies, wrong public hosts 404, authorized correct-host positive, and no clinical text on financial-only admin routes. An unmounted404, screenshot or redirect is not authorization proof. |
| Built-in SOAP | `/templates/soap/` selects the permitted department and reuses the persisted immutable four-field original and latest mapping. Actual mapping review/confirmation then `/encounters/new/`; unchanged approved synthetic notes through `/generate/` and real fixture worker. Capture first answers and source spans before corrections. Reopen the saved draft, accept/edit or choose Leave blank—reviewed, save and finalize, then authenticate `/export/`. Query resulting Encounter,Job,Usage and template/version rows through the launcher; hash original and exported DOCX, verify exact four destinations and unchanged surrounding structure. No inferred diagnosis or transferred old HPI qualification. |
| Custom original | Upload a permitted synthetic original through `/templates/upload/`; retain its first hash, physical mapping and coverage issues. Review actual `v3_coverage` exclusions where needed and leave `automatic_complete=false`; confirm the same version. Generate, review, resume, finalize and export via actual routes. Preserve existing entries, choices, neighboring fields, header/footer and links. Refusal for incomplete/unreviewed mapping must leave no paid job. Corrections and manual recovery remain separate from automatic correctness and the fixed 60 corpus. |
| Audio/transcript | Own permitted synthetic audio through recording/upload, fixture transcription job, editable reviewed transcript and separate raw audio/raw transcript/edits. Route `/voice/approve/` followed by the selected SOAP/custom generation must bind that reviewed source. Retain supported/held/missing first answers, explicit review/finalization and export. Same request/retry must not duplicate jobs, reservations or charges. Fixture voice is neither live-provider usefulness nor human microphone acceptance. |
| Billing and admin history | Freshly generated simulated jobs must persist zero final charge, released reservation and explanatory ledger/usage state. Verify department/personal allocation, original balances, promo grant idempotence, search/filters/pagination and individual charge explanations. Failed/unknown jobs stay visible with honest reconciliation state. Do not invoke payment APIs or add a new sandbox payment campaign as part of demo serving. |
| Historical preservation and rollback | Old789c metadata/source/state/database and existing final downloads remain separate and unchanged; a fresh database does not prove it imported those histories. Reuse the populated 0018→leaf preservation proof, then verify this archive's own finalized download remains hash-identical after subsequent draft edits. Keep the new candidate's failure logs/state on any refusal. Stop only its verified processes with its helper; restart only the preserved compatible old demo. Never down-migrate, drop a database or restore an older incompatible clinical snapshot. |
| Operational honesty | Admin status must retain expired B2 evidence, account/covered-provider gaps, native Word/microphone unverified status and current dated ICD coverage honestly. CPT stays disabled. No new offsite drill, alert message or external monitor provisioning for this served check. |

The existing identity-bound `ops/verify_qa_authorization.py` can be reused only through its confirmed archive launcher with exact candidate, three real PIDs, new run ID and `--execute`, when the integration owner verifies its still-applicable contract. Its 180-second/150-request limits, own synthetic fixtures and retained financial fingerprints are explicit; direct synthetic final-file fixtures qualify authorization only. Its output and current active-route controls have separate denominators from the historical 124. It is not a clinical workflow or Word acceptance shortcut.

Persist evidence under the new demo's own protected directory with request IDs, job IDs, source/version hashes, first answer results, manual corrections, exports, actual exits and original failures. Claim the served revision only after those checks complete. A fixture demonstration, qualified synthetic pilot and real-patient V1 have distinct requirements; no readiness follows solely from these proposed commands.
