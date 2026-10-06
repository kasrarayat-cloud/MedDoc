# Prepared new-archive invitation and recovery sequence — 2026-10-04

The compatible sequence is ready in [private_demo_identity.source](../../../../rebuild/ops/fixtures/private_demo_identity.source). It adapts the existing identity-browser invitation/recovery sequence to the new 9160/9161 archive and its QA file-mail outbox. The old browser assumes installed `/var/lib/quillmd` state and ports 9130/9131; it is retained unchanged. This preparation has not read credentials, queried a database, started a service or executed the served flow.

The literal SHA256 is `5e0aaf004118fcdc9e9cc902ac6a541e86f03cbaf3653c37b1b72ece31eb490b`. Six pure controls passed on source commit `c3761d19878a563635134e26b4f50be5c231910f`: actual exit 0, 0.048 seconds, outer elapsed 0.265 seconds. [identity-source-verification.json](identity-source-verification.json) binds the unchanged source, test and raw log. Those controls verify the prepared default, incomplete-execution refusal, token-path redaction, sealed original fault material, exact own-record selection in a same-file collision and stale/multiple/wrong-token refusal. They do not qualify the application routes.

## Exact future execution

The integration owner executes this only after the coherent candidate's exact CI, source/refutation and private fixture gates pass, using the normal factory archive and launcher described in [SERVED-VERIFICATION.md](SERVED-VERIFICATION.md). No change is made inside the immutable `src/rebuild` archive. Use a fresh run ID. Preserve any previous result, account declaration and original failure before a distinct retry.

The prospective [identity-execution-manifest.json](identity-execution-manifest.json) deliberately leaves the future full candidate, archive SHA256 and three actual process identities unset. At execution, bind them to the factory's retained source manifest and verified doctor/admin masters and generation worker: PID, owner, cwd, start tick, command, full release and the new `quillmd_qa_int_sol_<prefix>` database. An expected PID number alone is insufficient.

After those identities and available headroom are checked, copy the exact literal once to the new demo's protected evidence directory, with no overwrite. Verify the extracted literal and copied runner against the declared SHA before making the execution manifest. The manifest contains no password, raw token, cookie or CSRF value. Its concrete values must be captured before `--execute`.

```bash
fixture_identity_sha=5e0aaf004118fcdc9e9cc902ac6a541e86f03cbaf3653c37b1b72ece31eb490b
fixture_identity_script="$fixture_demo/evidence/identity-$fixture_identity_sha.py"
fixture_identity_run=<FRESH_IDENTITY_RUN_ID>

# Exact no-overwrite copy after the integration owner's execution grant.
python3 -B - "$fixture_demo" "$fixture_commit" "$fixture_identity_sha" <<'PY'
import hashlib, os, re, stat, sys
from pathlib import Path
demo, commit, expected = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
assert demo == demo.resolve() and re.fullmatch('[a-f0-9]{40}', commit)
assert demo.parent == Path('/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002')
assert demo.name == 'demo-' + commit[:8] and commit[:8] != '789c0372'
source = demo / 'src/rebuild/ops/fixtures/private_demo_identity.source'
evidence = demo / 'evidence'
assert not any(path.is_symlink() for path in (source, *source.parents))
info = evidence.stat()
assert stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700
raw = source.read_bytes()
assert hashlib.sha256(raw).hexdigest() == expected
target = evidence / ('identity-' + expected + '.py')
fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
with os.fdopen(fd, 'wb') as stream:
    stream.write(raw)
assert hashlib.sha256(target.read_bytes()).hexdigest() == expected
PY
# Record the concrete source/CI/PID manifest before execution. If any copy or
# manifest creation failed, retain it and inspect before retrying; no overwrite.

# A prepared-only invocation reads no application credentials or state.
python3 -B "$fixture_identity_script"

# Actual execution uses the normal protected QA launcher and fresh harness log.
# The outer bound includes launcher and observer teardown; the runner itself
# enforces 180 seconds, 100 HTTP requests and 6-second request timeouts.
timeout 205s bash "$fixture_demo/run_harness.sh" "$fixture_identity_run" \
  /usr/bin/python3 -B "$fixture_demo/qa_launch.py" --profile v1 -- \
  "$fixture_python" -B "$fixture_identity_script" \
  --demo-dir "$fixture_demo" --expected-commit "$fixture_commit" \
  --expected-script-sha "$fixture_identity_sha" --run-id "$fixture_identity_run" \
  --doctor-pid "$fixture_doctor_pid" --admin-pid "$fixture_admin_pid" \
  --worker-pid "$fixture_worker_pid" --execute
```

The launcher supplies fixture-only, invite-only, file-email configuration from its normal protected QA credentials. The runner additionally requires the exact immutable archive, absence of an archive `.env`, correct source cwd, fixed QA database at 127.0.0.1:55731 and all three process identities before credentials are accessed. Its socket guard permits only 127.0.0.1:9160, 9161 and 55731. The existing harness observer labels database port 55731 as “other than QA ports” because its browser-only list contains 9160/9161; retain that raw observation and explicitly adjudicate the expected database connection. Require zero non-loopback and DNS peers. Do not change the observer to hide an unexpected connection. Capture the actual foreground command exit and stop an observer that outlives its completed child; an outer timeout is a failed/incomplete run.

## Required actual outcomes

The five prospective check groups have separate identities from the historical 124 authorization checks. None replaces an old failure or denominator.

| Group | Actual persisted and served proof |
| --- | --- |
| Invite-only source identity | `/register/` 404 and both health responses bind the exact full release, synthetic data mode and correct surface. The helper verifies live source/process identities before and after the sequence. |
| Invitation acceptance and replay | An authorized seed owner creates one new department and invitation through mounted forms. Read only the changed owner-only QA outbox files with the retained record-level matcher and application invitation hash binding. The admin-host invitation refuses. The doctor-host form persists exactly one active, verified clinician account and membership, one accepted invitation and the configured idempotent welcome grant; GET/POST replay creates no second account or membership. |
| Department scope | The newly accepted account signs in and persists one own synthetic patient through `/patients/`. Its patient API includes that row; the foreign doctor API excludes it. A real foreign doctor POST targeting the new department must leave no denied patient row. Positive sign-in and database readbacks accompany the denial. |
| Recovery and session revocation | Request recovery only for the new account through the mounted route and neutral response. Bind the selected file-mail record to that user's UID and application verifier. The real reset form changes its password; old password fails and new password signs in. A previously authenticated session row is proved to belong to that account, then disappears after reset and its old cookie no longer grants access. One persisted recovery audit records session invalidation; token replay changes no password, credit or recovery count. |
| Existing records and provider isolation | Exact fingerprints of all preexisting wallets, ledger entries, jobs, usage, reservations, provider receipts and payments remain unchanged. No new provider job, usage, reservation, receipt or payment may appear. New account/departments and welcome rows are explicit fixture results, separately retained. |

Before any HTTP mutation, the helper writes `identity-<run-id>/identity-declaration.json` with the unique own email/department, issuer, source/script identities and original financial fingerprints. It records no credential. All actual request status/body hashes are retained with raw invitation/recovery URL segments redacted. Failure evidence preserves a protected redacted original traceback and SHA256 of its full original material, separate from the generic terminal refusal. It does not report partial success as completion.

The helper retires only its own newly created account by setting inactive and advancing its session version, with an audit row. It preserves the account, department, patient, invitation, file mail, financial rows and evidence. A retirement failure is separate retained evidence and makes completion false. If a hard outer stop occurs before the account row is read back, use the prior declaration to reconcile and retire only that exact account before retrying; do not sweep other synthetic accounts or outbox files. Check the source and process identities again and retain real exit, log, request records and ORM results.

This sequence qualifies invite acceptance, recovery and access behavior only if the actual run succeeds. It performs no clinical generation, microphone, provider, Word-family, live payment, invoice or real-patient readiness qualification. The existing admin MFA/financial and SOAP/custom persisted checks remain required separately.
