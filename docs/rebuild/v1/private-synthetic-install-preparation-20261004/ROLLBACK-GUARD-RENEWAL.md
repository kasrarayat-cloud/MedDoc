# Backward guard source renewal — 2026-10-04

The original confirmed-v3 rollback control failed on candidate63460193:
`0038_reinspection_confirmation_guard` disappeared from the applied migration
set before an older migration refused. Root independently reproduced the actual
failure (child exit1,14.074s), with source and owned DB disposal verified.
Original stderr, assertions and rows remain in the protected evidence root.

The newest leaf now calls0037's unchanged prior evidence refusals before its
reverse SQL can replace the guard. Forward SQL and every preceding migration
file remain byte-identical. The existing confirmation/correction rollback
controls and eight reinspection forward controls now pass. The first combined
26-method packet still failed on nine historical fixture blocks: their generic
fixture now creates import provenance contrary to their explicit no-import
precondition. No manifest or guard was cleared to get a passing result; those
fixtures require explicit historical construction and separate current-import
negative controls. This receipt does not claim that packet passed.

The full migration-file source binding changed, so the old schema/capture
receipts remain historical and the normal installer is renewed only from an
actual recapture. The normal bounded capture on4456b6cc completed with actual
child/outer exit0 in11.571s. Its owned database was destroyed, catalog count0,
connections0, source unchanged, no timeout, provider, renderer or installation.
Root compared complete before/after catalogs, permissions and content types
against the preceding actual capture: all identical. The only42-source witness
delta is the0038 Python file. This is neither a schema bypass nor a deployment.

New schema SHA256:
`8be79bb31d92f109b4112e751d1ac2d8e38050c631585a66e2c47b4970e829ac`.
Raw PostgreSQL capture SHA256:
`2304953b86847d7552ec2702baa959889ff63abdb7ea7bc545706fabf9622932`.
Full independent root comparison SHA256:
`8b3930d3c28879c065489def136a7efbfd58d1d9d326e7ed17682c8d01d459e8`.
Protected directory:
`operations/root-catalog0038-leaf-PREPARED-20261004T1754` under the storage
continuation evidence root. Its PREPARED directory name is historical; actual
results inside explicitly record completed execution and disposal.

The new append-only schema and receipt identify the repaired source. Previous
0037 and0038 preparation/capture files remain unchanged. Populated preservation,
finished-diff refutation, exact revision CI and product gates remain distinct.
