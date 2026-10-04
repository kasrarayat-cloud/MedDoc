# Historical migration fixtures after the 0038 rollback repair

The current-import fixture remains the default. A keyword-only `historical_empty_import=False` option creates a genuinely historical initial template version with empty import metadata only when explicitly selected; it does not clear or relabel any existing imported record. The original blank DOCX, actual inspector mapping, immutable original hash and department boundaries remain the same.

Only the coding-at-transcript-leaf, payment-mode reversal and reconciliation evidence-kind migration fixtures opt in. Their original behavioral assertions are unchanged. The reinspection reversal fixture separately proves that a historical initial record can reverse and reapply 0038 without record changes, while actual current-import evidence or a reinspection marker refuses reversal before the guard, applied migration set or rows change. The refusal retains count-only privacy. Three pure controls prove the composed previous-leaf guard is called once with the same applications and schema editor, including propagation of its original refusal without writes.

The original failed C CI and root rollback packet remain retained. This adapts historical test data to its declared migration era; it does not bypass the current import or signing guards.

## Actual affected packet

- Frozen source `9a161e1db39e31dc9b3686b45f4a016119f80f00`, on corrected 0038 base `88b9ba61db93da3065fef45f189c3f156a638b45`. Test-only changes: `92432bb05e259bf538b9e1c98f38cd4aca640350`; the subsequent commit changes only the new append-only catalog receipt filename expected by its test.
- Fourteen methods passed: eleven persisted migration/guard methods and three pure composition controls. Django took 62.633 seconds; the bounded supervisor returned actual exit 0 after 73.100380 seconds. No timeout or retry.
- Exact source files were unchanged before and after. The normal and test names for `quillmd_qa_sol_ops_historical1004` were directly absent before and after; the test destruction message and completed process wait were retained. No provider, renderer or installed service was used.
- Protected evidence: `/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/storage-resume-20261003T215613Z/operations/historical-fixtures-92432-actual-20261004T180600Z`. Log SHA-256 `169cf0e3a686baffaf7bf2abd0828d79ea257127de4b375b3e85099877ed39ba`.

An earlier direct-unittest probe failed because Django settings were not initialized. Its raw failure is preserved separately; configuring only `AUTH_USER_MODEL` allowed the same three pure controls to pass. That probe used no database. The packet above uses the normal protected QA wrapper.

This is affected regression evidence. It does not replace exact-revision CI, current catalog/source renewal, Word acceptance, provider qualification or release approval. Historical 0037 and first 0038 catalog receipts remain unchanged.
