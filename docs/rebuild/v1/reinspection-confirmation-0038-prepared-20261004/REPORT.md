# Reinspection confirmation database boundary — 2026-10-04

Migration `0038_reinspection_confirmation_guard` extends the existing encounter function's exact-version confirmation predicate from contract v3 to **contract v3 or presence of an immutable reinspection key**. Its literal is exactly the 0031 body with that one predicate replacement; historical 0031 and 0035 SQL remain unchanged. No trigger, table, column or clinical/financial row is added or rewritten by 0038. The reviewed encounter-function body SHA-256 is `3d174c3dcd7986a7bac9443f1e6a07a83123ad655544606ea41b409b83642d74`.

The reverse checks for any reinspection key before restoring the unchanged 0031 function. Confirmed mappings and malformed/empty marker values still refuse reversal. The message contains a count, without document/account identifiers. Ordinary legacy-only state may reverse this one migration and reapply it without changing retained records. This is a code-rollback boundary, not authorization to downgrade an installed database.

## Actual verification and original evidence

Eight persisted database methods and two actual reversal methods passed on clean `7fbb8652a94acdccf1afc6ad9498d9ec69407d12`: 10/10 in 12.612 seconds; child and outer exit 0, 23.541116 seconds overall. The actual old-0031 counterexample remains archived: the historical dedac162 Encounter model successfully starts an unconfirmed reinspected legacy draft under the old body. After installing the new body, that draft survives and remains editable, finalization refuses, and its exact mapping confirmation permits finalization. New insertion and relocation refuse; confirmation of another mapping does not count. Six malformed marker values, altered/dropped import provenance, cross-department insertion and finalized-record mutation are denied. The old function fails the current integrity assessment with exactly one mismatch and the same 111 triggers; the new function passes.

The first ten-method packet failed during fixture setup with `value too long for type character varying(100)`: the protected wrapper's long scratch prefix made an absolute original path exceed the existing column. It reached no guard assertions. The corrected fixture uses the application's short relative original keys and isolated MEDIA_ROOT, while retaining every actual inspected blank original before assertions. Original failed source, all ten errors and their real exit 1 remain separate; they are not overwritten or replaced.

One separate populated installed-baseline upgrade method passed on the same clean source: 1/1 in 9.458 seconds; child/outer exit 0, 19.854314 seconds overall. Its exact twenty forward migration members include 0038. All historical column/row projections, original/private-file checks, balances, ledger/usage/reservation/payment/audit evidence remain unchanged; two authenticated historical original/final downloads succeed and two foreign-department downloads are denied. The original nineteen-migration reports remain historical evidence.

Both packets independently read their owned normal and test database identities before and after, and found them absent. The processes finished, no source changed, and no provider, renderer, installed service, payment, offsite operation or cleanup ran. Actual guard and upgrade source receipts live below the protected operations runtime:

| Packet | Result SHA-256 | Log SHA-256 |
| --- | --- | --- |
| `reinspection-095f661c-db-first-20261004` (retained failed setup) | `fa00b68422bffcba76b2f101c5cc97440c3024d76107b0d30cd9259a433ee263` | `4689dc1df9eb748f57b1b51cadaf4bbee1451d85f3a71201810a95b45a06dba5` |
| `reinspection-7fbb8652-db-second-20261004` | `e9bdf07c2e2916ecac780e086c64e0504c37e951ec0256f1110f26ba57c80ed1` | `ef549fc46ef9dff7f433673a2f0ef61dff7f89a5773ff7034280d425f66dcfa6` |
| `reinspection-7fbb8652-populated-first-20261004` | `0d4324283bb45a0ab08cea42bd4e9103f75099a4cb9928c9382eb67ca3d1f279` | `16d248aa11979d00f011837b1c4beda894b27213b00aae519a14af12f1ab4302` |

Nine final finite source controls passed separately in 0.066 seconds, exit 0. They bind the exact old/new SQL derivation, reviewed function hash, unchanged 111-trigger/28-function membership, reverse ordering/alias/count behavior, and refusal of the old source/catalog contracts. An intermediate test-only failure treated the tracked catalog **receipt** as a full raw contract; it is retained and corrected to an explicitly simulated source-envelope refusal. CI reads no protected raw catalog. The initial unqualified `python` invocation failed before source mutation because that binary is absent; subsequent commands use the recorded qualified interpreter.

## Remaining normal preparation renewal

`migration-delta.PREPARED.json` (`f03210cbe7607e228a2192cd6972d488291df3e9283bf9baf3f5bbffc9ff5575`) prospectively binds all twenty forward bodies and unchanged eighteen baseline bodies. Its 36→60 total tables / 29→53 core tables and unchanged columns are **expected catalog results**, not a newly completed full PostgreSQL capture. The full 0038 synthetic catalog proof, source schema and exact twenty-migration preparation/adapter renewal remain required before the normal fixture factory can consume this candidate. The old 0037/nineteen source contract refuses the additional migration, and its catalog source receipt refuses changed function-source bytes. No pin, contract or old report has been relaxed or relabeled.

Two small preparation corrections remain source-only. The catalog capture now refuses an actual core leaf different from its reviewed declared leaf before any baseline migration; this prevents its final migrate-all from silently applying 0038 under the old 0037 contract. The populated test previously archived original and final `historical.docx` by basename, so the original durable copy was overwritten although both source-file assertions and authenticated downloads passed. That limitation remains in the first actual 0038 receipt. Future captures use distinct relative `files/originals`, `files/exports` and `files/receipts` paths with exclusive creation. No additional database rehearsal or full catalog capture has run for these preparation-only changes.

After a coherent source freeze and a new serialized grant, the existing protected QA wrapper runs the two affected selectors:

```text
manage.py test core.tests.test_reinspection_database_guard --verbosity=2 --noinput
manage.py test core.tests.test_v1_upgrade_preservation.InstalledBaselineUpgradePreservation.test_populated_0018_forward_upgrade_preserves_rows_files_balances_and_authorized_download --verbosity=2 --noinput
```

Use separate owned databases, the retained 180-second child / 300-second caller supervisor, independent 30-second normal/test catalog before and after, new output directories, prospective full-source manifests and actual child/outer exits. A later full catalog renewal must use the reviewed twenty-migration schema and exact 0038 leaf; the currently retained 0037 capture command deliberately refuses this source. The 119 financial and 17 Word packets stay prepared until the integration owner freezes their coherent source and supplies their explicit resource handoff.
