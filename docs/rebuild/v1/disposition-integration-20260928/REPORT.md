# Recovered disposition preparation — author validation

The isolated candidate now records review-only disposition requests, bounded dependency snapshots, distinct-custodian reviews and quarantined restore preparations on the integrated batch schema. It repairs demonstrated gaps in the recovered draft; no installed records, retention durations, destruction permission or production configuration changed. Independent finished-diff refutation is still required.

Base `9f2bdad03dfc135befceae12a600bb0f86c7f7be`; branch `fix/v1-disposition-integration`. The original dirty `v1-disposition-preparation` tree at3ee445b8 remains untouched. Its22-file snapshot was verified stable at03:26:48Z/03:27:56Z and preserved under shared `.runtime/v1-full-release-20260928/operations-recovery/`; original tracked patch SHA256 `9352d14901d99444a769521d57c4bdb6947be57a4733e86f75d899c1fc96cd04`. All earlier failed evidence remains available.

## Concrete defects and resulting behavior

| Retained counterexample | Recovered behavior | Repaired behavior and source |
|---|---|---|
| Known integrated0027 schema, otherwise valid proposal | Closed base catalog refused every plan;10 errors in16-test recovered pass | Four batch families and the immutable mapping constraint column explicitly cataloged; all other unknown schema changes still refuse. `core/disposition_catalog.py`; `disposition.py:22`. |
| Terminal batch, child in reconciliation, independent immutable response reference | Graph omitted batch/part/response nodes and response-only path; changing a late event did not invalidate review | All batches, children, events and immutable response paths enter the snapshot regardless of parent state; late change requires a new plan. `disposition.py:40`. |
| Restore quarantine, direct mapping/batch worker call | Direct worker entry bypassed the ordinary dispatcher guard | Each actual worker entry checks quarantine before querying or claiming work. `mapping_jobs.py:96`; `batch_jobs.py:262`. |
| Quarantine with private-preview authentication enabled | Preview sign-in returned503; public CSS blocked | Exact preview authentication endpoints and static assets remain reachable; clinical/data routes remain503. `disposition.py:199`. |
| Raw SQL/ORM insertion with another proposal target/department/scope or string-valued false | Database accepted contradictory plan metadata | Trigger binds scope/target/department to the immutable request, requires the exact review-only contract and a JSON boolean false. `migrations/0028_disposition_preparation.py`. |
| Restore row claiming journal freshness, a mismatched report target/backup, or string-valued true | Database accepted contradictory evidence | Trigger requires typed quarantine/no-admission/no-journal-proof flags and matching instance/target/backup references; it does not infer external authenticity. Same migration. |
| Two mocked requests leave101 valid answers recorded; set quarantine, then call direct finish | Answers changed fromempty to101 adopted entries despite quarantine | Direct completion refuses before reads/adoption. `batch_jobs.py:217`. A separate valid administrator recovery case also refuses before settlement or adoption (`:423`). |

The first combined adoption/recovery probe correctly demonstrated adoption but used a nonadministrator for recovery, which raised an unrelated permission error. That result is retained as04. The corrected05 contains two separate valid cases, both failing before the fix; it is the recovery counterexample authority. No provider request in any test reached a network endpoint; generated responses are explicit synthetic mocks.

The graph is deliberately a review-dependency snapshot. It never emits deletion authority. Account/access and ordinary audit bodies are not purge candidates; no deletion adapter for them is supplied. An additional regression snapshots every existing concrete core row, embeds synthetic signature/consent markers, and proves exact equality after proposal/review; pre-existing audit rows are also unchanged. Only the new preparation records and corresponding new audit events append. This verifies preservation for that finite case, not a complete future account/clinical purge graph.

## Migration and integrity union

0027 batch and0028 preparation both descend0026; empty merge0029 preserves both. The exact restore contract now covers63 guards/18 function bodies: all51 prior guards and17 prior function-body hashes are preserved, plus12 preparation guards and one new body. Positive actual-PostgreSQL checks and negative disabled/replaced trigger controls pass. No scanner identity or qualification pin was updated.

No schema/model drift was found by the no-network MigrationLoader/Autodetector check; core has exactly one leaf `0029_merge_batch_disposition`. The batch feature and restore quarantine both defaultfalse; no product activation happened. Quarantine must be selected before using a restored target and does not itself authenticate target installation or external instructions.

## Author validation

- **116 focused/affected checks PASS, zero skips**,140.278s test time. Includes all new preparation/integration cases, existing preservation/concurrency/readiness cases, batch workflows with quarantine off, mapping assistance and exact restore-integrity/file-reference checks. The uniquely named disposable database was destroyed after the run.
- Earlier retained stages:01 recovered16 tests,10 catalog errors;02 seven counterexample tests,13 failing assertions and one catalog error;03 repaired23 checks pass;04 one adoption/recovery probe with2 failures/one permission error;05 corrected two valid adoption/recovery failures. The final116 supersedes author partial passes without erasing failures.
- All test runs used the root-owned synthetic PostgreSQL container identity and verified loopback55821/owner label, unique `test_v1_disposition_<tag>` databases, scrubbed managed environment, fixture mode and no installed credentials. Source hashes remained unchanged through each run. First manifests01/02 tracked only tracked files; original untracked source identity comes from the preserved22-file snapshot. From03 onward, manifests also bind untracked source files.
- Schema/profiles: closed catalog matches; no model changes pending; single merged leaf;63 guards/18 bodies; feature defaults off. This pure check denied sockets and opened no database connection.
- Refero reference lock applied; existing hold/invitation/services screens retained. Actual Django-rendered form HTML was rendered in Chromium at1280px and390px using intercepted local assets only. All four views had no horizontal overflow or unlabeled visible inputs. Desktop restore and mobile proposal screenshots were inspected against the reference. Existing native details/buttons/labels and explicit unavailable notices remain. MFA, CSRF and exact scope-error form behavior are exercised by Django tests. This is not a full deployed browser workflow or accessibility certification.

Reproduce the affected author run with `python3 rebuild/.runtime/disposition-integration/run_tests.py <new-tag> core.tests.test_disposition_integration core.tests.test_disposition_preparation core.tests.test_restore_integrity_contract core.tests.test_retention_preservation core.tests.test_retention_readiness core.tests.test_generation_batch.BatchWorkflow core.tests.test_mapping_assistance ops.test_production_restore_check`. The retained runner verifies the root-owned synthetic container and refuses reused log names; never point it at an installed or production database. Exact labels/timing/source hashes and original failure logs are retained privately, with bounded copied evidence alongside this report.

## Remaining gates

This is local candidate engineering, not installed behavior: installed dedac162 remains synthetic-only. No paid provider/token-count/payment, restart, deployment, source overwrite in another tree or clinical/corpus artifact acquisition occurred. No new retention policy was chosen.

Independent finished-diff refutation and an independently witnessed migration union remain pending at this author freeze. General executable disposition, effective tombstones, idempotent row/file purge, external-copy ownership and expiry, independent instruction-journal freshness/replay, backup reconciliation and restored-instance admission remain unfinished engineering. Counsel/owner schedule/start events/hold authority and downstream procedures remain external inputs. Preparation alone does not close B-L6 or qualify launch.
