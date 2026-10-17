# Rowan recovery follow-up installation

This is a prepared procedure, not evidence of installation. The lead is the sole
deployment owner. The first Rowan activation is complete at
`bb8a185dc76cec8bff35820155e9416b24c087ea`; do not rerun that consumed operator.

The new inert entry point is `python -B -m ops.activate_rowan_followup`. Without
`--execute` it does not read operational inputs or perform any action. Its
focused offline checks are `python -B -m unittest ops.test_activate_rowan_followup`.

## Exact prospective delta

- Publish the complete, hash-bound source difference from installed `bb8a` to the
  PR-merged candidate, after the exact candidate passes current CI and secrets-scan.
- Apply only `0030_retained_semantic_revalidation`. No table, column, constraint,
  trigger, index or prior migration-row change is admitted. Only the exact
  before/after body hashes of `public.quillmd_ai_stage_guard()` may differ; its
  owner and ACL, and all other functions, must stay identical.
- Add `QUILLMD_SEMANTIC_REVALIDATION_ORIGIN_JOB_IDS` containing only
  `1e56aac0-69ae-4927-bd75-168beb8b4a95`, and update the release SHA. All other
  environment bytes and values remain unchanged, including Corti configuration,
  credentials path, prospective cutoff, actor scope and billing settings.
- Publish only declared changed public static aliases, if any, retaining all
  historical hashed assets. If no static source changes, static bytes stay fixed.
- Stop and restart only the three existing native QuillMD units. Preserve unit
  configuration, ingress, the separate Corti preview and all unrelated services.

Every existing database row and clinical file is measured before stopping and
again before resuming. The sole row addition during installation is the migration
ledger row. The migration sequence advances once. Installation creates no
clinician decision and sends no provider request. The later ordinary-dashboard
recheck is a separate, bounded action; installation does not execute it.

The catalog snapshot covers the named table/column, constraint, index, trigger,
function and sequence properties; it is not a universal catalog fingerprint.
Before stopping and again before migration, the hash-bound migration must parse
as exactly one `RunSQL` with literal forward/reverse replacements of the one
named function. Additional SQL, imports, executable Python, operations or other
DDL are refused, including column-default changes outside the snapshot's scope.

## Execution preparation

1. Review the finished clinical and migration diff, with its required refutation
   and focused checks. Merge through the existing guarded PR procedure and wait
   for the exact merged candidate's required workflows. Do not use ancestor CI.
2. Keep `/opt/meddoc-pro` on clean installed `main` at `bb8a`. The separate clean
   candidate worktree must be exactly the merged candidate. Bind a private plan
   containing every changed tracked path and committed SHA256, the current native
   environment SHA256, the exact before/after function MD5s measured through the
   isolated migration check, and only the changed supported static names.
3. Review the plan and write a new prospective declaration in a separate execution
   worktree, directly descended from that candidate. Commit the declaration before
   any act. It must identify `quillmd-rowan-recovery-native-install-v1`, the full
   candidate revision, plan hash, expected deltas and preservation scope. Existing
   declaration and evidence directories remain unchanged.
4. From that **execution worktree's cwd**, invoke its existing
   `scripts/run-ruled-mutation.sh --declaration <absolute committed declaration>`
   with `env PYTHONPATH=<clean candidate>/rebuild` and the installed venv Python
   executing `-B -m ops.activate_rowan_followup --execute --plan <private plan>
   --plan-sha256 <exact hash>`. The wrapper resolves tracked declaration membership
   against its cwd; running from the candidate worktree with a declaration tracked
   elsewhere fails that gate. The operator code comes from the clean candidate,
   never the declaration-only child. Leave wrapper/watchdog supervision enabled.
5. Read the new receipt and verify normal HTTPS `/health/` names the full candidate.
   Resume the separately bounded ordinary clinician recovery/review/download flow
   only after successful installation. Retain every original and follow-up failure.

The operator has bounded subprocess, migration, lock and readiness waits. It has
no provider operation, retry path or automatic clinical recovery. If a failure
occurs before source publication, it may resume the unchanged original units. If
source or schema has changed, it leaves stopped units stopped for an explicit
diagnosed recovery. Once units resume, it does not automatically stop or rerun
them. An existing output directory refuses execution; do not overwrite evidence
to make an attempt look new.
