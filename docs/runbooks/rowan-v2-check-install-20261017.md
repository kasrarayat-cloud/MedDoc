# Rowan independent v2 check installation

This procedure is prepared, not executed. The lead remains the sole deployment
and provider-call owner. Both earlier Rowan installation operators and the v1
independent check are consumed. Do not rerun them or replace their evidence.

The new entry point is `python -B -m ops.activate_rowan_v2`. Without `--execute`
it reads no operational inputs and performs no database, service or provider
operation. Focused offline checks are
`python -B -m unittest ops.test_activate_rowan_v2`.

## Declared installation boundary

- Installed base is exactly `e069f3cdcf01bbc689e2eb66d2f8b41eab8f46e5`.
  Publish the complete hash-bound tracked-source difference to the merged
  candidate after that exact commit passes current CI and secrets-scan.
- Apply only `0031_retained_semantic_revalidation_v2`: one literal `RunSQL`
  replacing `public.quillmd_ai_stage_guard()`. Its installed pre-migration
  `pg_get_functiondef` MD5 must be `89bb50ff163624cd3577f543d68e0933`;
  the reviewed post-migration MD5 is bound in the plan. Keep its owner/ACL,
  every other function, tables, columns, constraints, triggers and indexes fixed.
- Add only `QUILLMD_SEMANTIC_REVALIDATION_V2_ORIGIN_JOB_IDS` with original job
  `1e56aac0-69ae-4927-bd75-168beb8b4a95`, and update the release SHA. Retain
  the consumed v1 setting, Corti configuration, credentials, provider selection,
  billing configuration and all other environment bytes and values.
- Publish only declared changed supported public static aliases, if needed,
  preserving historical hashed assets. With no static changes, retain every byte.
- Stop and restart only the three existing native QuillMD services. Keep unit
  configuration, normal HTTPS ingress, the separate Corti preview and unrelated
  services unchanged.

All existing database rows and clinical files must match between the pre-stop
baseline and pre-resume snapshot. This includes the original failed Rowan case,
the fresh original generation, the failed v1 check
`8d77cf06-4277-4746-bf13-336ad08c6df1`, all receipts, usage, reservations,
decisions, audit rows and the existing Corti prediction. The only row addition
during installation is the new migration ledger row; only its sequence advances.
Installation sends no provider request and creates no clinical decision.

The database snapshot covers its named catalog properties, not every possible
PostgreSQL property. The exact migration must also parse before stopping and
before execution as one literal function replacement with no extra imports,
Python execution, SQL statements or operations. This prevents unwatched DDL from
being introduced by the migration. The newly installed function is not invoked
as part of this installation.

## Execution preparation

1. Complete focused tests and the clinical refutation pass. Merge through the
   guarded PR procedure, then wait for required workflows on the exact merged
   candidate. Do not substitute ancestor results.
2. Keep `/opt/meddoc-pro` on clean installed `main` at the exact base. Keep the
   candidate worktree clean at the merged revision. Bind a new private plan with
   every changed tracked path/hash, source worktree, current protected environment
   hash, exact old/new guard hashes and the changed supported static aliases.
   The format is `quillmd-rowan-independent-v2-native-install-v1`.
3. In a separate execution worktree directly descended from that candidate,
   commit a new prospective declaration naming the full candidate, private plan
   hash, format, expected deltas and preservation scope. Use a new private output
   directory. Preserve earlier plans, declarations and attempt directories.
4. From the **execution worktree's cwd**, run its existing
   `scripts/run-ruled-mutation.sh --declaration <absolute committed declaration>`
   with `env PYTHONPATH=<clean candidate>/rebuild` and the installed venv Python
   executing `-B -m ops.activate_rowan_v2 --execute --plan <private plan>
   --plan-sha256 <exact hash>`. Leave wrapper/watchdog supervision enabled. The
   wrapper resolves the declaration in its cwd; operator code comes from the
   clean candidate, not the declaration-only child.
5. Inspect the installation receipt and normal HTTPS health revision. Only then
   may the lead perform a separately bounded ordinary-dashboard v2 submission.
   It must have a new contract/job identity bound to the failed v1 predecessor,
   one new standing-authority reservation and one checker operation. Installation
   does not submit it. A failed or inconclusive v2 result remains a hold.

Every subprocess, lock, migration and readiness wait is bounded. No automatic
provider task, retry or clinical recovery is built into the operator. Before any
source change, a failure may resume the original units. After a source/schema
change it leaves stopped units stopped for diagnosed recovery; it never repeats
the migration or overwrites evidence automatically.
