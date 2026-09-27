# Independent bounded fixture review — 759e0dcd

Reviewed commit: `759e0dcd67d41d37d6753cf213fb0cb82b235b7b` in the release worktree.
**NOTHING FOUND** in the changed assertions/fixture setup. This was read-only code,
installed Django executor and manifest inspection, with no DB access, test rerun,
provider request or release edit.

- Queue-row wording matches `admin_console.live_generation_queue_row`: both
  generation and mapping jobs, live configuration, and queued/running/reconciliation
  counts. Existing `test_mapping_is_included_in_operator_drain_state` supplies a
  real mapping-job positive; the correction keeps unreadable-table negative and
  readable-table zero controls.
- Migration0022 rejects changes of an existing job's encounter, mapping version,
  user or kind. Creating the transcription kind at birth respects that guard;
  marking the old unheld generation fixture failed keeps it out of dispatch.
  Original succeeded/coding-invalidation assertions remain. The test still covers
  historical direct transcript adoption; it does not replace qualification of the
  newer reviewed-transcript application path.
- Installed Django `MigrationExecutor._migrate_all_backwards` unapplies each
  descendant in order. `unapply_migration` enters a separate schema editor with
  `atomic=migration.atomic` (default True), not one graph-wide transaction.
  Thus0021/0022 can already be reversed before0020 refuses. The test retains its
  immediate refused-state assertions for0020/schema/live evidence, then restores
  descendants before current Job ORM requires mapping_version.0021/0022 do not
  modify payment mode evidence. Repeated post-restore live evidence/schema checks
  and live-funded reservation preserve the original payment-integrity claim.
  This is not proof that a refused full-graph rollback changed no other schema.
- D19 independent manifest: **19 listed /19 actual**, no omitted or extra files,
  no duplicate path, and every SHA-256 matches. Its scope excludes the manifest
  itself and separately retained rendered images, as stated.

Root owns the repaired modules'80-test run and the original failed broader run;
this report does not claim those executions as independent new checks.

## Reviewed blob hashes

- rebuild/core/tests/test_configuration_status.py: `3c2dd6f4522ae89dd5d79db1d12cba9e7ae60bafa5b66c0cb97732c7e1681797`
- rebuild/core/tests/test_refutation.py: `23dc15bb4e116d9a7db5195e13a299d319abf120753fe131db74ff8cb34c6c3d`
- rebuild/core/tests/test_v1_real_mode_payments.py: `86b5491197e4a1d95d06afdae7aadc79db61f80db9a1da6a29a9eb19c7e6a609`
- docs/rebuild/v1/evidence/d19-20260927/independent/MANIFEST.json: `87f12e6835afdae2f3d74aa78991c2d06c40d81d75af4add7603afb39d84df2b`
