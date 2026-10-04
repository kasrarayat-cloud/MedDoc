# Actual 0038 catalog and exact-twenty preparation renewal — 2026-10-04

The normal preparation and isolated fixture factory now require `0038_reinspection_confirmation_guard` and exactly **twenty** forward migrations from installed baseline `dedac1625032e32c7a149e6771be22e26c307eb1` / `0018_servicehealth`. This renewal follows actual isolated PostgreSQL execution and independent full-catalog comparison. It grants no installation, demonstration launch or real-patient activation.

The current source contract is [`schema-contract-0038.json`](schema-contract-0038.json), SHA-256 `47e45ec7ff94ce89cfa3ce8f3fbc514fa05eddb5e88e480d1ed58fa26706da96`. It has exactly the bytes prospectively declared in `schema-contract-0038.PREPARED.json`. The prior `schema-contract.json`, `postgresql-catalog-capture.json`, nineteen-migration reports and raw evidence remain historical and unchanged. `CATALOG-0038-PREPARED.md` describes the earlier capture barrier; this record documents its subsequently satisfied condition.

## Actual execution and complete catalog comparison

One owned empty database, `quillmd_qa_sol_installcontract38_1004`, ran the normal protected synthetic wrapper on clean commit `21415f6e56f0c949e1500a55b82e0890593384d8`. The capture validated all eighteen baseline and twenty forward migration files before migrating. Child and supervisor exits were **0**, with 8.146227 seconds for create/capture/drop and 10.720914 seconds for the outer packet. Source bytes remained unchanged. Zero connections remained before drop; the database was destroyed and both normal/test names were independently absent before and after. No renderer, provider, installed service/database or cleanup mutation occurred.

The append-only [`postgresql-catalog-capture-0038.json`](postgresql-catalog-capture-0038.json) receipt binds all **42** catalog-source files, exact schema bytes, raw catalog, child/supervisor results, full-source before/after records and both independent comparisons. The actual raw catalog remains outside the repository at:

`/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/storage-resume-20261003T215613Z/operations/catalog-0038-21415f6e-ACTUAL-20261004T144551Z/capture/captured.json`

Raw SHA-256: `4d0ae856d0ca66d513e079617bbb7bf3cb43c509377272ef16171c5abe5f9914`. The preceding 0037 raw catalog, SHA-256 `d2163c5fb2b35d5caf6355f7500772a50c1d818e742339f662ad383a2f1bf0b6`, is retained separately. No protected runtime artifact is read by CI.

The complete baseline catalogs are identical. Total/core tables remain **36/29 → 60/53**; the 0038 addition does not add a table or column. Target columns/defaults, constraints, indexes, all **111** trigger definitions/members, permissions, content types and the **28** function identities remain identical. Only `quillmd_encounter_guard()` body and definition change, each by the single declared predicate:

```sql
v.contract='v3' AND NOT EXISTS
```

becomes:

```sql
(v.contract='v3' OR v.import_manifest ? 'reinspection') AND NOT EXISTS
```

The exact old/new body hashes are `580e426b543a237ad47fd28b427b522eae312320259793b7f3052101d33c55ae` / `3d174c3dcd7986a7bac9443f1e6a07a83123ad655544606ea41b409b83642d74`. Owners, ACLs, function attributes and every other function row remain unchanged. All thirty-seven preceding migration files remain byte-identical. The new migration recorder row is the only additional recorder identity relative to the nineteen-migration transition.

Operations' complete comparison passed, SHA-256 `d67ba12791b67e402d6beea75dba40ad380dfa2df6f823cbd311803dafdbf6a7`. Root independently read both full raw catalogs and the 42 files on `07079a699f5ba68473d1b3b9b6fa65cb0381ab24`: **15 checks passed**, result SHA-256 `5efe40f77e0b7e9d58ac12144a9f5018bad6ace5f4e172e22e744dc9625507c9`. The catalog-source bytes match both commits. The root's earlier wrong-function-name instrument error remains distinct; its original tool transcript is retained, without a claim that a raw log was captured.

Before actual launch, one metadata draft was refused because an inner `result.json` would collide with the supervisor's exclusive result path. It was marked not executed; no database was created. The actual packet used separate `capture/result.json` and outer `result.json`. Neither draft nor any earlier failure was overwritten.

## Normal doors and retained safeguards

`ops/v1_private_install_preparation.py` now pins the new schema path/hash, explicit 0038 leaf and exact twenty-member graph. `ops/private_fixture_candidate.py` uses that same path. The installed lifecycle still derives its exact migration plan from the declared schema; its phase is `apply_exact_twenty_forward_migrations`. No trigger, catalog, permission, source or migration check was removed or made count-only.

The actual normal driver must read the complete raw catalog and authenticate the exact candidate source, merged PR, required successful exact-revision `CI` and `secrets-scan`, stopped historical rows/files, financial state, unrelated-service identities and rollback assets. The tracked receipt and simulated pure-test catalogs cannot substitute for those reads. An unchanged old schema or old raw catalog refuses current source. Missing 0038, an extra 0039, or self-consistent source/declaration dictionaries that omit a required migration also refuse.

The installed auto/v4 candidate still needs the fixed **54/60** overall and **18/20** holdout Word family/safety gates plus genuinely useful source-bound model evidence. Manual recovery receives no automatic correctness credit. Existing rights holds, synthetic-only operation, test payments, public maintenance and CPT-disabled controls remain. The fixture-only demonstration exception still requires its own exact CI/source/refutation/state checks and does not authorize the installed transition.

## Affected verification and limits

The renewed preparation, adapter, fixture factory, source/receipt controls and actual migration-literal integrity assertion ran **42 provider/DB-free tests**, all passing in 0.647 seconds; actual process exit **0**, outer 1.294744 seconds, process reaped and source unchanged. Protected packet: `operations/catalog-0038-renewal-pure-20261004T150035Z`; log SHA-256 `85855bc2a454c06fdd4668a9702900c8cd797121c090ca2b8abf462e38adad64`. These tests use portable repository evidence and clearly simulated backend/catalog controls.

The earlier actual guard packet remains **10/10**, including eight persisted guard methods and two reverse controls; the populated 0018→0038 preservation method remains **1/1**. Their failures, original 0037 reports, row/file projections and evidence limits are retained in `reinspection-confirmation-0038-prepared-20261004/REPORT.md`. This renewal performs no repeat populated upgrade, installed transition, offsite restore drill, alert send or external approval. It establishes an accessible engineering prerequisite, not release readiness.
