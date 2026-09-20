# Review of the 12 skipped operations tests — 2026-09-20

## Result and scope

All 12 checks skipped in the final `8aa1d1d4` CI run executed successfully on the
actual VPS at 14:52 UTC, with no skips. The same 12 also passed before the test-only
repair. No activation, migration, worker restart, database write or provider call
was performed by this review.

Ten skips were missing Git history in CI; two were missing QuillMD systemd service
infrastructure in CI. None denotes retired product functionality or an uncovered
doctor workflow. The ten historical checks still protect the recorded scope and
provenance of completed one-time activations; preserve them and their historical
results. The activators themselves must not be rerun merely to exercise tests.

Historical evidence, retained unchanged:

`rebuild/.runtime/overnight-completion-20260920/resume-merge-ci-pass.log`

That log reports 374 operations tests, 12 skipped. It describes the old CI run,
not the results below.

## Individual classification

All identifiers below are in `rebuild/ops/`. “Git unavailable” means authentic
release objects or the trunk ref were not fetched in the default shallow CI
checkout. “Service unavailable” means the GitHub runner has no active
`quillmd-fresh-worker.service`.

| # | Exact unittest identifier | Classification and assertion | Actual VPS result |
|---|---|---|---|
| 1 | `test_audio_submission_activation.AllowedPaths.test_every_path_this_activation_shipped_was_declared` | Git unavailable; completed activation's real changed paths against its declared allowlist | Passed |
| 2 | `test_audio_submission_activation.AllowedPaths.test_the_shipped_sha_is_a_merge_commit_on_the_trunk` | Git unavailable; historical target is a two-parent merge on main's first-parent history | Passed |
| 3 | `test_audio_submission_activation.AllowedPaths.test_what_shipped_is_a_descendant_of_the_release_it_replaced` | Git unavailable; authentic before/after ancestry | Passed |
| 4 | `test_audio_submission_activation.TheWorkerIsIdentifiedByMoreThanItsPid.test_it_describes_this_host_correctly` | Service unavailable in CI; current live PID, command, cgroup and process-start evidence | Passed against running worker |
| 5 | `test_billing_activation.AllowedPaths.test_every_changed_path_since_the_running_release_is_declared` | Git unavailable; completed billing migration's authentic changed-path set | Passed |
| 6 | `test_recording_limit_activation.AllowedPaths.test_every_path_this_activation_shipped_was_declared` | Git unavailable; completed recording-limit activation's authentic changed-path set | Passed |
| 7 | `test_recording_repair_activation.AllowedPaths.test_every_path_this_activation_shipped_was_declared` | Git unavailable; completed recording-repair activation's authentic changed-path set | Passed |
| 8 | `test_recording_repair_activation.AllowedPaths.test_the_shipped_sha_is_a_merge_commit_on_the_trunk` | Git unavailable; historical target is a two-parent merge on main's first-parent history | Passed |
| 9 | `test_recording_repair_activation.AllowedPaths.test_what_shipped_is_a_descendant_of_the_release_it_replaced` | Git unavailable; authentic before/after ancestry | Passed |
| 10 | `test_recording_repair_activation.TheWorkerIsIdentifiedByMoreThanItsPid.test_it_describes_this_host_correctly` | Service unavailable in CI; current live PID, command, cgroup and process-start evidence | Passed against running worker |
| 11 | `test_service_date_activation.AllowedPaths.test_every_path_this_activation_shipped_was_declared` | Git unavailable; completed service-date activation's authentic changed-path set | Passed |
| 12 | `test_storage_migration.MigrationInvariants.test_allowed_set_names_every_tracked_change_and_the_declaration` | Git unavailable; completed new-system storage migration's authentic changed-path set and declared resources | Passed |

## Focused repair

The Python CI job now fetches full Git history (`fetch-depth: 0`) and explicitly
requires a non-shallow checkout and fetched `origin/main`. Only that job needs the
history. The two trunk tests read the fetched remote ref, with a local-main
fallback for non-remote local checkouts. This works when a PR checkout is detached
and has no local main branch; it does not create or move any repository refs.
Actual ancestry and changed-path assertions are unchanged. Shallow developer
checkouts retain their honest missing-input skips.

The two live service tests retain their CI skips. Starting a fake service under
the production unit name on a GitHub runner would not prove this VPS's identity.
Instead, `test_worker_identity_fixtures.py` adds five deterministic tests (21 cases
across the two historical helpers and the helper used by the latest completed
private activation):

- Valid identity records both kernel and systemd start sources.
- No main PID refuses before any process inspection.
- A PID in an unrelated service cgroup refuses.
- A foreign interpreter, non-worker management command, or unrelated script refuses.
- A process disappearing during inspection propagates failure; it is not accepted.

All process, systemd and external command inputs in those fixtures are isolated.
These are negative-path tests of the real helper functions, not claims that a
service was restarted or interrupted on the host.

## Executed evidence

Protected evidence directory:

`rebuild/.runtime/operational-recovery-20260920/`

- `skipped-coverage-focused.log`: the 12 original checks plus five new tests;
  **17 passed, 0 failed, 0 skipped**.
- `skipped-coverage-focused.json`: exact test names, UTC timestamp, source hashes,
  baseline Git head, and live worker snapshot. PID `2964610`, service
  `quillmd-fresh-worker.service`, dedicated rebuild interpreter; kernel start
  `2026-09-20T09:51:41.870000+00:00`, systemd start `09:51:42 UTC`.
- The same JSON records **two additional passing detached-checkout tests**. They
  used temporary Git metadata containing only a remote-main ref, authentic existing
  commit objects read through an alternate, and no local main ref. Both original
  trunk assertions ran without skips. The temporary metadata was removed.
- An earlier focused run of the two modified activation test modules and the new
  fixture module passed **48 tests, 0 skipped**. The persisted 17-test result above
  is the concise repeatable acceptance evidence.

The code under test here was the feature worktree based on
`8aa1d1d4efe090d6f0e6e1bf7d594375ddca9940`, with the listed test/CI changes. The live
worker remained the existing release. CI and any operational integration
activation must be cited separately in the milestone closeout; these local
results do not claim remote CI has already run.

## Remaining coverage boundary

The next CI run should execute all ten Git checks and retain precisely the two
host-only worker skips from this reviewed set. Review actual CI output to confirm
that expectation. CI still cannot independently certify this VPS's running
process; this review's read-only host checks provide that evidence. There is no
remaining unexplained coverage gap among these 12 checks. This classification is
not a claim of exhaustive application, recovery or security coverage.
