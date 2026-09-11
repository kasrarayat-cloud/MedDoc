# JUDGEMENT — the #312 confirm of the re-issued 53-control form (ruled act)

**Judged against `docs/foundation/mutations/20260910-confirm-reissued-form.md`,
every row of it.** The declaration was committed at `a36d7c10`,
2026-09-11T02:25:18Z. The clean dry run ended at 04:38:48Z with exit 0. The
commit run started at 04:39:3xZ, and every audit row landed between
04:39:34.741Z and 04:39:34.912Z.

## VERDICT — 🟢 every declared quantity holds. One 🟡: a wording inaccuracy in the declaration (a target type), with no data deviation.

**Pre-guards, printed by the door before any write: 23 of 23 ✓.** They include:

- the whole 53-row set is byte-identical to the judged `dd4dc378…`;
- 0 audit rows already name the act;
- 43 rows were CERTIFIED before the act, and 0 decided rows had drifted;
- manual rules: no concept, and no policy on any manual row.

### MUST CHANGE, all on `d2120cdd`

| row | declared | before | after | |
|---|---|---|---|---|
| mappings `CERTIFIED` | 43 → 53 | 43 | **53** | 🟢 |
| RECOGNIZED / NEEDS_CONFIRMATION | 9 / 1 → 0 / 0 | 9 / 1 | **0 / 0** | 🟢 |
| sourceType `manual` | 0 → 3 (56, 70, 71); concept NULL, `unmentionedPolicy` NULL | 0 | **3**; rows 56, 70 and 71 are `manual / NULL / NULL` | 🟢 |
| sourceType `visit_metadata` | 2 → 2 (Patient, Age), now CERTIFIED | 2 | **2** | 🟢 |
| sourceType `extraction` | 51 → 48 | 51 | **48** | 🟢 |
| `approvedById` set / `approvedAt` set | 0 → 53 / 0 → 53 | 0 / 0 | **53 / 53**, 1 distinct approver (the owning doctor) | 🟢 |
| the stamp on the 43 transferred rows | declared: the approval of the mapping SET | none | included in the 53 above | 🟢 |
| `audit_logs` | +12 | 12519 | **12531** | 🟢 |
| of which `TEMPLATE_TWIN_MAPPING_UPDATED` | +12 | 94 | **106** | 🟢 |
| of which name `ruling #311(d)` | 11 (the door's rows) | 0 | **11** | 🟢 |
| the resulting set sha, on the door's aggregate row and the writer's row | both carry it, and the door reads it back | — | **`33ffb02b…` on BOTH** set-level rows | 🟢 |
| the aggregate row's contents | `approvedAsASet 53`, `confirmedFieldIds` ×10, `carriedOverFromTransfer 43`, `certifiedMappingCount 53` | — | **53 / 10 / 43 / 53**, plus `confirmingActor`, `decisionRuling` and `declarationCommit` | 🟢 |

### MUST NOT CHANGE

| row | before | after | |
|---|---|---|---|
| the certified ACTIVE `18a7ae19`'s mappings (53, all columns) | md5 `94bc1c1a…` | **`94bc1c1a…`: not one row** | 🟢 |
| `d2120cdd.certificationStatus` | NEEDS_CONFIRMATION | **NEEDS_CONFIRMATION** | 🟢 |
| certifications · compiled versions · fill manifests · source artifacts · note templates | 4 · 6 · 5 · 8 · 17 | **4 · 6 · 5 · 8 · 17** | 🟢 |
| ACTIVE template / the draft | `939aa9ea` active / `3877d5cf` draft | **unchanged** | 🟢 |
| **clinical: visits · patients · signatures** | **58 · 46 · 40** | **58 · 46 · 40** | 🟢 |
| `ai_calls` / `api_usage_events` (no model is called) | 1686 / 1867 | **1686 / 1867** | 🟢 |

### 🟡 THE DIFFERENCE THE DECLARATION DID NOT NAME

The declaration described the writer's set-level audit row as targeting *"the
note template"*. **Measured, it targets `TemplateTwinCompiledVersion`**, the same
type as the door's aggregate row. Its keys are `certifiedMappingCount`,
`mappingCount`, `mappingsSha256` and `templateVersion`, and it carries the
resulting sha.

The count, the action and the sha are all as declared. Only the declaration's
description of the writer's target type was wrong: the writer has always written
that target. The declaration wording is corrected here and not re-written, and
nothing in the data deviates.

## ⚠️ THE EXIT CODE IS 143, FOR THE SAME REASON AS THE BACKFILL

The script printed its END STATE (`resulting mapping-set sha: 33ffb02b…`) and
**"🟢 confirm complete: 10 confirmed under ruling #311(d)"**, and then did not
exit. Its dry run had exited on its own, so the handle opens on the WRITE path.
The orchestrator's watcher waited for the completion line, gave an 8-second
grace, verified the in-container pid's command line
(`scripts/confirm-reissued-form.ts`) and sent SIGTERM to that pid only, at
04:39:44Z. The door then printed `exit 143`. **What landed is the snapshot diff
above, not the exit code.**

Filed as `RULED-ACT-SCRIPTS-DO-NOT-EXIT`.

A `pg` deprecation warning also printed ("client.query() when the client is
already executing a query"). It is noise, recorded here.

⚠️ **My first confirm dry run (04:37:44Z) was killed 7 seconds in by the
orchestrator's own watcher.** The watcher keyed on "DRY RUN", which the door
prints in its header. It wrote nothing: the mapping-set md5 was unchanged at
`5b1c7db8…`, and 0 rows named `#311(d)`, both verified. It was re-run with the
watcher keyed on the script's final line.
